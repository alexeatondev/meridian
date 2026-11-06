# 04 — Compliance & Agent Governance Framework

**Version 0.1 · 2026-11-06 · Owner: CCO (to be assigned) · Status: DRAFT for counsel review**

> This framework maps Meridian's controls to common U.S. regulatory obligations. It is not legal advice. Applicability depends on the operating entity's registrations and client types; the CCO and outside counsel must confirm scope, citations and retention periods before adoption.

## 1. Regulatory posture
There is currently no SEC rule written specifically for AI in investment management. The SEC's 2023 proposal on conflicts from predictive data analytics was formally withdrawn on June 12, 2025 along with 13 other proposals; any future AI rule would need a new proposal. Existing, technology-neutral obligations therefore apply in full: fiduciary duty, compliance programs, books and records, supervision, marketing and disclosure. FINRA's 2026 Annual Regulatory Oversight Report (December 2025) added a dedicated generative-AI section that names AI agents as an emerging risk — specifically autonomy without human validation, agents exceeding their intended scope or authority, auditability of multi-step reasoning, and data sensitivity — and expects firms to assess obligations and set up supervision **before** deployment.

Meridian's design response: humans approve; scope is constrained by policy-as-code and tool permissions; every step is logged; sensitive data is excluded from agent context.

## 2. Applicability matrix (confirm with counsel)
| Regime | Applies if Meridian is operated by… | Key obligations touched |
|---|---|---|
| Investment Advisers Act of 1940 | SEC-registered adviser (incl. OCIO) | Fiduciary duty; Rule 206(4)-7 compliance program & annual review; Rule 204-2 books & records; Rule 206(4)-1 marketing (incl. hypothetical performance); Form ADV disclosures; Rule 204A-1 code of ethics |
| Investment Company Act of 1940 | Adviser to registered funds | Rule 38a-1; diversification (§5(b)(1)); fund-of-funds limits (§12(d)(1), Rule 12d1-4); Rule 18f-4 derivatives (VaR limits, derivatives risk manager, limited-user exception); Rule 22e-4 liquidity; Rule 2a-5 valuation |
| Exchange Act / FINRA | Broker-dealer | Rules 17a-3/17a-4 records (WORM or audit-trail alternative); FINRA 3110/3120 supervision; 4511 records; 2210 communications; Reg BI / 2111 if recommendations to customers |
| CFTC / NFA | Futures, swaps, FX derivatives use | CPO/CTA registration or exemption/exclusion (e.g., Rule 4.5 for registered funds, 4.13(a)(3) for private funds); swap reporting via counterparties |
| Regulation S-P (as amended 2024) | SEC-registered advisers, BDs, funds | Safeguards, incident response, customer notification, service-provider oversight. Compliance dates: larger entities Dec 3, 2025; smaller entities June 3, 2026 — both now in force |
| Regulation S-ID | Covered accounts | Identity theft program (mainly client-facing) |
| ERISA | Plan assets | Prudence, prohibited transactions, documentation of process |
| Form PF / 13F / 13D-G / Sec. 16 | Private fund advisers; large equity holders | Reporting fed from Meridian holdings data |
| State / international (e.g., EU AI Act, UK FCA) | Non-U.S. clients or operations | Out of scope v1.0; assess before expansion |

## 3. Control framework

### 3.1 Governance & accountability
| Control | Description | Evidence |
|---|---|---|
| GOV-1 AI Governance Committee | CIO (chair), CCO, CRO, Head of Research, Model Risk owner, CTO. Approves autonomy levels, new pipelines, material agent changes | Charter, minutes in ledger |
| GOV-2 Named human owner per agent | Every agent has a business owner and technical owner in the registry | Agent registry |
| GOV-3 Autonomy level per pipeline | Set by GOV-1; default L3 (human approves each proposal) | Config + approval record |
| GOV-4 Kill switch | Global and per-pipeline; tested quarterly | Test logs |
| GOV-5 Annual review | Meridian included in Rule 206(4)-7 / 38a-1 annual compliance review | Review report |

### 3.2 Policy & investment-guideline compliance
| Control | Description |
|---|---|
| PC-1 Policy-as-code | IPS/guidelines/fund-doc limits encoded in versioned YAML; each rule cross-referenced to source document section |
| PC-2 Dual sign-off on policy changes | PM/Research author + Compliance approver; diff stored |
| PC-3 Deterministic rule engine | Hard limits evaluated in code only; LLM cannot override |
| PC-4 Pre-trade checks | Every trade list checked before approval queue; FAIL blocks |
| PC-5 Post-trade monitoring | Daily on custodian/accounting holdings; breaches → exception workflow with CCO notification |
| PC-6 Exceptions | Reason code, approver, expiry, remediation plan |
| PC-7 Rule testing | Each rule has unit tests (pass, boundary, fail) run on every release |

### 3.3 Supervision of agents (human-in-the-loop)
| Control | Description |
|---|---|
| SUP-1 Approval matrix | Who approves what, by materiality; four-eyes for material changes |
| SUP-2 Reasoned approvals | Approver must record a reason; "approve all" disallowed. Counters automation complacency (paper §5.1) |
| SUP-3 Dissent visibility | Minority and bottom-flagged views shown on approval screen and in board memo |
| SUP-4 Scope limits | Agents' tools and data permissions declared and enforced; out-of-scope actions blocked and logged |
| SUP-5 Challenge reviews | Quarterly sample of decisions re-reviewed by Risk/Compliance with written challenge |
| SUP-6 Escalation triggers | Policy-defined triggers (regime change, CMA invalidation, drawdown, limit proximity) force human review / off-cycle meeting |

