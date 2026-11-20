"""Daily closing prices (Yahoo Finance, free) for the home-screen performance table.

A weekday GitHub workflow (.github/workflows/prices.yml) runs `meridian prices fetch` and posts the result to
the app (POST /api/ingest/prices). The app keeps about 13 months of daily adjusted closes per ticker and computes
cumulative returns over 1W, MTD, QTD, YTD and 1Y.

Securities that don't trade under their own ticker (Meridian's own mutual funds and CITs, T-bills) are priced with
the asset class's proxy ETF from config/universe.yaml (identifiers.proxy_etf), and are labelled as proxies. Fund
returns are hypothetical: today's holdings weights x each holding's return (no trading, fees or cash flows).
Yahoo's endpoint is unofficial and for personal, non-commercial use: replace it with a licensed source before
production (config/data_sources.yaml notes the same).
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd

from .data.public import http_get
from .policy import load_universe

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?period1={p1}&period2={p2}&interval=1d&events=div%7Csplit"
PERIODS = ("1W", "MTD", "QTD", "YTD", "1Y")


def price_ticker(inst: dict, universe: dict | None = None) -> tuple[str | None, bool]:
    """(ticker to price this instrument with, is_proxy). ETFs trade under their own symbol."""
    if inst.get("type") == "etf":
        return inst["id"], False
    uni = universe or load_universe()
    ac = uni.get(inst.get("asset_class"), {})
    return (ac.get("identifiers") or {}).get("proxy_etf"), True


def tickers(instruments) -> list[str]:
    uni = load_universe()
    out = {price_ticker(i, uni)[0] for i in instruments}
    return sorted(t for t in out if t)


def parse_daily(raw: bytes) -> dict[str, float]:
    j = json.loads(raw)
    res = (j.get("chart") or {}).get("result") or []
    if not res:
        raise ValueError(f"empty chart ({(j.get('chart') or {}).get('error')})")
    r = res[0]
    ts = r.get("timestamp") or []
    adj = ((r.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []
    idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/New_York").tz_localize(None).normalize()
    return {d.date().isoformat(): round(float(v), 6) for d, v in zip(idx, adj) if v is not None}


def fetch(symbols: list[str], days: int = 400, end: date | None = None) -> dict:
    """{as_of, source, series: {ticker: {date: adjusted close}}, errors}."""
    end = end or date.today()
    p2 = int(pd.Timestamp(end + timedelta(days=1)).timestamp())
    p1 = int(pd.Timestamp(end - timedelta(days=days)).timestamp())
    series, errors = {}, {}
    for t in symbols:
        try:
            series[t] = parse_daily(http_get(URL.format(t=t, p1=p1, p2=p2), retries=2))
        except Exception as e:  # noqa: BLE001  one bad ticker shouldn't stop the rest
            errors[t] = str(e)[:200]
    last = max((max(s) for s in series.values() if s), default=None)
    return {"as_of": last, "source": "Yahoo Finance daily adjusted closes (unofficial endpoint)", "series": series,
            "errors": errors}


def _close_on_or_before(s: dict[str, float], d: str) -> tuple[str, float] | None:
    ks = [k for k in s if k <= d]
    return (max(ks), s[max(ks)]) if ks else None


def period_starts(as_of: str) -> dict[str, str]:
    """The base date of each period: the last close on or before it is the starting price."""
    d = date.fromisoformat(as_of)
    q0 = date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)
    return {"1W": (d - timedelta(days=7)).isoformat(), "MTD": (d.replace(day=1) - timedelta(days=1)).isoformat(),
            "QTD": (q0 - timedelta(days=1)).isoformat(), "YTD": date(d.year - 1, 12, 31).isoformat(),
            "1Y": (d - timedelta(days=365)).isoformat()}


def returns(s: dict[str, float], as_of: str) -> dict[str, float | None]:
    end = _close_on_or_before(s, as_of)
    out = {}
    for k, d0 in period_starts(as_of).items():
        st = _close_on_or_before(s, d0)
        # no price that far back (e.g. history too short): no return rather than a partial one
        out[k] = (end[1] / st[1] - 1) if end and st and st[1] and min(s) <= d0 else None
    return out
