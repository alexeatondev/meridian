# Skill: cma-judge (adapted from paper Exhibit 4)

Candidates: historical, equilibrium (reverse-optimized from glide-path weights), building_block (dividend yield + real growth + inflation + valuation change),
cape_yield (1/CAPE + inflation), yield_based (yield − expected loss, fixed income), regime_adjusted.

1. **Dispersion:** tight < 3pp, moderate 3–6pp, wide > 6pp. Wider dispersion → explain more.
2. **Regime:** late-cycle/recession → add weight to regime-adjusted and valuation methods; expansion → balanced blend.
3. **Valuation:** CAPE > 28 → valuation methods ≥ 60%; CAPE < 16 → historical + equilibrium ≥ 60%.
4. **Fixed income:** yield-based ≥ 60%.
5. Output weights over methods + rationale. **Constraint:** the final estimate must lie within [min, max] of candidates (enforced in code).
