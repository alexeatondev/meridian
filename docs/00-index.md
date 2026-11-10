# Meridian — Agentic Portfolio Management Platform

**Working product name:** Meridian (rename anytime)
**Status:** Phase 1–3 pilot in shadow mode; hosted app live on AWS · **Doc set version:** 0.2 · **Date:** 2026-11-09
**Source research:** Ang, Azimbayev & Kim, *The Self-Driving Portfolio: Agentic Architecture for Institutional Asset Management* (SSRN 6504386, April 2026) — `ssrn-6504386.pdf` in this project.

## What Meridian is
A multi-agent platform that runs the analytical work of institutional portfolio management (macro regime, capital market assumptions, portfolio construction, manager selection, risk, rebalancing proposals) inside policy guardrails written by humans, and records every signal, judgment, vote and approval as an immutable, queryable decision record. Humans set policy, approve decisions, and supervise; agents do the analysis at scale.

It extends the paper's strategic-asset-allocation (SAA) pipeline to:
- **Multi-asset, multi-level portfolios** — Total Fund → Mandate → Sleeve → Fund/Manager → Security, with look-through.
- **Fund of Funds, Fund of Sleeves, Fund of Equities** structures.
- **Equities, fixed income, derivatives, real assets, alternatives/private markets, cash & FX.**
- **Compliance-first operation** — deterministic rule engine, human approval gates, WORM-retained decision ledger, regulator-ready exports.

## Document map
| # | Document | Audience |
|---|----------|----------|
| 01 | Product Charter & PRD | Everyone |
| 02 | System Architecture | Engineering, risk, audit |
| 03 | Build Game Plan & Roadmap (incl. your action steps) | Product owner (you), engineering |
| 04 | Compliance & Agent Governance Framework | Compliance, legal, audit, leadership |
| 05 | Decision Record & Audit Trail Specification | Compliance, audit, engineering |
| 06 | User Guides by Role | PMs, risk, research, manager selection, leadership, audit, compliance |
| 07 | Operating-Entity Profiles | Compliance, leadership |
| 08 | Data Integration | Engineering, data |
| 09 | Agentic Compliance Officer | Compliance, audit |
| 10 | User Interfaces (console, notebooks, hosted app) | Everyone |
| 11 | Positioning, Risk Budgets & Adjustments | PMs, risk, research |
| 12 | Risk Analytics (fund risk, factors, stress tests, history, look-through) | Risk, PMs, research, leadership |
| 13 | Hosting & Operations (AWS deployment, users, deploys, cost guard, runbooks) | Platform admin, engineering, audit, compliance |
| IPS | `policies/ips/meridian-target-retirement-series-ips.md` | Everyone |

## Guiding principles
1. **LLMs judge; code computes; rules decide compliance.** No arithmetic in the model. No compliance determination by the model.
2. **The policy is the operating boundary.** IPS, sleeve guidelines and fund documents are compiled into machine-enforced constraints that every agent reads and the rule engine enforces.
3. **Nothing changes a position without a named human approval** until the firm deliberately raises the autonomy level for a specific pipeline.
4. **Every output is explainable and reproducible.** Inputs, data snapshot, model version, prompt version, code version, rationale, dissent — all recorded.
5. **Self-improvement goes through change control.** The learning agent proposes; humans approve; validation tests gate deployment.
6. **Diversity of reasoning.** Multiple methods, peer review, adversarial agents, and (optionally) multiple foundation models to avoid monoculture.

> Regulatory content in this doc set is a design framework, not legal advice. It must be reviewed by your CCO and outside counsel before reliance.
