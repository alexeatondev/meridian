#!/usr/bin/env python3
"""Meridian on AWS (CDK). One stack, region us-east-2 by default.

  CloudFront (HTTPS) ──VPC origin (private)──▶ internal ALB ──▶ ECS Fargate (Meridian app container)
                                                     │                │
                              Cognito user pool ◀────┘                └──▶ RDS PostgreSQL (isolated subnets)
  Secrets Manager: DB credentials, session key, ingest token, Cognito client secret.
  No NAT gateway (cost): tasks run in public subnets with a public IP but accept traffic only from the load
  balancer; the load balancer and the database sit in private subnets with no internet route. CloudFront reaches
  the load balancer through a CloudFront VPC origin, so it has no public address (NIST SP 800-53 SC-7).
"""
import os

import aws_cdk as cdk
from aws_cdk import (CfnOutput, Duration, Fn, RemovalPolicy, Stack, aws_cloudfront as cf,
                     aws_cloudfront_origins as origins, aws_cognito as cognito, aws_ec2 as ec2, aws_ecs as ecs,
                     aws_ecs_patterns as ecsp, aws_logs as logs, aws_rds as rds, aws_secretsmanager as sm)
from aws_cdk import aws_budgets as budgets, aws_elasticloadbalancingv2 as elbv2, aws_iam as iam
from constructs import Construct

ROLES = ["portfolio_manager", "risk", "analyst", "manager_selection", "leadership", "compliance", "audit", "admin",
         "investment_committee", "chief_compliance_officer", "route_manager", "approver"]   # last four: permission flags, not workspaces
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _cognito_css() -> str:
    """The active brand theme as Cognito sign-in CSS (src/meridian/branding.py)."""
    import sys
    sys.path.insert(0, os.path.join(REPO_ROOT, "src"))
    from meridian.branding import cognito_css
    return cognito_css()


