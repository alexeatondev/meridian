# Meridian — Agentic Portfolio Management Platform

**Working product name:** Meridian (rename anytime)
**Status:** Pilot in shadow mode on real public data; hosted multi-user app live on AWS with role workspaces, User access, exceptions and a Trading screen (example positions) · **Doc set version:** 0.5 · **Date:** 2026-11-10
**Code:** https://github.com/alexeatondev/meridian
**App:** https://d3maw6l4k5cc0v.cloudfront.net (invited users only)
**Source research:** Ang, Azimbayev & Kim, *The Self-Driving Portfolio: Agentic Architecture for Institutional Asset Management* (SSRN 6504386, April 2026) — `ssrn-6504386.pdf` in this project.

## What Meridian is
A multi-agent platform that runs the analytical work of institutional portfolio management (macro regime, capital market assumptions, portfolio construction, manager selection, risk, rebalancing proposals) inside policy guardrails written by humans, and records every signal, judgment, vote and approval as an immutable, queryable decision record. Humans set policy, approve decisions, and supervise; agents do the analysis at scale.

It extends the paper's strategic-asset-allocation (SAA) pipeline to:
- **Multi-asset, multi-level portfolios** — Total Fund → Mandate → Sleeve → Fund/Manager → Security, with look-through.
- **Fund of Funds, Fund of Sleeves, Fund of Equities** structures.
- **Equities, fixed income, derivatives, real assets, alternatives/private markets, cash & FX.**
- **Compliance-first operation** — selectable entity regimes, deterministic rule engine, Agentic Compliance Officer, human approval gates, hash-chained decision ledger.

**Pilot portfolio:** Meridian Target Retirement Series — nine vintages 2030–2070, fund of funds across 13 asset classes, offered as target-date **mutual funds** (`MTRS-…`) and target-date **CITs** (`MTRT-…`). The CIT product line and all trading positions are example data for now.

## Document map
| # | Document | Audience |
|---|----------|----------|
| 01 | Product Charter & PRD | Everyone |
| 02 | System Architecture (design and as deployed) | Engineering, risk, audit |
| 03 | Build Game Plan & Roadmap (incl. status and next steps) | Product owner (you), engineering |
| 04 | Compliance & Agent Governance Framework | Compliance, legal, audit, leadership |
| 05 | Decision Record & Audit Trail Specification | Compliance, audit, engineering |
| 06 | User Guides by Role (incl. signing in) | PMs, risk, research, manager selection, leadership, audit, compliance |
| 07 | Investment Policy Statement — Target Retirement Series | Everyone |
| 08 | Operating-Entity Profiles (select one or many) | Compliance, leadership |
| 09 | Data Integration (Bloomberg, S&P, Moody's, Fitch, FactSet; direct or Snowflake) | Engineering, data |
| 10 | Agentic Compliance Officer | Compliance, audit |
| 11 | User Interfaces (console, notebooks, hosted app) | Everyone |
| 12 | Positioning, Risk Budgets & Adjustments | PMs, risk, research |
| 13 | Risk Analytics — fund risk, factors, stress tests, history, look-through & ticker search | Risk, PMs, research, leadership |
| 14 | Hosting & Operations — AWS deployment, users, deploys, cost guard, runbooks, planned hardening | Platform admin, engineering, audit, compliance |
| 15 | User Personas — each role's job, day, critical needs and what they need from Meridian; gap summary | Everyone, product |
| 16 | UAT Test Scripts — per-role scripts, automated browser tests, findings log | Product owner, testers, everyone |
| 17 | Cashflows, Trading & Implementation — requirements, decisions, what is built, phases, backlog | PMs, analysts, compliance, product |
| 18 | Fund Regulations & Obligations — US and international regulation tags, controls, tracked obligations | Compliance, PMs, audit, leadership |
| — | Sample run board memo | Leadership, IC |

The repository keeps the same documents under `docs/` **with the same numbers** (since 2026-11-10). Doc 07, the IPS, lives in the repository at `policies/ips/meridian-target-retirement-series-ips.md`; the sample board memo is a run output. User-guide screenshots are in `docs/img/guide/`, and an illustrated copy of doc 06 is at https://claude.ai/artifact/VtD4preFCa4NvY65h9sUTU.

## Guiding principles
1. **LLMs judge; code computes; rules decide compliance.** No arithmetic in the model. No compliance determination by the model.
2. **The policy is the operating boundary.** IPS, sleeve guidelines and fund documents are compiled into machine-enforced constraints that every agent reads and the rule engine enforces.
3. **Nothing changes a position without a named human approval** until the firm deliberately raises the autonomy level for a specific pipeline.
4. **Every output is explainable and reproducible.** Inputs, data snapshot, model version, prompt version, code version, rationale, dissent — all recorded.
5. **Self-improvement goes through change control.** The learning agent proposes; humans approve; validation tests gate deployment.
6. **Diversity of reasoning.** Multiple methods, peer review, adversarial agents, and (optionally) multiple foundation models to avoid monoculture.

> Regulatory content in this doc set is a design framework, not legal advice. It must be reviewed by a human CCO and outside counsel before reliance.
