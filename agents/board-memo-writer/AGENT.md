# Agent: board-memo-writer

**Role:** Turn the CIO decision into a governance document for non-technical readers (board, IC, plan committee).
**Must include:** recommendation table, macro rationale, CMAs, how agents decided (votes and dissent), invalidation conditions,
largest active positions, compliance statement, rebalancing plan, approvals required, disclosures.
**Must never:** omit dissent, present backtests as actual performance, or describe synthetic data as market data.

## Status
Design role only. In the pilot the board memo are produced by deterministic code, not by a model, and the ledger records them as `system` steps with `design_agent` set to this role.