### 3.4 Model risk management (agents, skills, analytics)
Aligned in spirit with bank model-risk guidance (e.g., SR 11-7) as industry best practice.
| Control | Description |
|---|---|
| MRM-1 Inventory | Every agent, skill, analytic method, and foundation-model version registered with tier (materiality) |
| MRM-2 Development standards | Documentation (AGENT.md/SKILL.md), assumptions, limitations, tests |
| MRM-3 Independent validation | Before production and annually for Tier 1; includes conceptual soundness, outcome analysis, benchmarking vs. deterministic baselines |
| MRM-4 Change control | All changes via pull request; owner + validator approval; validation suite must pass; production pins release tags |
| MRM-5 Meta-learner governance | Meta-learner may only *propose* changes as PRs with evidence; cannot deploy (departure from paper §5.3 by design) |
| MRM-6 New-method promotion | PC-researcher methods run in research environment; promotion requires ≥ N cycles of shadow results + validation |
| MRM-7 Foundation-model changes | Model version pinned; upgrades treated as material change with regression run on golden snapshots |
| MRM-8 Monoculture mitigation | Deterministic baselines always run; optional multi-model PC agents; disagreement metrics tracked |
| MRM-9 Lookahead-bias disclosure | Any backtest involving LLM judgment labeled as potentially contaminated; point-in-time models used where feasible |

### 3.5 Books & records and audit trail
| Control | Description |
|---|---|
| REC-1 Decision records | Every agent run, review, vote, approval, exception and policy change written to the ledger (doc 05) |
| REC-2 Immutability | Append-only, hash-chained; evidence packs on WORM storage (e.g., object lock in compliance mode) |
| REC-3 Retention | Per firm schedule; baseline ≥ 5 years with first 2 readily accessible (Advisers Act 204-2 baseline) — CCO to confirm; BD requirements per 17a-4 |
| REC-4 Reproducibility | Snapshot IDs + versions allow reconstruction; LLM outputs stored verbatim |
| REC-5 Exam readiness | Evidence-pack export by decision, portfolio, date range, or rule |
| REC-6 Communications | Board memos and any externally shared output archived; external use goes through marketing review |

### 3.6 Marketing & disclosure
| Control | Description |
|---|---|
| MKT-1 No AI-washing | Any statement about Meridian's AI capabilities must be accurate and substantiated; Compliance pre-approves |
| MKT-2 Hypothetical performance | Backtests and simulated results are hypothetical performance under the marketing rule — restricted audiences, policies, and required disclosures |
| MKT-3 Form ADV / offering docs | Describe use of AI/agents in investment process, material risks (model error, monoculture, data, lookahead) |
| MKT-4 Conflicts | Agents must not consider firm revenue/affiliated products unless policy explicitly allows and conflict is disclosed; rule-engine check for affiliated-fund selection in FoF |

### 3.7 Data protection & security
| Control | Description |
|---|---|
| SEC-1 PII exclusion | Client PII never enters agent context; portfolio IDs only |
| SEC-2 Vendor oversight | LLM providers and data vendors under service-provider oversight (Reg S-P); contractual no-training / retention terms |
| SEC-3 Least privilege | RBAC/ABAC for users; scoped tools for agents; sandboxed code execution |
| SEC-4 Prompt-injection defense | External/web text treated as untrusted data; isolation; output validation |
| SEC-5 Incident response | Covers AI-specific incidents (erroneous recommendation, data leakage, agent misuse) and Reg S-P notification |
| SEC-6 Data licensing | Vendor contracts checked for AI-use permissions before connection |

### 3.8 Trading-related (when Phase 6 is live)
Best-execution policy coverage for trade lists; allocation fairness across accounts; restricted list integration; personal-trading (code of ethics) not affected by agents; CFTC/NFA derivatives obligations; 18f-4 VaR checks for registered funds.

## 4. AI risk register (initial)
| ID | Risk | Likelihood | Impact | Key controls |
|---|---|---|---|---|
| R1 | Hallucinated fact or number drives a CMA | M | H | Scripts compute; judge bounded to [min,max] of methods; source tagging; CRO review |
| R2 | Agent recommends policy-violating portfolio | M | H | PC-3/PC-4 engine blocks |
| R3 | Rubber-stamp approvals | H | H | SUP-2, SUP-3, SUP-5 |
| R4 | Correlated errors across agents (single LLM) | M | M | MRM-8 |
| R5 | Lookahead bias inflates backtests | H | M | MRM-9, MKT-2 |
| R6 | Self-modifying agent degrades performance | M | H | MRM-4/5 |
| R7 | Prompt injection via web/news | M | H | SEC-4, no write tools |
| R8 | Client data leakage to model provider | L | H | SEC-1, SEC-2 |
| R9 | Licensed data used in breach of contract | M | M | SEC-6 |
| R10 | Overstated AI claims in marketing | M | H | MKT-1 |

## 5. Compliance user workflows (summary — see doc 06)
Rule library maintenance · exception queue · daily breach dashboard · approval audit · surveillance of agent scope violations · quarterly challenge sampling · annual review package · regulator exam export.

## 6. Required written policies & procedures (to draft in Phase 8)
1. AI & Agent Governance Policy
2. Model Risk Management Policy (agents & analytics)
3. Investment Guideline Compliance Procedures (Meridian addendum)
4. Books & Records / Retention Schedule addendum
5. Change Management Procedure
6. Data Governance & Vendor Data Licensing Procedure
7. Information Security & Incident Response addendum (Reg S-P)
8. Marketing Review Procedure addendum (AI claims, hypothetical performance)
9. Business Continuity: Meridian unavailable → manual fallback