class MeridianStack(Stack):
    def __init__(self, scope: Construct, cid: str, **kw):
        super().__init__(scope, cid, **kw)

        vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=0, subnet_configuration=[
            ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
            ec2.SubnetConfiguration(name="db", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24),
            ec2.SubnetConfiguration(name="lb", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24)])

        db = rds.DatabaseInstance(
            self, "Db", engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_16),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE4_GRAVITON, ec2.InstanceSize.MICRO),
            vpc=vpc, vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            credentials=rds.Credentials.from_generated_secret("meridian"), database_name="meridian",
            allocated_storage=20, max_allocated_storage=50, storage_encrypted=True, multi_az=False,
            backup_retention=Duration.days(7), deletion_protection=True, removal_policy=RemovalPolicy.SNAPSHOT,
            publicly_accessible=False, auto_minor_version_upgrade=True)

        gen = lambda n, length=48: sm.Secret(self, n, generate_secret_string=sm.SecretStringGenerator(
            password_length=length, exclude_punctuation=True))
        session_secret, ingest_token = gen("SessionSecret"), gen("IngestToken")
        origin_verify = Fn.select(2, Fn.split("/", self.stack_id))      # stack GUID; CloudFront → ALB shared header

        # ---- Cognito (sign-in; groups = Meridian roles)
        pool = cognito.UserPool(
            self, "Users", user_pool_name="meridian-users", self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True), auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(fullname=cognito.StandardAttribute(required=False, mutable=True)),
            mfa=cognito.Mfa.OPTIONAL, mfa_second_factor=cognito.MfaSecondFactor(sms=False, otp=True),
            password_policy=cognito.PasswordPolicy(min_length=12, require_symbols=True),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY, feature_plan=cognito.FeaturePlan.ESSENTIALS,
            removal_policy=RemovalPolicy.RETAIN)
        for r in ROLES:
            cognito.CfnUserPoolGroup(self, f"Group-{r}", user_pool_id=pool.user_pool_id, group_name=r,
                                     description=f"Meridian role: {r}")
        domain = pool.add_domain("Domain", cognito_domain=cognito.CognitoDomainOptions(
            domain_prefix=Fn.join("-", ["meridian", self.account])),
            managed_login_version=cognito.ManagedLoginVersion.CLASSIC_HOSTED_UI)

        # ---- app service (ALB + Fargate)
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc, container_insights_v2=ecs.ContainerInsights.DISABLED)
        # Internal load balancer in private subnets; only CloudFront's origin-facing addresses may connect
        alb_sg = ec2.SecurityGroup(self, "AlbSg", vpc=vpc, allow_all_outbound=False,
                                   description="Meridian internal ALB: inbound only from CloudFront VPC origins")
        cf_prefix = ec2.PrefixList.from_lookup(self, "CloudFrontOriginFacing",
                                               prefix_list_name="com.amazonaws.global.cloudfront.origin-facing")
        alb_sg.add_ingress_rule(ec2.Peer.prefix_list(cf_prefix.prefix_list_id), ec2.Port.tcp(80),
                                "CloudFront origin-facing (VPC origin)")
        alb = elbv2.ApplicationLoadBalancer(self, "Alb", vpc=vpc, internet_facing=False, security_group=alb_sg,
                                            vpc_subnets=ec2.SubnetSelection(subnet_group_name="lb"),
                                            drop_invalid_header_fields=True)
        svc = ecsp.ApplicationLoadBalancedFargateService(
            self, "Web", cluster=cluster, cpu=512, memory_limit_mib=1024, desired_count=1,
            load_balancer=alb, public_load_balancer=False, open_listener=False, assign_public_ip=True,
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True), min_healthy_percent=100,
            task_image_options=ecsp.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset(REPO_ROOT, platform=cdk.aws_ecr_assets.Platform.LINUX_AMD64),
                container_port=8000,
                log_driver=ecs.LogDrivers.aws_logs(stream_prefix="meridian", log_retention=logs.RetentionDays.ONE_MONTH)))
        svc.target_group.configure_health_check(path="/healthz", healthy_http_codes="200")
        db.connections.allow_default_port_from(svc.service)

        dist = cf.Distribution(
            self, "Cdn", comment="Meridian",
            default_behavior=cf.BehaviorOptions(
                origin=origins.VpcOrigin.with_application_load_balancer(
                    alb, protocol_policy=cf.OriginProtocolPolicy.HTTP_ONLY,
                    custom_headers={"X-Origin-Verify": origin_verify}, read_timeout=Duration.seconds(60)),
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                cache_policy=cf.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER),
            price_class=cf.PriceClass.PRICE_CLASS_100)   # viewer TLS 1.2+ needs a custom domain + certificate (backlog S-1)
        base_url = Fn.join("", ["https://", dist.distribution_domain_name])

        client = pool.add_client(
            "WebClient", generate_secret=True,
            o_auth=cognito.OAuthSettings(flows=cognito.OAuthFlows(authorization_code_grant=True),
                                         scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
                                         callback_urls=[Fn.join("", [base_url, "/auth/callback"])],
                                         logout_urls=[Fn.join("", [base_url, "/signed-out"])]),
            supported_identity_providers=[cognito.UserPoolClientIdentityProvider.COGNITO],
            id_token_validity=Duration.hours(1), access_token_validity=Duration.hours(1),
            prevent_user_existence_errors=True)
        client_secret = sm.Secret(self, "CognitoClientSecret", secret_string_value=client.user_pool_client_secret)

        # Sign-in pages (Cognito hosted UI, classic) in the brand's colours, from config/brand.yaml. Applies to
        # every app client of the pool ("ALL"). CSS only: Cognito takes a logo image through its API, not here.
        signin_css = cognito.CfnUserPoolUICustomizationAttachment(self, "SignInBranding", user_pool_id=pool.user_pool_id,
                                                                  client_id="ALL", css=_cognito_css())
        signin_css.node.add_dependency(domain)                    # Cognito needs the domain before UI settings

        c = svc.task_definition.default_container
        for k, v in {"MERIDIAN_AUTH": "cognito", "APP_BASE_URL": base_url, "COGNITO_DOMAIN": domain.base_url(),
                     "COGNITO_CLIENT_ID": client.user_pool_client_id, "COGNITO_USER_POOL_ID": pool.user_pool_id,
                     "COGNITO_REGION": self.region, "ORIGIN_VERIFY": origin_verify, "MERIDIAN_LLM": "off"}.items():
            c.add_environment(k, v)
        # User access screen: the app manages users and groups in its own user pool only
        svc.task_definition.task_role.add_to_principal_policy(iam.PolicyStatement(
            actions=["cognito-idp:ListUsers", "cognito-idp:ListUsersInGroup", "cognito-idp:AdminListGroupsForUser",
                     "cognito-idp:AdminCreateUser", "cognito-idp:AdminAddUserToGroup",
                     "cognito-idp:AdminRemoveUserFromGroup", "cognito-idp:AdminUpdateUserAttributes",
                     "cognito-idp:AdminDisableUser", "cognito-idp:AdminEnableUser",
                     "cognito-idp:AdminUserGlobalSignOut", "cognito-idp:AdminDeleteUser"],
            resources=[pool.user_pool_arn]))
        c.add_secret("DB_SECRET", ecs.Secret.from_secrets_manager(db.secret))
        c.add_secret("SESSION_SECRET", ecs.Secret.from_secrets_manager(session_secret))
        c.add_secret("INGEST_TOKEN", ecs.Secret.from_secrets_manager(ingest_token))
        c.add_secret("COGNITO_CLIENT_SECRET", ecs.Secret.from_secrets_manager(client_secret))

        CfnOutput(self, "AppUrl", value=base_url)
        CfnOutput(self, "UserPoolId", value=pool.user_pool_id)
        CfnOutput(self, "IngestTokenSecretArn", value=ingest_token.secret_arn)
        CfnOutput(self, "SignInDomain", value=domain.base_url())


