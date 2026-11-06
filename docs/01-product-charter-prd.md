# 01 — Product Charter & Product Requirements (PRD)

**Version 0.1 · 2026-11-06 · Owner: Dev (Product Owner)**

## 1. Problem
Institutional portfolio management is bandwidth-bound, not data-bound (paper §1). A CIO oversees ~10–15 departments; committees meet monthly or quarterly; teams typically run one portfolio-construction method because comparing many is too slow; and the rationale behind decisions is scattered across decks, emails and memory — making audit and compliance review expensive.

## 2. Vision
Shift the investment team's role from analytical execution to **policy design, judgment and oversight**. Meridian runs dozens of parallel analyses, makes agents debate and vote, and turns each run into a board-ready memo plus a complete, regulator-ready evidence trail.

## 3. Goals and non-goals
**Goals (v1.0)**
- G1. Run an agentic SAA pipeline equivalent to the paper (macro → asset-class CMAs → covariance → 20+ PC methods → peer review & vote → CIO ensemble → board memo).
- G2. Model portfolios as a hierarchy (fund → sleeve → manager/fund → security) with look-through exposures and constraint inheritance.
- G3. Cover equities, fixed income, derivatives (futures, options, swaps, FX forwards), real assets, alternatives and cash.
- G4. Support FoF manager research and selection workflows.
- G5. Produce rebalancing **proposals** with pre-trade compliance checks, routed for human approval and export to the firm's OMS.
- G6. Full decision lineage: any number on any screen can be traced to its inputs, agent, model and approver.
- G7. Role-based workspaces and a conversational "Ask Meridian" interface constrained by permissions.

**Non-goals (v1.0)**
- Autonomous order execution without human approval.
- Retail advice or client-facing recommendations (would trigger Reg BI / suitability scope; out of scope until explicitly added).
- Replacing the books-of-record accounting system, custodian or OMS. Meridian integrates with them.
- High-frequency or intraday trading.

## 4. Users & personas
| Persona | Primary jobs | Key screens |
|---|---|---|
| Portfolio Manager | Review proposals, adjust parameters, approve/reject rebalances, own sleeve outcomes | Portfolio cockpit, proposal review, what-if |
| Risk Analytics | Validate CRO-agent reports, stress tests, limit monitoring, model challenge | Risk console, limit dashboard, stress lab |
| Research | Own CMA methods, skills, signals; review agent research outputs | Research lab, CMA workbench, signal library |
| Manager Selection | Due diligence, manager scoring, FoF construction, monitoring | Manager universe, DD workflow, look-through |
| Leadership / CIO / IC | Approve SAA, read board memos, set autonomy levels | Board memo, decision queue, KPI view |
| Compliance | Maintain rule library, review exceptions, run surveillance, exam response | Compliance center, rule editor, exception queue, exam export |
| Audit (internal/external) | Read-only reconstruction of any decision | Decision ledger explorer, replay, evidence export |
| Platform Admin / Model Risk | Agent registry, versions, change control, access | Agent registry, change requests, validation reports |

## 5. Core capabilities (epics)
| Epic | Description | Paper reference | Priority |
|---|---|---|---|
| E1 Policy-as-Code | IPS / sleeve guidelines / fund docs → versioned YAML policy → enforceable constraints | §4, §5.2 | P0 |
| E2 Data Platform | Point-in-time market, macro, holdings, reference data; snapshot IDs | §3.2 scripts | P0 |
| E3 Agent Runtime | Agent = description + scripts + skills + output contract; orchestration; retries | §3.2 | P0 |
| E4 SAA Pipeline | Macro, AC agents with CMA judge, covariance, PC agents, review, CIO | §3.1–3.6 | P0 |
| E5 Decision Ledger | Immutable decision records, lineage graph, WORM retention | §1 audit trails | P0 |
| E6 Compliance Engine | Deterministic pre/post-trade rules, exceptions, attestations | new | P0 |
| E7 Approvals & Autonomy | Approval workflows, autonomy level per pipeline, kill switch | §1, §5.2 | P0 |
| E8 Portfolio Hierarchy | Multi-level portfolio graph, look-through, constraint inheritance | new | P1 |
| E9 Asset-class Analytics | FI (duration, KRD, spread), derivatives (delta/notional, margin, counterparty), alts (desmoothing, pacing) | new | P1 |
| E10 Manager Selection / FoF | DD agents, returns/holdings-based style analysis, fee layering, liquidity terms | new | P1 |
| E11 Implementation | Rebalance proposals, trade lists, OMS export, TCA feedback | §3 implement | P1 |
| E12 Role Workspaces & Ask Meridian | UI + RBAC-scoped conversational access to ledger | new | P1 |
| E13 Meta-Agent Learning | Forecast-vs-realized feedback, proposed code/prompt changes through change control | §5.3 | P2 |
| E14 PC Researcher | Proposes new methods, sandboxed evaluation, registry promotion | §3.4 | P2 |
| E15 Agent Teams | Decompose macro/CRO into specialist sub-agents | §5.4 | P2 |

