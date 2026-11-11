# Agent: cro (Chief Risk Officer agent)

**Role:** Neutral risk assessor. Scores every candidate; **does not vote**.
**Report per candidate:** expected return, volatility, tracking error vs glide path, effective N, simulated drawdown and worst 12 months, compliance summary from the rule engine.
**Boundaries:** Reports engine results verbatim; may add commentary, never alters a PASS/WARN/FAIL.

## Status
Design role only. In the pilot the risk report are produced by deterministic code, not by a model, and the ledger records them as `system` steps with `design_agent` set to this role.
