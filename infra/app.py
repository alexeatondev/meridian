#!/usr/bin/env python3
"""Meridian on AWS (CDK). One stack, region us-east-2 by default.

  CloudFront (HTTPS) ──X-Origin-Verify──▶ ALB ──▶ ECS Fargate (Meridian app container)
                                                     │                │
                              Cognito user pool ◀────┘                └──▶ RDS PostgreSQL (isolated subnets)
  Secrets Manager: DB credentials, session key, ingest token, Cognito client secret.
  No NAT gateway (cost): tasks run in public subnets with a public IP; the database has no internet route.
"""
import os

import aws_cdk as cdk
from aws_cdk import (CfnOutput, Duration, Fn, RemovalPolicy, Stack, aws_cloudfront as cf,
                     aws_cloudfront_origins as origins, aws_cognito as cognito, aws_ec2 as ec2, aws_ecs as ecs,
                     aws_ecs_patterns as ecsp, aws_logs as logs, aws_rds as rds, aws_secretsmanager as sm)
from constructs import Construct

ROLES = ["portfolio_manager", "risk", "analyst", "manager_selection", "leadership", "compliance", "audit", "admin"]
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class MeridianStack(Stack):
    def __init__(self, scope: Construct, cid: str, **kw):
        super().__init__(scope, cid, **kw)

        vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=0, subnet_configuration=[
            ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
            ec2.SubnetConfiguration(name="db", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24)])

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
        svc = ecsp.ApplicationLoadBalancedFargateService(
            self, "Web", cluster=cluster, cpu=512, memory_limit_mib=1024, desired_count=1,
            public_load_balancer=True, assign_public_ip=True,
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
                origin=origins.LoadBalancerV2Origin(svc.load_balancer, protocol_policy=cf.OriginProtocolPolicy.HTTP_ONLY,
                                                    custom_headers={"X-Origin-Verify": origin_verify},
                                                    read_timeout=Duration.seconds(60)),
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                cache_policy=cf.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER),
            price_class=cf.PriceClass.PRICE_CLASS_100)
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

        c = svc.task_definition.default_container
        for k, v in {"MERIDIAN_AUTH": "cognito", "APP_BASE_URL": base_url, "COGNITO_DOMAIN": domain.base_url(),
                     "COGNITO_CLIENT_ID": client.user_pool_client_id, "COGNITO_USER_POOL_ID": pool.user_pool_id,
                     "COGNITO_REGION": self.region, "ORIGIN_VERIFY": origin_verify, "MERIDIAN_LLM": "off"}.items():
            c.add_environment(k, v)
        c.add_secret("DB_SECRET", ecs.Secret.from_secrets_manager(db.secret))
        c.add_secret("SESSION_SECRET", ecs.Secret.from_secrets_manager(session_secret))
        c.add_secret("INGEST_TOKEN", ecs.Secret.from_secrets_manager(ingest_token))
        c.add_secret("COGNITO_CLIENT_SECRET", ecs.Secret.from_secrets_manager(client_secret))

        CfnOutput(self, "AppUrl", value=base_url)
        CfnOutput(self, "UserPoolId", value=pool.user_pool_id)
        CfnOutput(self, "IngestTokenSecretArn", value=ingest_token.secret_arn)
        CfnOutput(self, "SignInDomain", value=domain.base_url())


app = cdk.App()
MeridianStack(app, "Meridian", env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"),
                                                   region=os.getenv("MERIDIAN_AWS_REGION", "us-east-2")),
              description="Meridian agentic portfolio management — hosted app")
cdk.Tags.of(app).add("project", "meridian")
app.synth()
