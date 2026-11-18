"""SEC EDGAR financials: frame parsing, matching to look-through holdings, market cap."""
import pandas as pd

from meridian.analytics import risk as RK
from meridian.data import edgar as E

TICKERS = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
           "1": {"cik_str": 1067983, "ticker": "BRK-B", "title": "Berkshire Hathaway"},
           "2": {"cik_str": 999, "ticker": "TM", "title": "Unrelated US filer"}}


def frames():
    return {"revenue": ("CY2025", [{"cik": 320193, "val": 400e9, "end": "2025-09-27"}, {"cik": 1, "val": 5}]),
            "net_income": ("CY2025", [{"cik": 320193, "val": 100e9}]),
            "shares_outstanding": ("CY2026Q3I", [{"cik": 320193, "val": 15e9, "end": "2026-10-17"},
                                                 {"cik": 1067983, "val": 1.3e9, "end": "2026-10-20"},
                                                 {"cik": 999, "val": 1e9}])}


def test_frames_to_frame_maps_ciks_to_tickers():
    df = E.frames_to_frame(TICKERS, frames())
    a = df.set_index("ticker").loc["AAPL"]
    assert a["revenue"] == 400e9 and a["shares_outstanding"] == 15e9 and a["fiscal_period"] == "CY2025"
    assert a["balance_date"] == "2026-10-17" and a["name"] == "Apple Inc."
    assert 1 not in set(df["cik"])                      # unknown CIK dropped
    assert list(df.columns) == E.COLUMNS


def test_periods_walk_back_from_as_of():
    from datetime import date
    assert E._years_back(date(2026, 11, 18), 2) == ["CY2025", "CY2024"]
    assert E._quarters_back(date(2026, 11, 18), 3) == ["CY2026Q3I", "CY2026Q2I", "CY2026Q1I"]
    assert E._quarters_back(date(2026, 2, 1), 1) == ["CY2025Q4I"]


def test_user_agent_from_env(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Meridian ops ops@example.com")
    assert E.user_agent() == "Meridian ops ops@example.com"


def test_lookthrough_market_cap_us_equities_only():
    h = pd.DataFrame([
        {"security_id": "AAPL|United States|Equity", "ticker": "AAPL", "name": "APPLE", "sector": "IT", "asset_class": "Equity",
         "country": "United States", "weight": 0.07, "duration": None, "asset_id": "us_large_cap", "fund_ticker": "IVV",
         "date": "2026-11-05", "price": 230.0, "lines": 1},
        {"security_id": "BRK.B|United States|Equity", "ticker": "BRK.B", "name": "BERKSHIRE", "sector": "Fin", "asset_class": "Equity",
         "country": "United States", "weight": 0.02, "duration": None, "asset_id": "us_large_cap", "fund_ticker": "IVV",
         "date": "2026-11-05", "price": 480.0, "lines": 1},
        {"security_id": "TM|Japan|Equity", "ticker": "TM", "name": "TOYOTA", "sector": "Cons", "asset_class": "Equity",
         "country": "Japan", "weight": 0.01, "duration": None, "asset_id": "intl_dev", "fund_ticker": "IEFA",
         "date": "2026-11-05", "price": 20.0, "lines": 1}])
    ed = E.frames_to_frame(TICKERS, frames())
    ed["date"] = pd.Timestamp("2026-11-03")
    look = RK.lookthrough(h, ["us_large_cap", "intl_dev"], {}, {}, edgar=ed)
    fin = look["financials"]
    assert fin["available"] and fin["as_of"] == "2026-11-03"
    secs = {s[0]: i for i, s in enumerate(look["securities"])}
    aapl = fin["rows"][str(secs["AAPL"])]
    assert aapl["market_cap"] == 15e9 * 230.0 and aapl["net_income"] == 100e9
    assert fin["rows"][str(secs["BRK.B"])]["market_cap"] == 1.3e9 * 480.0      # BRK.B matched to SEC's BRK-B
    assert str(secs["TM"]) not in fin["rows"]                                  # foreign listing never matched


def test_lookthrough_without_edgar():
    h = pd.DataFrame([{"security_id": "X", "ticker": "X", "name": "X", "asset_class": "Equity", "country": "United States",
                       "weight": 1.0, "asset_id": "a", "fund_ticker": "F", "date": "2026-11-05", "lines": 1}])
    fin = RK.lookthrough(h, ["a"], {}, {})["financials"]
    assert fin["available"] is False and fin["rows"] == {}
