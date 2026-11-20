# 19 — Security and NIST Controls

**Version 0.1 · 2026-11-20 · Self-assessment of the hosted Meridian pilot against NIST SP 800-53 Rev 5 (Moderate baseline), with SP 800-63B (authentication), SP 800-218 (secure development) and the Cybersecurity Framework (CSF) 2.0. It is not an authorization to operate (ATO): no independent assessor has reviewed it, and the organization-level controls (policies, training, personnel, physical) belong to the firm.**

## 1. Scope, categorization and approach

| Item | Decision |
|---|---|
| System | Meridian hosted pilot: CloudFront → internal Application Load Balancer → ECS Fargate app → RDS PostgreSQL, Amazon Cognito sign-in, Secrets Manager, GitHub Actions for build and deploy (doc 14) |
| Data | Investment proposals, approvals and trade lists (books and records under SEC Rule 204-2 / 17a-4 style retention, doc 04), example positions, users' names and work emails. No client account numbers, SSNs or payment data |
| FIPS 199 category | **Moderate** (confidentiality Moderate: non-public investment decisions; integrity Moderate: regulated records; availability Low-Moderate: shadow mode, nothing executes). Baseline chosen by the product owner on 2026-11-20 |
| Standards | SP 800-53 Rev 5 Moderate controls; SP 800-63B AAL2 for sign-in; SP 800-218 SSDF for the build pipeline; CSF 2.0 for the summary (section 7) |
| Shared responsibility | Physical, environmental and hypervisor controls (PE, parts of SC, MA, MP) are inherited from AWS, whose services used here are in the FedRAMP Moderate/High authorizations. Cognito, CloudFront, ECS, RDS and Secrets Manager provide encryption, patching of managed layers and availability inside one Region |
| Cost rule | Product owner, 2026-11-20: **build only the free controls now**; everything that adds AWS cost is in the backlog (section 5) with time and cost estimates |
| Not done on purpose | **MFA is not yet required** (product owner, 2026-11-20). Recorded as open gap G-1 with its risk (section 4) |

Status words used below: **Met** (in place and tested), **Partly** (in place with a stated limit), **Gap** (not in place; backlog ID given), **Inherited** (AWS or GitHub provides it), **Org** (needs a firm policy, procedure or person; Meridian supports it).

## 2. Built on 2026-11-20