# Actions denied while the monthly budget is exceeded: creating or scaling up billable resources.
# Running resources keep running; AWS Budgets removes the policy at the start of the next month.
SPEND_BLOCK_ACTIONS = [
    "ec2:RunInstances", "ec2:StartInstances", "ec2:CreateNatGateway", "ec2:AllocateAddress",
    "ec2:CreateVolume", "ec2:CreateVpcEndpoint", "ec2:RequestSpotInstances", "ec2:CreateFleet",
    "rds:CreateDBInstance", "rds:CreateDBCluster", "rds:RestoreDBInstanceFromDBSnapshot",
    "rds:RestoreDBClusterFromSnapshot", "rds:StartDBInstance", "rds:StartDBCluster", "rds:ModifyDBInstance",
    "ecs:CreateService", "ecs:UpdateService", "ecs:RunTask", "ecs:StartTask",
    "elasticloadbalancing:CreateLoadBalancer", "lambda:CreateFunction", "eks:CreateCluster",
    "eks:CreateNodegroup", "sagemaker:Create*", "redshift:CreateCluster", "elasticache:Create*",
    "es:CreateDomain", "opensearch:CreateDomain", "cloudfront:CreateDistribution", "lightsail:Create*",
    "bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:CreateProvisionedModelThroughput",
    "autoscaling:CreateAutoScalingGroup", "autoscaling:UpdateAutoScalingGroup", "autoscaling:SetDesiredCapacity",
]


