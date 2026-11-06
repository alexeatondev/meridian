"""Board memo (CIO agent output for the investment committee / fund board)."""
from __future__ import annotations


def _p(x, d=1):
    return f"{x * 100:.{d}f}%"


def board_memo(run_id, as_of, mv, cma, vint, regime, co, synthetic, policy, model_label, snapshot_id) -> str:
    L = [f"# Board Memo — Meridian Target Retirement Series", "",
         f"**Run:** `{run_id}` · **As of:** {as_of} · **Policy:** `{policy.id}` · **Data snapshot:** `{snapshot_id}`  ",
         f"**Judgment engine:** {model_label} · **Compliance review:** {co['status']} · **Autonomy:** {regime.autonomy_level} (human approval required)", ""]
    if synthetic:
        L += ["> **SYNTHETIC DATA — SYSTEM TEST ONLY.** Figures below come from generated data, not market data. "
              "They are hypothetical, are not investment advice, and must not be used in any marketing material.", ""]
    L += ["## 1. Recommendation", "",
          "Hold each vintage within its tactical band around the strategic glide path, implementing the CIO agent's ensemble "
          "allocations below once approved by the designated approvers. No vintage requires a glide-path (strategic) change.", "",
          "| Vintage | Yrs to target | Equity neutral | Equity proposed | Tilt | E[r] | Vol | TE vs glide path | Compliance |",
          "|---|---|---|---|---|---|---|---|---|"]
    for v, d in vint.items():
        L.append(f"| {v} | {d['years_to_target']:.1f} | {_p(d['equity_neutral'])} | {_p(d['equity_final'])} | "
                 f"{(d['equity_final'] - d['equity_neutral']) * 100:+.1f}pp | {_p(d['exp_ret'])} | {_p(d['vol'])} | {_p(d['te'], 2)} | "
                 f"{d['compliance_summary']['overall']} |")
    L += ["", "## 2. Macro view", "", f"**Regime:** {mv['regime'].replace('_', '-')} (confidence {mv['confidence']}).  ",
          f"Scores — growth {mv['scores']['growth']}, inflation {mv['scores']['inflation']}, monetary policy {mv['scores']['monetary_policy']}, "
          f"financial conditions {mv['scores']['financial_conditions']}.  ", mv.get("rationale", ""), "",
          "## 3. Capital market assumptions (10-year, nominal)", "",
          "| Asset class | Historical | Equilibrium | Valuation/Yield | Auto-blend | Judge | Judge − blend | Vol |", "|---|---|---|---|---|---|---|---|"]
    for c in cma:
        vy = c.get("building_block", c.get("yield_based"))
        L.append(f"| {c['name']} | {_p(c['historical'])} | {_p(c['equilibrium'])} | {_p(vy) if vy is not None else '—'} | "
                 f"{_p(c['auto_blend'])} | **{_p(c['judge'])}** | {c['judge_minus_blend'] * 100:+.1f}pp | {_p(c['vol'])} |")
    L += ["", "## 4. How the agents decided (per vintage)", ""]
    for v, d in vint.items():
        top = ", ".join(f"{r['method']} ({r['votes']:+d})" for r in d["ranking"][:3])
        bottom = d["ranking"][-1]
        L += [f"**{v}** — ensemble: `{d['ensemble']}`. Peer-vote leaders: {top}. Lowest ranked: {bottom['method']} ({bottom['votes']:+d}).  ",
              f"Effective N {d['eff_n']:.1f}; simulated max drawdown {_p(d['backtest']['max_drawdown'])} vs glide path {_p(d['backtest_neutral']['max_drawdown'])}.", ""]
    first_v, first = next(iter(vint.items()))
    L += ["## 5. Rationale and what would make this wrong", "",
          f"*CIO agent reasoning for the {first_v} vintage shown; every vintage's reasoning is in the Console and the decision ledger.*", "",
          first["rationale"], ""]
    L += [f"- {c}" for c in first["invalidation_conditions"]]
    L += ["", "## 6. Largest tactical positions (2050 vintage)", "", "| Asset class | Glide path | Proposed | Active |", "|---|---|---|---|"]
    d50 = vint.get(2050) or first
    act = sorted(((a, d50["final"][a] - d50["neutral"][a]) for a in d50["final"]), key=lambda x: -abs(x[1]))[:6]
    for a, x in act:
        L.append(f"| {a} | {_p(d50['neutral'][a])} | {_p(d50['final'][a])} | {x * 100:+.1f}pp |")
    L += ["", "## 7. Compliance statement", "",
          f"Deterministic rule engine evaluated every proposal against `{policy.id}` with entity regimes {regime.selected}. "
          f"Agentic Compliance Officer status: **{co['status']}** (DRAFT — requires human CCO sign-off).", ""]
    L += [f"- {f}" for f in co["findings"]]
    L += ["", "## 8. Rebalancing plan", "",
          "Quarterly calendar rebalance; off-cycle if any asset class drifts more than 2.0pp from target, or any invalidation "
          "condition triggers. Glide path steps monthly.", "",
          "## 9. Approvals required", ""]
    approvers = sorted({a for d in vint.values() for a in d["approvers"]})
    L += [f"- {a}: pending" for a in approvers]
    L += ["", "## 10. Disclosures", "",
          "Prepared by Meridian's autonomous agents operating at autonomy level L3 under the Investment Policy Statement. "
          "Expected returns are estimates, not guarantees. Backtests are hypothetical, may be affected by look-ahead bias, and "
          "do not reflect actual trading, fees or taxes. All agent reasoning and data lineage are retained in the decision ledger."]
    return "\n".join(L) + "\n"
