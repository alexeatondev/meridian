import json
import shutil

import pandas as pd
import pytest

from meridian.data import public
from meridian.data.base import DataUnavailable, Request
from meridian.data.registry import DataRegistry, merge_frames
from meridian.policy import load_universe


def test_parse_fred_csv_handles_missing_and_new_header():
    raw = b"observation_date,DTB3\n2026-09-30,3.90\n2026-10-01,.\n2026-10-31,3.85\n"
    s = public.parse_fred_csv(raw, "DTB3")
    assert list(s.values) == [3.90, 3.85]


def test_parse_yahoo_chart_month_end_index():
    payload = {"chart": {"result": [{"timestamp": [1759276800, 1761955200],
                                      "indicators": {"adjclose": [{"adjclose": [100.0, 102.0]}]}}], "error": None}}
    s = public.parse_yahoo_chart(json.dumps(payload).encode())
    assert len(s) == 2 and s.index[0].is_month_end


def test_splice_prefers_primary_and_backfills_history():
    idx = pd.date_range("2020-01-31", periods=6, freq="ME")
    primary = pd.Series([0.01, 0.02, 0.03], index=idx[3:])
    proxy = pd.Series([0.1] * 6, index=idx)
    out = public.splice_returns([primary, proxy])
    assert list(out.values) == [0.1, 0.1, 0.1, 0.01, 0.02, 0.03]


def test_merge_time_series_priority_and_provenance():
    d = pd.date_range("2024-01-31", periods=3, freq="ME")
    a = pd.DataFrame({"asset_id": "x", "date": d[1:], "ret": [0.1, 0.2], "_source": "vendor"})
    b = pd.DataFrame({"asset_id": "x", "date": d, "ret": [9, 9, 9], "_source": "cache"})
    m = merge_frames("returns.monthly", [a, b])
    assert list(m["ret"]) == [9, 0.1, 0.2] and list(m["_source"]) == ["cache", "vendor", "vendor"]


def test_merge_snapshot_fills_per_field():
    a = pd.DataFrame([{"asset_id": "us", "date": "2026-10-31", "cape": 41.07, "dividend_yield": None, "earnings_growth": None, "_source": "manual"}])
    b = pd.DataFrame([{"asset_id": "us", "date": "2026-10-31", "cape": 30.0, "dividend_yield": 0.013, "earnings_growth": 0.02, "_source": "synthetic"}])
    m = merge_frames("fundamentals.valuation", [a, b]).iloc[0]
    assert m["cape"] == 41.07 and m["dividend_yield"] == 0.013 and m["_source"] == "manual+synthetic"


def test_fallback_only_fills_missing_assets(monkeypatch):
    """Real history for one asset must never be patched with synthetic rows."""
    u = load_universe()
    reg = DataRegistry.from_config(overrides={"yahoo": True, "fred": False, "cache": False})
    d = pd.date_range("2015-01-31", "2026-09-30", freq="ME")

    def fake_fetch(self, req):
        return pd.DataFrame({"asset_id": "us_large_cap", "date": d, "ret": 0.01})
    monkeypatch.setattr(public.YahooSource, "fetch", fake_fetch)
    res = reg.get(Request("returns.monthly", list(u.values()), start="2010-01-31", end="2026-10-31"))
    lc = res.frame[res.frame.asset_id == "us_large_cap"]
    assert set(lc["_source"]) == {"yahoo"} and lc["date"].min() == d.min()      # no synthetic pre-2015 patch
    others = res.frame[res.frame.asset_id != "us_large_cap"]
    assert set(others["_source"]) == {"synthetic"} and res.synthetic
    assert "synthetic_assets" in res.notes


def test_network_failure_falls_through(monkeypatch):
    def boom(url, timeout=30, retries=1):
        raise public.NetworkUnavailable("cannot reach host")
    monkeypatch.setattr(public, "http_get", boom)
    reg = DataRegistry.from_config()
    res = reg.get(Request("macro.indicators", list(load_universe().values()), as_of="2026-10-31"))
    assert any(a["source"] == "fred" and "unavailable" in a["status"] for a in reg.attempts)
    assert not res.frame.empty


def test_cli_plug_unplug_preserves_comments(tmp_path, monkeypatch):
    from meridian.data import manage
    from meridian.data.registry import CONFIG_PATH
    cfg = tmp_path / "ds.yaml"
    shutil.copy(CONFIG_PATH, cfg)
    manage.set_enabled("yahoo", False, cfg)
    manage.set_enabled("bloomberg_snowflake", True, cfg)
    manage.set_route("returns.monthly", ["bloomberg_snowflake", "yahoo"], "merge", ["synthetic"], cfg)
    manage.add_source("my_csv", "csv_url", "http", {"datasets": {}}, True, cfg)
    text = cfg.read_text()
    assert "# Data connectivity" in text and "Plug / unplug" in text
    reg = DataRegistry.from_config(cfg)
    assert reg.cfg["sources"]["yahoo"]["enabled"] is False and reg.cfg["sources"]["bloomberg_snowflake"]["enabled"] is True
    assert reg.cfg["routing"]["returns.monthly"]["sources"] == ["bloomberg_snowflake", "yahoo"]
    with pytest.raises(SystemExit):
        manage.set_enabled("nope", True, cfg)