## 6. Key requirements
**Functional**
- FR-1 Every agent output conforms to a JSON schema (machine) + markdown narrative (human).
- FR-2 Every pipeline run binds to an immutable data snapshot and a policy version.
- FR-3 Hard constraints are evaluated by the rule engine; LLM agents may *explain* but never *override* a compliance result.
- FR-4 Any proposal that changes positions requires approval by a user with the right entitlement; four-eyes for material changes (threshold set by policy).
- FR-5 PC review supports randomized peer assignment with recorded seed, modified Borda voting, dissent capture and family-diversity constraint (paper §3.5).
- FR-6 CIO agent produces weights, rationale, invalidation conditions ("what would make this wrong"), and a board memo (paper §3.6).
- FR-7 Look-through aggregation across fund/sleeve/manager to security-level exposures, with staleness flags for estimated holdings.
- FR-8 Exam/audit export: a self-contained evidence pack for any decision or date range.
- FR-9 Kill switch per pipeline and global; halts runs and freezes pending proposals.

**Non-functional**
- NFR-1 Reproducibility: re-running a recorded decision with the same snapshot and versions reproduces deterministic outputs exactly and LLM outputs within recorded tolerance (LLM outputs are stored, not regenerated, for the official record).
- NFR-2 Retention: decision records retained per firm schedule (≥ 5 years baseline; see doc 04) on WORM storage.
- NFR-3 Security: least-privilege agents, sandboxed code execution, no agent write access to production policy or code.
- NFR-4 Availability: monthly/quarterly pipelines tolerate retries; daily monitoring jobs with alerting.
- NFR-5 Data privacy: client PII excluded from agent context by default (Reg S-P).

## 7. Success metrics
| Metric | Target (pilot) |
|---|---|
| SAA cycle time (data → board memo) | < 2 hours vs. weeks |
| PC methods evaluated per cycle | ≥ 20 |
| Decisions with complete lineage | 100% |
| Compliance hard-rule breaches reaching approval queue undetected | 0 |
| Audit evidence pack generation time | < 10 minutes |
| Parallel-run tracking vs. human process | Documented for ≥ 2 quarters before go-live |
| User trust (PM/IC survey) | ≥ 4/5 on "I understand why the system recommended this" |

## 8. Autonomy levels (adapted from paper footnote 2)
| Level | Meaning in Meridian | Default use |
|---|---|---|
| L0 | Humans do the work; Meridian records | Legacy import |
| L1 | Agents assist on request (research, summaries) | Research tools |
| L2 | Agents produce full analyses; humans decide and build proposals | Pilot start |
| L3 | Agents produce proposals inside policy; human approves each | **v1.0 target** |
| L4 | Agents act inside narrow bounds (e.g., drift rebalances < X bps, cash sweeps); humans review after the fact | Opt-in per pipeline, IC approval |
| L5 | Full autonomy | Not supported |

## 9. Risks (summary — see doc 04)
Lookahead bias in LLM backtests; LLM monoculture; automation complacency ("rubber-stamping"); agent overreach / scope creep; data licensing limits on LLM use; prompt injection via web data; misleading marketing of AI capability ("AI-washing").
