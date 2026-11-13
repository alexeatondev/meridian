# 14 — Hosting & Operations (AWS)

**Version 0.5 · 2026-11-13 · Audience: platform admin, engineering, audit, compliance**

How the hosted Meridian app is built, deployed and run, and what to do when something needs attention. Everything here describes what is actually deployed as of 2026-11-13 (last deploy: the Trading redesign with the New trade builder and impact view, PR #6). Planned changes are listed separately in §12.

## 1. What is running

| Item | Value |
|---|---|
| App URL | https://d3maw6l4k5cc0v.cloudfront.net (health check: `/healthz`) |
| AWS account | 950088505912 (member account in organization `o-gz7gwi4fzq`, advanced features activated 2026-11-09) |
| Region | us-east-2. An organization SCP denied this account's deploy role in us-east-1 (seen 2026-11-09); keep all regional resources in us-east-2. Global services (IAM, CloudFront, Budgets) work |
| Infrastructure as code | AWS CDK (Python), `infra/app.py`, two CloudFormation stacks: `Meridian` and `MeridianCostGuard` |
| Sign-in | Amazon Cognito user pool `us-east-2_OX4vbNaqC`, hosted sign-in at https://meridian-950088505912.auth.us-east-2.amazoncognito.com |
| Mode | Shadow mode: no money moves. Hosted app runs with `MERIDIAN_LLM=off`; live LLM judgment runs in the `agent-run` GitHub workflow |

## 2. Architecture

```
Browser ──HTTPS──▶ CloudFront ──(secret X-Origin-Verify header)──▶ Application Load Balancer
                                                                      │
                                                                      ▼
                                           ECS Fargate service "Web" (1 task, 0.5 vCPU, 1 GB)
                                           FastAPI app + Meridian Console, public subnet, no NAT
                                              │                     │                    │
                     Cognito user pool ◀──────┘                     │                    └──▶ CloudWatch Logs (30 days)
                     (sign-in, role groups)                         ▼
                                           RDS PostgreSQL (t4g.micro, 20–50 GB, encrypted,
                                           isolated subnets, no internet route)
Secrets Manager: database credentials, session key, ingest token, Cognito client secret.
```

| Component | Configuration | Why |
|---|---|---|
| CloudFront | Default `*.cloudfront.net` certificate, PriceClass 100 | HTTPS without a custom domain |
| Load balancer | Public; only accepts requests carrying CloudFront's secret origin header | Stops people bypassing CloudFront |
| ECS Fargate | 1 task; public IP; no NAT gateway | Lowest cost. The database is the only private tier |
| RDS PostgreSQL | Single-AZ, encrypted, 7-day automated backups, deletion protection on, final snapshot if the stack is removed | Runs, ledger and governance records, access log, exceptions, positions, change requests, policy overrides, cashflows, trade lists, trading settings, fund regulations, compliance obligations |
| Cognito | No self sign-up; admin-created users only; password ≥ 12 characters with symbols; MFA optional (authenticator app); account recovery by email; user pool retained if the stack is removed | Identity for all human users |
| Role groups | Workspaces: `portfolio_manager`, `risk`, `analyst`, `manager_selection`, `leadership`, `compliance`, `audit`, `admin`. Permissions: `investment_committee`, `chief_compliance_officer`, `route_manager` | The app's navigation and permissions follow these groups (doc 06, doc 11) |

## 3. How GitHub talks to AWS (no stored keys)

GitHub Actions signs in to AWS with OpenID Connect (OIDC): each workflow run gets a short-lived GitHub token, and AWS STS swaps it for temporary credentials for one IAM role (`AssumeRoleWithWebIdentity`). No AWS access keys exist anywhere.

| Item | Value |
|---|---|
| Identity provider | `arn:aws:iam::950088505912:oidc-provider/token.actions.githubusercontent.com`, audience `sts.amazonaws.com` |
| Role | `meridian-github-deploy` (repo variable `AWS_DEPLOY_ROLE_ARN`) |
| Trust condition | `sub` must equal `repo:alexeatondev@82978383/meridian@1448386556:ref:refs/heads/main` (GitHub's immutable owner/repo ID format), `aud` must equal `sts.amazonaws.com` |
| Permissions today | AWS-managed `AdministratorAccess` (to be narrowed, §12) |
| Session | 1 hour maximum |

Workflows that use the role:

| Workflow | Trigger | What it does in AWS |
|---|---|---|
| `deploy` | Push to `main` touching app/infra/config paths, or manual | Runs tests offline, then `cdk bootstrap` and `cdk deploy --all` |
| `manage-users` | Manual | Reads the `Meridian` stack outputs; creates, re-roles or disables Cognito users (fallback for the User access screen) |
| `agent-run` | Manual | Reads stack outputs and the ingest token; pulls approved positions, risk history and policy overrides from the app; runs the pipeline with live LLM judgment; publishes the run to the app |

`ci`, `data-refresh` (3rd of each month, 13:17 UTC) and `uat` (manual browser tests, doc 16) do not touch AWS.

## 4. Deploying

1. Merge or push to `main`. The `deploy` workflow starts automatically when files under `src/`, `infra/`, `config/`, `policies/`, `regimes/`, `agents/`, `skills/`, the `Dockerfile` or `pyproject.toml` change. It can also be started by hand (Actions → deploy → Run workflow).
2. The workflow fails before touching AWS if any test fails.
3. CDK builds the container image, updates both stacks, and prints the outputs (`AppUrl`, `UserPoolId`, `SignInDomain`, `BudgetName`, `SpendBlockPolicyArn`) in the run summary.
4. Check `https://d3maw6l4k5cc0v.cloudfront.net/healthz` returns `{"ok":true,...}`.

A full deploy takes about 10–15 minutes; an image-only change is faster.

**Rollback:** revert the offending commit on `main` and push; the deploy workflow redeploys the previous code. ECS keeps the old task running until the new one is healthy, so a failed deploy does not take the app down. The database is never dropped by a deploy (deletion protection).

## 5. Managing users

**In the app (recommended): User access screen** at `/admin` (admins land there; others with Admin, Audit or Compliance roles reach it from **User access** in the app bar).

| Tab | What it does | Who |
|---|---|---|
| Users | Add a user (sends the invitation email), edit name, tick workspaces, switch permissions on or off, resend an invitation, disable / enable, delete a disabled account (type the email to confirm) | Admin edits; Audit and Compliance read-only |
| Access review | Matrix of who holds which workspace and permission; download as CSV for periodic access reviews | Admin, Audit, Compliance |
| Access log | Every change: when, who, action, before, after, reason. The database refuses edits or deletions of these entries | Admin, Audit, Compliance |

Rules the server enforces: every change needs a reason (≥ 10 characters); an admin can't remove their own admin role, disable or delete themselves; at least one enabled admin always remains; accounts are deleted only after being disabled; separation-of-duties conflicts (e.g. PM plus Investment Committee, more than one CCO) are shown as warnings before saving. **Any change to a person's roles, permissions or status signs them out of Meridian immediately**, so it takes effect at once. The app's own AWS role may manage users and groups in this user pool only.

**Alternative: the `manage-users` workflow** (Actions → manage-users → Run workflow), useful if nobody can sign in as admin:

| Input | Values |
|---|---|
| `email` | The person's email; it is also their username |
| `name` | Full name shown in the app and recorded on decisions |
| `roles` | Comma-separated workspace roles from §2 and/or permissions: `investment_committee`, `chief_compliance_officer`, `route_manager` |
| `action` | `add` (create and email a temporary password), `set-roles` (replace all roles), `grant` / `revoke` (switch the listed roles or permissions on / off, leaving the rest), `disable` (block sign-in; history is kept) |

**Permissions** are switched on or off per person: `investment_committee` lets a Leadership user record committee decisions (glide-path and autonomy changes); `chief_compliance_officer` lets a Compliance user approve exceptions and policy changes and must only go to the named CCO. `route_manager` (Trade route manager) lets a person change where orders are routed on the Trading screen; every change is recorded (doc 17). Example: `grant` with roles `investment_committee`. Changes apply at the user's next sign-in. Neither permission gives screens on its own.

Cognito emails the temporary password; the person sets their own password at first sign-in (doc 06, "Signing in"). Nobody else ever sees it.

**Current users (2026-11-10):**

| User | Roles | Purpose |
|---|---|---|
| Alex Eaton (aeaton3252@gmail.com) | All eight | Product owner; full-access testing |
| RCTest User (aeaton52@hotmail.com) | `risk`, `compliance` | Second person for segregation-of-duties testing |
| UAT Committee Tester (aeaton3252+uat@gmail.com) | Disabled | Created and disabled during UAT round 1 (doc 16) |

Nobody holds `route_manager` yet; who should hold it is held by the product owner (doc 17 §9).

Segregation of duties: the app records each approval against the signed-in user and refuses a second decision on the same vintage by the same person in a different role; a requester can't approve their own risk-budget change. A real deployment should not give one person every role.

## 6. Running the agent pipeline

Actions → agent-run → Run workflow with:

| Input | Meaning |
|---|---|
| `as_of` | Month-end date |
| `model` | Dropdown: `config default` (the `default` in `config/models.yaml`, currently `claude-haiku-5-5`, the cheapest), or `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5` for this run only |
| `backend` | `sdk` (default): Claude Agent SDK agents with read-only tools. `messages`: single-shot calls, the original and cheapest path |
| `budget_usd` | Spend cap for the run on the `sdk` backend (default 3.00). When it is used up, remaining judgments use the deterministic policy |
| `publish` | Untick for a test run: nothing is sent to the app, but the run bundle is still attached to the workflow |

The run summary shows the cost against the budget, agent turns, tool calls and how many judgments each path made. The run:
1. Pulls approved positions, recorded risk history and policy overrides from the app (so the next run builds on human decisions).
2. Runs the target-date pipeline with live model judgment in 50 agent sessions (doc 02 §4a; key: GitHub secret `ANTHROPIC_API_KEY`; FRED data key: `FRED_API_KEY`).
3. Publishes the run bundle to the app (`/api/ingest`, authenticated with the ingest token) and uploads it as a workflow artifact.

First hosted run: `run_tds_20261031_48d07c` (as-of 2026-10-31), published 2026-11-09.

## 7. Cost guard

Stack `MeridianCostGuard` (in us-east-2; AWS Budgets is a global service).

| Item | Setting |
|---|---|
| Budget | `meridian-cost-guard`, $75 per month, all account costs |
| Email alerts (aeaton3252@gmail.com) | Actual spend > 80%; forecast spend > 100% |
| Automatic block | At actual spend > 100%, AWS Budgets attaches the deny policy `meridian-spend-block` to `meridian-github-deploy` and `cdk-hnb659fds-cfn-exec-role-950088505912-us-east-2` |
| What the block denies | Creating or scaling up billable resources: EC2 instances/volumes/NAT/EIPs, RDS create/start/modify, ECS create/update service and tasks, load balancers, Lambda, EKS, SageMaker, Redshift, ElastiCache, OpenSearch, CloudFront distributions, Lightsail, Bedrock invocation, Auto Scaling. Deploys fail while it is attached |
| What it does not do | Stop running resources. The app keeps running and keeps costing money |
| Reset | AWS removes the policy automatically at the start of the next month |
| Expected run-rate | About $60–65/month at list prices (Fargate ~$18, load balancer ~$17, RDS ~$14, public IPv4 ~$11, other ~$3); to be confirmed from Cost Explorer. Product owner's Cost Explorer check on 2026-11-10: about $1 spent so far |

**Lifting the block early** (e.g., to deploy a fix): deploys are blocked, so do this in the AWS console, where your own access is not affected. Go to Billing and Cost Management → Budgets → `meridian-cost-guard`, raise the amount if needed, then Actions → select the action → Reverse. CLI equivalent: `aws budgets execute-budget-action --account-id 950088505912 --budget-name meridian-cost-guard --action-id <id> --execution-type REVERSE_BUDGET_ACTION`. After the reversal, AWS does not re-evaluate the action until next month, so update `infra/cdk.json` to match the new amount on the next deploy.

The alert email address lives in `infra/cdk.json` (`costGuard.email`); the repository is private.

## 8. Monitoring & logs

| What | Where |
|---|---|
| App health | `GET /healthz`; ECS and the load balancer health-check the container and replace it if unhealthy |
| App logs | CloudWatch Logs, stream prefix `meridian`, kept 30 days |
| Deploy, user and run history | GitHub Actions run logs and summaries |
| Who did what in AWS | CloudTrail event history (90 days, on by default; no long-term trail configured) |
| Spend | Budget alerts above; Cost Explorer |

No CloudWatch alarms or uptime notifications exist yet (§12).

## 9. Backups & records

- RDS automated backups: 7 days, point-in-time restore. Deletion protection on.
- Decision ledger: hash-chained records in Postgres, plus each run bundle (including `ledger.jsonl`) as a GitHub workflow artifact.
- Decision records are append-only in the database itself: triggers refuse any UPDATE, DELETE or TRUNCATE on `ledger_records`, whoever issues them (added 2026-11-09, no cost).
- Retention applied by the pipeline: 6 years (strictest selected regime).
- **Gap against docs 04 (REC-2, REC-3) and 05 §3:** no WORM (S3 Object Lock) copy and no daily anchor of ledger hashes; backups kept 7 days. Deferred to production by the product owner because they add AWS cost (§12).

## 10. Secrets and keys

| Secret | Where | Rotation |
|---|---|---|
| `ANTHROPIC_API_KEY`, `FRED_API_KEY` | GitHub repository secrets | Reminder scheduled 2026-12-02 |
| Database credentials, session key, ingest token, Cognito client secret | AWS Secrets Manager, generated by CDK, injected into the container at start | Not yet rotated automatically |

Keys are never pasted into chat or committed. Secret values are entered by the product owner directly in GitHub or AWS.

## 11. Account guardrails and history

- 2026-11-06: account upgraded from the Free plan to the Paid plan. A managed SCP from the free-plan organization still denied `iam:CreateOpenIDConnectProvider`.
- 2026-11-09: organization advanced features activated by the product owner (irreversible; removes the free-plan spend limit, which the cost guard replaces). OIDC provider created; trust policy pinned to the immutable `sub` claim; first deploy (run 42677958733) succeeded. Support case 179424629200877 updated as resolved.
- Organization SCPs deny us-east-1 for this account; keep all regional resources in us-east-2.

## 12. Planned hardening (not yet done)

| Item | Why |
|---|---|
| Split `meridian-github-deploy` into deploy / users / run roles; require a GitHub environment in each trust policy | Least privilege; today any workflow on `main` has admin access |
| Narrow the deploy role to CDK's minimum and remove `cdk bootstrap` from the workflow | Bootstrap is the only step that needs broad access |
| Narrow `cdk-hnb659fds-cfn-exec-role` with a custom execution policy and permissions boundary | CloudFormation acts as this role during deploys; it has admin by default |
| Require MFA for approvers and admins | Approvals are regulated decisions |
| Record approvals against the Cognito user ID/email, not the display name | Unambiguous identity for audit and segregation of duties |
| WORM evidence store (S3 Object Lock), daily ledger anchor, longer backup retention (deferred to production: adds cost) | Docs 04 REC-2/REC-3 and 05 §3 |
| CloudWatch alarms (5xx, unhealthy target, database storage/CPU) emailed to the admin | Today an outage would go unnoticed |
| Schedule `agent-run` after the monthly data refresh, with a notification (held: runs stay ad hoc during development) | Operating loop |
| Update GitHub Actions still on Node 20 | Deprecation warnings |
| **Custom domain (held until production).** Register or pick a domain; request an ACM certificate for it in us-east-1 (CloudFront only uses us-east-1 certificates; the organization SCP denies the deploy role there, so request it in the console or add a narrow SCP exception); add it as an alternate domain name on the CloudFront distribution in the CDK stack; create the DNS alias (Route 53 hosted zone about $0.50/month, or your registrar's DNS); add the new address to the Cognito app client's callback and sign-out URLs; update docs and UAT links | A memorable address such as `meridian.<firm>.com`. A `*.cloudfront.net` name is assigned by AWS and can't be chosen |
