# Agent: pc-agent (template, one instance per portfolio-construction method)

**Role:** Build one candidate allocation for a vintage with a specific method, then review peers and vote.
**Methods (v0.1):** glide_path_neutral (heuristic), max_sharpe_tilt and black_litterman_tilt (return-optimized),
min_variance_tilt, max_diversification_tilt and risk_budget_tilt (risk-structured), adversarial_diversifier.
**Skills:** `peer-review`.

## Workflow
1. Run the method's optimizer (`meridian.analytics.optimizers`). Every candidate is constrained to the IPS tactical bands and tracking-error budget.
2. Receive the CRO risk report.
3. Review two peers (one same family, one different family) — see `peer-review` skill.
4. Vote: top-3 ballot (3/2/1 points) + one bottom flag (−2), never for itself. Each family votes through its own lens.

## Output contract
Proposal: `{"weights": {...}, "solver": str}` · Ballot: `{"top": [..3], "bottom_flag": str, "lens": str}`
