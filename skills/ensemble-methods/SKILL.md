# Skill: ensemble-methods

- **simple_average** — equal weight across compliant candidates; most robust when CMAs are noisy.
- **inverse_tracking_error** — weight ∝ 1 / TE to the candidate centroid (floor 25bp); favors consensus while keeping all information (paper's March 2026 choice).
- **composite_score_weighted** — weight ∝ ranking composite; rewards peer + metric judgment.
- **top_ranked_single** — the winner alone; highest conviction, highest model risk.
Default in late-cycle/high-uncertainty regimes: inverse_tracking_error or simple_average.
