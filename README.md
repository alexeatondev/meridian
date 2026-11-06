# Meridian — Agentic Portfolio Management

Meridian is a multi-agent platform for institutional portfolio management, modeled on Ang, Azimbayev & Kim, *The Self-Driving Portfolio* (SSRN 6504386, 2026). It extends the paper's design to multi-asset, multi-level portfolios and adds a governance layer:
- policy-as-code compiled from the Investment Policy Statement;
- a deterministic compliance engine that agents can't override;
- selectable regulatory regimes;
- an Agentic Compliance Officer;
- a hash-chained decision ledger;
- human approval gates.

**Pilot:** Meridian Target Retirement Series, nine vintages 2030–2070 (fund of funds, 13 asset classes).

## Quick start
```bash
pip install -e ".[dev]"
meridian entities show            # which regulatory regimes are active
meridian data                     # which data sources are plugged in
meridian run target-date --as-of 2026-10-31
pytest
meridian ui                       # build the role-based Meridian Console for the latest run
meridian approve runs/<run_id> --vintage 2050 --role portfolio_manager --name "Dev" --decision approve --reason "..."
jupyter lab notebooks/            # PM, research and compliance workbenches
```
Each run writes `runs/<run_id>/`: `board_memo.md`, `compliance_report.md`, `results.json`, `ledger.jsonl`, `snapshot/`.
A sample is committed in `examples/sample-run/`.

**LLM judgment:** set `ANTHROPIC_API_KEY` (and optionally `MERIDIAN_MODEL`) and `pip install -e ".[llm]"`. The judgment agents then use the model; numbers are still computed and bounded in code. Without a key, documented deterministic policies run, and every decision record says which path was used.

## Repository map
| Path | What |
|---|---|
| `policies/ips/` | Investment Policy Statement (human-readable) |
| `policies/target_date_series.yaml` | Policy-as-code: glide path, rules, approvals |
| `regimes/regimes.yaml` | Regulatory packs per entity type |
| `config/` | Entity profile, data sources & routing, investable universe |
| `agents/`, `skills/` | Agent descriptions and shared skills (paper §3.2 anatomy) |
| `src/meridian/data/` | Provider-agnostic data layer (Bloomberg, FactSet, S&P, Moody's, Fitch; direct or via Snowflake) |
| `src/meridian/analytics/` | Deterministic CMA, covariance, optimizers, risk |
| `src/meridian/compliance/` | Rule engine + Agentic Compliance Officer |
| `src/meridian/pipelines/` | Target-date pipeline, board memo |
| `src/meridian/ledger.py` | Immutable decision ledger |
| `schemas/` | Output contracts |
| `src/meridian/ui/` | Role-adaptive Meridian Console |
| `notebooks/` | Jupyter workbenches (PM, research, compliance/audit) |
| `docs/` | Product, architecture, compliance, user guides, interfaces |

## Status
Phase 1 pilot running on **synthetic data** in **shadow mode**. Not investment advice. Production is blocked until the required human roles (incl. a human CCO) are filled and the regime packs are reviewed by counsel.