| Change | Controls | Evidence |
|---|---|---|
| **Inactivity timeout 30 minutes** (absolute session 8 hours unchanged); a "Still there?" warning 2 minutes before, with **Stay signed in**; background polling (My work) doesn't count as activity | AC-11, AC-12, IA-11; 800-63B AAL2 reauthentication | `auth.IDLE_TTL`, `test_idle_timeout_and_absolute_limit` |
| **Security event log**: successful and failed sign-ins, sign-outs, sessions ended (idle, expired, revoked), refused requests (403), CSRF failures, bad machine tokens, requests that bypassed CloudFront; who, when, IP address, method and path. Append-only in the database (triggers refuse UPDATE and DELETE) and copied as JSON to CloudWatch | AU-2, AU-3, AU-8, AU-9, AU-12, SI-4 | `security_events` table; `test_security_log_records_denials_and_is_restricted`, `test_security_log_is_append_only` |
| **Security log screen** for Admin, Audit and Compliance (User access → Security log): filter by event, person and period, CSV export | AU-6, AU-7 | SEC-1 |
| **Last sign-in and inactive-account flag** (no sign-in for 90 days) on User access | AC-2(3) (flag; disabling stays a human decision) | `test_users_show_last_signin_and_inactive_flag` |
| **Records carry the person's stable user ID** (Cognito `sub`) as well as name and email; **segregation of duties checks use the ID** when the record has one (previously the display name) | IA-2, AU-3, AU-10, AC-5 | `auth.same_person`, `test_same_person_prefers_the_user_id`, `test_records_carry_the_user_id` |
| **Authors stamped by the server**: a browser could previously send its own "by" on a tilt, exit or exclusion; now an unchanged entry keeps its recorded author and a new one is stamped with the signed-in person | AU-10, SI-10 | `test_settings_entries_cannot_claim_another_author` |
| **Security headers** on every response: Content-Security-Policy (same origin only, no plugins, no framing, forms only to the app and Cognito), HSTS (1 year), Permissions-Policy, Cross-Origin-Opener/Resource-Policy, nosniff, no-store, Referrer-Policy | SC-8, SC-18, SI-10, CM-7 | `test_security_headers_on_pages_and_api`, SEC-2 |
| **Load balancer made private**: internal ALB in private subnets, reached only through a CloudFront VPC origin; its security group admits only CloudFront's origin-facing addresses; invalid HTTP headers dropped. The CloudFront shared header check stays as a second layer | SC-7, SC-7(4), AC-4 | `infra/app.py`, deploy; SEC-3 |
| **Database connections require TLS** (`sslmode=require`; RDS PostgreSQL 16 also forces TLS on the server side by default) | SC-8, SC-8(1) | `store.db_url_from_env` |
| **CSRF token compared in constant time**; https-only fetches for public data | SC-23, SI-10 | `auth.check_csrf`, `data/public.py` |
| **Secure development checks in CI** (fail the build): pip-audit (known vulnerable Python packages), bandit (Python static analysis), gitleaks (secrets in the whole git history), Trivy (image and repository vulnerabilities and misconfigurations, high and critical), cfn-lint (IAM template); **CodeQL** weekly and on every pull request (Python and the pages' JavaScript); **Dependabot** weekly for pip, GitHub Actions and Docker; workflow token read-only by default | RA-5, SI-2, SA-11, SA-15, CM-3; SSDF PO.5, PW.4, PW.7, PW.8, RV.1 | `.github/workflows/ci.yml`, `codeql.yml`, `.github/dependabot.yml` |
| **Least-privilege roles prepared** for GitHub Actions: deploy (assumes the CDK roles only), user admin (Cognito user admin only), ingest (reads the ingest token only), each usable only from its own GitHub environment; and a narrowed CloudFormation execution policy (Meridian services only, IAM limited to Meridian-named roles, no IAM users or access keys). **Takes effect when an administrator deploys it once** (runbook R-1) | AC-6, AC-6(1), AC-6(9), AC-6(10), CM-5, IA-2 | `infra/security/github-oidc-roles.yaml` |

## 3. Control map, SP 800-53 Rev 5 Moderate

One row per family, naming the controls that matter for this system. "Backlog" refers to section 5.

| Family | Key controls | Status | How Meridian meets it / what is missing |
|---|---|---|---|
| **AC** Access control | AC-2, AC-2(3), AC-3, AC-5, AC-6, AC-7, AC-11, AC-12, AC-17 | **Partly** | Role-based access (8 workspaces) plus permissions (Investment Committee, CCO, Route manager, Approver) enforced on the server; every access change in an append-only access log with reason; access change signs the person out; segregation of duties by user ID; no self-approval; 30-minute idle and 8-hour absolute sessions; inactive accounts flagged at 90 days; Cognito locks out repeated failed passwords. **Gaps:** GitHub/AWS admin roles still broad until runbook R-1 is run (AC-6); portfolio-level entitlements (F-3, data visible to every signed-in role) |
| **AT** Awareness and training | AT-2, AT-3 | **Org** | In-app guide and info bubbles explain controls; security awareness and role training are firm programs |
| **AU** Audit and accountability | AU-2, AU-3, AU-6, AU-8, AU-9, AU-11, AU-12 | **Partly** | Hash-chained decision ledger (doc 05), append-only access log and security log in the database, JSON copies in CloudWatch, UTC timestamps from AWS time sync, review screen and CSV. **Gaps:** CloudWatch retention 1 month (backlog S-7: 1 year+); no WORM copy (S-8); no alert when logging fails (AU-5, S-4); CloudTrail trail for AWS API activity not confirmed (S-3) |
| **CA** Assessment, authorization, monitoring | CA-2, CA-5, CA-6, CA-7 | **Partly** | This document is the self-assessment and plan of action (sections 4-5); automated tests (235) and CI security checks run on every change. **Gaps:** independent assessment and a named authorizing official (Org); continuous monitoring service (Security Hub, S-5) |
| **CM** Configuration management | CM-2, CM-3, CM-5, CM-6, CM-7, CM-8 | **Met** for the app, **Partly** for AWS | Everything is code (CDK, workflows, policy-as-code); changes go through pull requests, CI and a recorded deploy; container runs as a non-root user; only required ports open; inventory = CDK stack. **Gap:** AWS Config rules to detect drift (S-5); branch protection on `main` requiring CI (G-4, a GitHub setting) |
| **CP** Contingency planning | CP-2, CP-4, CP-9, CP-10 | **Partly** | RDS automated backups 7 days, deletion protection, snapshot on removal; app and infrastructure rebuildable from git; ledger verifiable. **Gaps:** 35-day backups (S-9), single-AZ database and single task (S-10, S-11), no restore test yet (procedure in section 6) |
| **IA** Identification and authentication | IA-2, IA-2(1), IA-2(2), IA-2(8), IA-5, IA-5(1), IA-8, IA-11 | **Partly** | Cognito OAuth 2.0 authorization-code flow with client secret, JWT verified against the pool's keys, 12-character passwords with symbols, email-only recovery, no self sign-up, unique accounts, machine access by a secret token in Secrets Manager. **Gap G-1: MFA optional** (IA-2(1), IA-2(2); 800-63B AAL2 requires it); compromised-password checks need Cognito Plus (S-12) |
| **IR** Incident response | IR-4, IR-5, IR-6, IR-8 | **Org / Partly** | Security log and exceptions workflow support handling; outline procedure in section 6. **Gap:** firm incident response plan and contacts; GuardDuty detection (S-5) |
| **MA** Maintenance | MA-2, MA-4 | **Inherited** | No servers to maintain; AWS patches managed layers; RDS minor versions auto-upgrade; container rebuilt on every deploy |
| **MP** Media protection | MP-6 | **Inherited** | AWS media sanitization; no removable media |
| **PE** Physical and environmental | PE-* | **Inherited** | AWS data centers |
| **PL** Planning | PL-2, PL-4, PL-8 | **Partly** | This document and doc 14 describe the system and its security architecture; rules of behavior shown at sign-in ("For authorized users only..."). **Org:** signed rules of behavior |
| **PM / PS** Program, personnel | PS-3, PS-4, PS-5 | **Org** | Meridian supports joiner/mover/leaver with User access (disable, delete, access log, sign-out on change); screening and termination procedures are the firm's |
| **PT** PII processing | PT-2, PT-3 | **Partly** | Only names and work emails of users; no client PII. Privacy notice is a firm item |
| **RA** Risk assessment | RA-3, RA-5 | **Met** | Risks in sections 4-5 and doc 03; vulnerability scanning on every change (pip-audit, Trivy, CodeQL, bandit, Dependabot) |
| **SA** System and services acquisition | SA-3, SA-8, SA-9, SA-11, SA-15 | **Met** | SSDF practices in section 2; security by design (shadow mode, policy-as-code, ledger); third-party services documented (AWS, GitHub, Anthropic API for agent runs, public data sources) |
| **SC** System and communications protection | SC-7, SC-8, SC-12, SC-13, SC-23, SC-28 | **Partly** | HTTPS for viewers; private load balancer (VPC origin); database in isolated subnets; TLS to the database; encryption at rest for RDS, Secrets Manager, logs (AWS-managed keys); signed session cookies (HttpOnly, Secure, SameSite=Lax). **Gaps:** viewer TLS 1.0/1.1 still accepted because the default `*.cloudfront.net` certificate can't set a minimum (S-1, custom domain); CloudFront to load balancer is HTTP inside the AWS network (S-1); no WAF or rate limiting (S-2); app tasks have public IPs for outbound calls (inbound only from the load balancer; S-13); AWS-managed rather than customer-managed keys (S-14) |
| **SI** System and information integrity | SI-2, SI-3, SI-4, SI-7, SI-10, SI-11 | **Partly** | Dependency and image scanning with Dependabot fixes; input validation on every API; errors don't leak stack traces; ledger integrity verified on every page load. **Gaps:** runtime threat detection (GuardDuty, S-5); CSP still allows inline scripts (S-15) |
| **SR** Supply chain | SR-3, SR-11 | **Partly** | Dependencies pinned by minimum version and scanned; Dependabot. **Gap:** GitHub Actions pinned by tag, not commit SHA (G-5); no SBOM published (S-16) |

## 4. Open gaps and accepted risks

| ID | Gap | Risk | Owner and next step |
|---|---|---|---|
| **G-1** | **MFA not required** (IA-2(1), IA-2(2); 800-63B AAL2) | A stolen or guessed password gives full access to that person's role, including approvals and user administration | Deferred by the product owner on 2026-11-20 while only test users sign in. **Must be closed before any real user or real data**; effort and cost in S-0 (free). Until then: strong passwords, idle timeout, security log review |
| **G-2** | Broad AWS deploy permissions until runbook R-1 is run | A compromised workflow on `main` could change any AWS resource | Administrator runs R-1 (about 1 hour) |
| **G-3** | Portfolio-level entitlements (F-3) | Every signed-in role can read all run data | Waits on the product owner's entitlement design |
| **G-4** | Branch protection on `main` (require pull request and passing CI; block force-push) | A direct push could deploy unreviewed code | GitHub setting, 10 minutes, free; product owner |
| **G-5** | Actions pinned by tag | A compromised action tag could run in CI with AWS access | Pin to commit SHAs (2 hours, free; Dependabot keeps them current) |
| **G-6** | One person holds every role in testing | Segregation of duties exercised only with test logins | Real users per role at UAT |

## 5. Backlog: controls that cost money (or larger free items), with estimates

Estimates are for this pilot's size (a few users, one small database, one task), us-east-2 list prices in November 2026, and Claude doing the build with you approving. One-time effort excludes your review time. Monthly cost is the added AWS bill.

| ID | Item | Controls | One-time effort | Monthly cost | Priority |
|---|---|---|---|---|---|
| **S-0** | **Require MFA** for all users (Cognito MFA = ON, authenticator app) and refuse approvals from sessions without MFA; enrolment help in the guide | IA-2(1), IA-2(2), AAL2 | 0.5 day | $0 | **Before real users** |
| **S-1** | **Custom domain and certificate** (e.g. `meridian.<firm>.com`): viewer TLS 1.2+ only, HTTPS from CloudFront to the load balancer, new Cognito callback URLs | SC-8, SC-13, SC-23 | 0.5-1 day (plus DNS approval) | ~$1.50 (domain ~$15/yr, Route 53 $0.50) | High |
| **S-2** | **AWS WAF** on CloudFront: rate limiting per IP, AWS managed rules (common, known bad inputs, IP reputation) | SC-5, SC-7, SI-4 | 0.5 day | ~$9-12 | High |
| **S-3** | **CloudTrail** trail (management events) to an S3 bucket with lifecycle, if the organization trail doesn't already cover the account | AU-2, AU-12 | 2 hours | ~$0-1 (first trail free; S3 cents) | High |
| **S-4** | **CloudWatch alarms** emailed to the admin: 5xx rate, unhealthy target, database CPU/storage, failed sign-in spike, security-log write failures | AU-5, SI-4, IR-5 | 0.5 day | ~$1 | High |
| **S-5** | **GuardDuty** (threat detection) and **Security Hub** with the NIST SP 800-53 Rev 5 standard (needs AWS Config) | SI-4, CA-7, CM-6, RA-5 | 0.5 day | ~$10-20 (30-day free trials) | Medium |
| **S-6** | **VPC flow logs** to CloudWatch (rejected traffic only) | AU-12, SI-4 | 1 hour | ~$1-2 | Medium |
| **S-7** | **Log retention 1 year** in CloudWatch, then archive (records retention per doc 04) | AU-11 | 1 hour | <$1 | Medium |
| **S-8** | **WORM evidence copy** (S3 Object Lock, compliance mode) of the ledger, access and security logs, and a daily ledger hash anchor | AU-9(2), AU-10, records rules | 1-2 days | ~$1 | Before production |
| **S-9** | **35-day database backups** and a weekly snapshot copy | CP-9 | 1 hour | ~$1-2 | Medium |
| **S-10** | **Multi-AZ database** | CP-10, SC-5 | 1 hour (+ brief failover) | ~$13 | Before production |
| **S-11** | **Two app tasks across availability zones** | CP-10 | 1 hour | ~$18 | Before production |
| **S-12** | **Cognito Plus**: compromised-credential checks, adaptive authentication, sign-in event export | IA-5(1), AC-7, SI-4 | 2 hours | ~$1 at <50 users | Medium |
| **S-13** | **No public IPs on app tasks**: VPC endpoints (ECR, Secrets Manager, Logs, Cognito via NAT) or a NAT gateway | SC-7 | 0.5 day | ~$35-40 | Before production |
| **S-14** | **Customer-managed KMS keys** for RDS, Secrets Manager and logs (key rotation and access under your control); RDS needs a snapshot restore | SC-12, SC-28(1) | 1 day + ~30 min downtime | ~$3 | Before production |
| **S-15** | **Strict CSP with nonces** (no inline scripts or `onclick` handlers) | SI-10, SC-18 | 2-3 days | $0 | Medium |
| **S-16** | **SBOM** (CycloneDX) published with each image, and **image signing** | SR-3, SR-4, SSDF PS.3 | 0.5 day | $0 | Medium |
| **S-17** | **Secret rotation** for the session key and ingest token (Secrets Manager rotation Lambda), and RDS credentials | IA-5, SC-12 | 1 day | <$1 | Medium |
| **S-18** | **Database TLS with certificate check** (`verify-full` with the RDS CA bundle in the image) | SC-8, SC-23 | 2 hours | $0 | Medium |
| **S-19** | **Independent penetration test and assessment** | CA-2, CA-8 | 2-3 weeks (external) | one-time ~$5,000-15,000 | Before production |
| **S-20** | **Restore test** each quarter (restore a snapshot to a temporary instance, verify the ledger, delete it) | CP-4 | 2 hours each | ~$1 per test | Before production |

**Totals.** High priority (S-1 to S-4): about 2 days of work and about $11-16 a month. Everything except the penetration test: about 12-15 days and about $95-115 a month at today's size, most of it the availability and network items (S-10, S-11, S-13).

## 6. Procedures

**Runbook R-1: switch GitHub Actions to least-privilege roles** (an administrator, about 1 hour, no cost)
1. In AWS CloudShell (us-east-2) as an administrator: get the repository (`git clone https://github.com/alexeatondev/meridian`), then
   `aws cloudformation deploy --stack-name MeridianGitHubRoles --template-file meridian/infra/security/github-oidc-roles.yaml --capabilities CAPABILITY_NAMED_IAM`.
2. In GitHub → Settings → Environments, open **production**, **user-admin** and **ingest** (create them if they aren't there) and set **Deployment branches** to `main` only. Optionally add yourself as a required reviewer on **production** and **user-admin**.
3. In GitHub → Settings → Variables, set `AWS_DEPLOY_ROLE_ARN`, `AWS_USERS_ROLE_ARN` and `AWS_INGEST_ROLE_ARN` to the stack outputs. Then tell Claude: the workflows are switched to their environments and roles in one pull request, and the `cdk bootstrap` step comes out of the deploy workflow.
4. Narrow CloudFormation: in CloudShell run `npx aws-cdk@2 bootstrap aws://950088505912/us-east-2 --cloudformation-execution-policies <CfnExecutionPolicyArn output>`, then run the deploy workflow once to prove it works. If a deploy fails for a missing permission, add that one action to the policy; to roll back, run the same bootstrap command with `arn:aws:iam::aws:policy/AdministratorAccess`.
5. When a deploy, a user change and a prices run have all worked with the new roles, delete the old `meridian-github-deploy` role (and point the cost guard's spend block at `meridian-gh-deploy`, in the same pull request as step 3).

**Weekly security log review** (Admin or Compliance, 10 minutes; AU-6): User access → Security log → last 7 days. Look at failed sign-ins (several for one person, or from unusual addresses), refused requests, CSRF failures, bad tokens and direct hits on the load balancer. Record the review as a note on an exception if anything needs action.

**Monthly access review** (Admin with Compliance; AC-2): User access → Access review CSV; disable accounts flagged **Inactive** unless the owner confirms they're needed; check permissions (CCO is the named CCO only, Approver only where intended).

**Quarterly restore test** (CP-4; S-20) once production backups are set.

**Incident outline** (IR-4, until the firm's plan applies): 1. Contain: disable the user in User access (signs them out at once) or rotate the ingest token. 2. Preserve: download the security log and evidence pack (CSV/JSON); don't delete anything (the logs are append-only). 3. Assess with Compliance whether regulatory notification applies (e.g. SEC Regulation S-P incident notice). 4. Fix, then record the incident and decision as an exception.

## 7. CSF 2.0 summary

| Function | Where Meridian stands |
|---|---|
| **Govern (GV)** | Policy-as-code IPS, roles and permissions, this document; firm policies, risk appetite and named officials are Org items |
| **Identify (ID)** | Asset inventory is the CDK stack and repository; risk register = sections 4-5 and doc 03; vulnerability scanning on every change |
| **Protect (PR)** | Role-based access, segregation of duties, sessions with idle timeout, encryption in transit and at rest, private load balancer and database, secure development checks. MFA open (G-1) |
| **Detect (DE)** | Security event log with review screen and CloudWatch copy; CI scanning. Runtime detection (GuardDuty, WAF, alarms) in backlog S-2, S-4, S-5 |
| **Respond (RS)** | Exceptions workflow, disable-and-sign-out, append-only evidence; incident outline above |
| **Recover (RC)** | Database backups, infrastructure and app rebuilt from git, ledger verification. Multi-AZ and restore tests in backlog |
