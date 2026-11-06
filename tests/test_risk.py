"""Risk analytics: holdings parsing, durations, risk model identities, stress tests, history, export."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from meridian.analytics import risk as RK
from meridian.data import DataRegistry, Request, to_wide_returns
from meridian.data.public import aggregate_holdings, parse_ishares_holdings
from meridian.policy import load_policy, load_universe

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def setup():
    pol, u = load_policy(), load_universe()
    ul = [u[a] for a in pol.assets]
    reg = DataRegistry.from_config()
    rets = to_wide_returns(reg.get(Request("returns.monthly", ul, start="1999-01-31", end="2026-10-31")).frame, pol.assets)
    cfg = RK.load_risk_config()
    chars = reg.get(Request("fund.characteristics", ul, as_of="2026-10-31")).frame
    ch = RK.characteristics(pol.assets, chars, None, cfg, u)
    return pol, u, rets, cfg, ch, RK.risk_model(rets, cfg, ch["eff_duration"])


def test_ishares_parser_aggregates_issuers_and_keeps_stock_and_bond_apart():
    df, as_of = parse_ishares_holdings((FIX / "ishares_bond_sample.csv").read_bytes())
    assert as_of == "2026-11-05" and len(df) == 7          # footer disclaimer excluded
    agg = aggregate_holdings(df)
    t = agg[agg["ticker"] == "T"].iloc[0]
    assert t["lines"] == 2 and abs(t["weight"] - 0.42) < 1e-9
    assert abs(t["duration"] - (0.30 * 5.8 + 0.12 * 16.1) / 0.42) < 1e-9   # weight-averaged
    eq = aggregate_holdings(parse_ishares_holdings((FIX / "ishares_equity_sample.csv").read_bytes())[0])
    assert abs(eq["weight"].sum() - 1.0) < 1e-9
    assert set(agg.loc[agg.ticker == "JPM", "security_id"]).isdisjoint(set(eq.loc[eq.ticker == "JPM", "security_id"]))


def test_durations_from_holdings_override_manual(setup):
    pol, u, rets, cfg, ch, m = setup
    g = aggregate_holdings(parse_ishares_holdings((FIX / "ishares_bond_sample.csv").read_bytes())[0])
    g["asset_id"], g["fund_ticker"], g["date"] = "us_core_bond", "AGG", "2026-11-05"
    chars = DataRegistry.from_config().get(Request("fund.characteristics", [u[a] for a in pol.assets], as_of="2026-10-31")).frame
    c2 = RK.characteristics(pol.assets, chars, g, cfg, u)
    assert abs(c2["eff_duration"]["us_core_bond"] - 6.544) < 1e-3
    assert abs(c2["spread_duration"]["us_core_bond"] - 2.872) < 1e-3       # Treasuries and cash excluded
    assert c2["source"]["us_core_bond"].startswith("holdings look-through")
    assert c2["eff_duration"]["us_large_cap"] == 0.0


def test_risk_model_identities(setup):
    pol, u, rets, cfg, ch, m = setup
    assert np.linalg.eigvalsh(m.resid).min() > -1e-10                       # specific risk never negative
    b = pol.neutral_weights(23.2)
    w = b.copy(); w[0] += 0.02; w[6] -= 0.02
    met = RK.fund_metrics(w, b, m, ch, cfg)
    assert abs(met["total_risk"] - np.sqrt(w @ m.cov @ w)) < 1e-12
    assert abs(met["var"] - 1.6448536 * met["total_risk"] / np.sqrt(12)) < 1e-6
    assert abs(met["active_var"] - 1.6448536 * met["active_risk"] / np.sqrt(12)) < 1e-6
    assert abs(met["rel_duration"] - (met["eff_duration"] - met["bench_eff_duration"])) < 1e-12
    assert 0 < met["diversification"] < 1
    bd = RK.risk_breakdown(w, b, m)
    assert abs(sum(r["pct_total_risk"] for r in bd["assets"]) - 1) < 1e-9
    assert abs(sum(r["pct_active_risk"] for r in bd["assets"]) - 1) < 1e-9
    fd = RK.factor_decomposition(w, b, m)
    for k in ("total", "active", "benchmark"):
        assert abs(sum(f["pct"] for f in fd[k]["factors"]) + fd[k]["specific"]["pct"] - 1) < 1e-9
    assert fd["total"]["specific"]["pct"] >= -1e-9


def test_stress_tests(setup):
    pol, u, rets, cfg, ch, m = setup
    b = pol.neutral_weights(3.2)
    st = RK.stress_tests({2030: b}, {2030: b}, rets, m, cfg)
    gfc = next(h for h in st["historical"] if h["id"] == "gfc")
    assert gfc["available"] and gfc["vintages"]["2030"]["portfolio"] < -0.15 and abs(gfc["vintages"]["2030"]["active"]) < 1e-12
    eq = next(h for h in st["hypothetical"] if h["id"] == "equity_selloff")
    r = [lvl["vintages"]["2030"]["portfolio"] for lvl in eq["levels"]]
    assert all(x > y for x, y in zip(r, r[1:])) and r[0] < 0             # worse as severity rises
    rates = next(h for h in st["hypothetical"] if h["id"] == "rates_up")
    assert rates["propagation"] == "isolated" and rates["levels"][0]["vintages"]["2030"]["portfolio"] < 0
    f = RK.conditional_factor_moves(m, {"rates": -0.01}, "isolated")
    assert np.count_nonzero(f) == 1


def test_pipeline_risk_outputs_and_history(tmp_path):
    from meridian.pipelines.target_date import run
    import json
    r0 = run(as_of="2026-09-30", out_root=tmp_path)
    r = run(as_of="2026-10-31", out_root=tmp_path)
    R = json.loads((r.out_dir / "results.json").read_text())
    assert R["risk"]["model"]["months"] > 200 and len(R["risk"]["model"]["factors"]) == 10
    hist = R["risk"]["history"]
    assert len({h["date"] for h in hist}) == 18 and hist[-1]["source"].startswith("this run")
    assert set(R["vintages"]["2050"]["risk_analytics"]) == {"metrics", "breakdown", "factors"}
    assert (tmp_path / "risk_history.csv").exists()
    # the October run uses the September run's recorded (point-in-time) snapshot for September
    sep = [h for h in hist if h["date"] == "2026-09-30"]
    assert sep and all(h["source"] == f"recorded ({r0.run_id})" for h in sep)


def test_ishares_bond_file_without_ticker_column_aggregates_by_name():
    df, as_of = parse_ishares_holdings((FIX / "ishares_bond_noticker_sample.csv").read_bytes())
    assert "Ticker" not in df.columns and len(df) == 7
    agg = aggregate_holdings(df)
    assert abs(agg["weight"].sum() - 1.0) < 1e-9
    assert agg["security_id"].str.startswith("BANK OF AMERICA CORP").sum() == 2   # distinct names stay distinct