class CostGuardStack(Stack):
    """Monthly cost budget with email alerts and an automatic spend block at 100% of actual cost.

    Deployed in the app Region (the account's SCPs deny other Regions; Budgets is a global service). The block attaches a deny
    policy to the GitHub deploy role and to the CDK CloudFormation execution roles (CloudFormation,
    not the GitHub role, creates the resources during a CDK deploy).
    """

    def __init__(self, scope: Construct, cid: str, *, limit_usd: float, email: str, app_region: str, **kw):
        super().__init__(scope, cid, **kw)
        acct = self.account
        name = "meridian-cost-guard"
        targets = ["meridian-github-deploy"] + [
            f"cdk-hnb659fds-cfn-exec-role-{acct}-{r}" for r in sorted({app_region, self.region})]

        block = iam.ManagedPolicy(self, "SpendBlock", managed_policy_name="meridian-spend-block",
            description="Applied by AWS Budgets when Meridian monthly cost reaches 100 percent of budget",
            statements=[iam.PolicyStatement(sid="DenyNewSpend", effect=iam.Effect.DENY,
                                            actions=SPEND_BLOCK_ACTIONS, resources=["*"])])

        exec_role = iam.Role(self, "BudgetsActionRole", role_name="meridian-budgets-action",
            assumed_by=iam.ServicePrincipal("budgets.amazonaws.com"),
            description="Lets AWS Budgets attach and detach the Meridian spend block policy")
        exec_role.add_to_policy(iam.PolicyStatement(
            actions=["iam:AttachRolePolicy", "iam:DetachRolePolicy"],
            resources=[f"arn:aws:iam::{acct}:role/{t}" for t in targets],
            conditions={"ArnEquals": {"iam:PolicyARN": block.managed_policy_arn}}))

        sub = [budgets.CfnBudget.SubscriberProperty(subscription_type="EMAIL", address=email)]
        def note(kind, pct):
            return budgets.CfnBudget.NotificationWithSubscribersProperty(
                notification=budgets.CfnBudget.NotificationProperty(
                    notification_type=kind, comparison_operator="GREATER_THAN", threshold=pct,
                    threshold_type="PERCENTAGE"), subscribers=sub)

        budget = budgets.CfnBudget(self, "Budget", budget=budgets.CfnBudget.BudgetDataProperty(
            budget_name=name, budget_type="COST", time_unit="MONTHLY",
            budget_limit=budgets.CfnBudget.SpendProperty(amount=limit_usd, unit="USD")),
            notifications_with_subscribers=[note("ACTUAL", 80), note("FORECASTED", 100)])

        action = budgets.CfnBudgetsAction(self, "BlockAt100",
            budget_name=name, action_type="APPLY_IAM_POLICY", approval_model="AUTOMATIC",
            notification_type="ACTUAL", execution_role_arn=exec_role.role_arn,
            action_threshold=budgets.CfnBudgetsAction.ActionThresholdProperty(type="PERCENTAGE", value=100),
            definition=budgets.CfnBudgetsAction.DefinitionProperty(
                iam_action_definition=budgets.CfnBudgetsAction.IamActionDefinitionProperty(
                    policy_arn=block.managed_policy_arn, roles=targets)),
            subscribers=[budgets.CfnBudgetsAction.SubscriberProperty(type="EMAIL", address=email)])
        action.node.add_dependency(budget)
        action.node.add_dependency(exec_role)

        CfnOutput(self, "BudgetName", value=name)
        CfnOutput(self, "SpendBlockPolicyArn", value=block.managed_policy_arn)


app = cdk.App()
MeridianStack(app, "Meridian", env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"),
                                                   region=os.getenv("MERIDIAN_AWS_REGION", "us-east-2")),
              description="Meridian agentic portfolio management — hosted app")
cg = app.node.try_get_context("costGuard") or {}
if cg.get("email"):
    CostGuardStack(app, "MeridianCostGuard", limit_usd=float(cg.get("monthlyLimitUsd", 75)), email=cg["email"],
                   app_region=os.getenv("MERIDIAN_AWS_REGION", "us-east-2"),
                   env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"),
                                       region=os.getenv("MERIDIAN_AWS_REGION", "us-east-2")),
                   description="Meridian cost guard - monthly budget, alerts and spend block")
cdk.Tags.of(app).add("project", "meridian")
app.synth()
