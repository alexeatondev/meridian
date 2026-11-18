"""SEC EDGAR company financials (free, official): `fundamentals.edgar`.

Uses the SEC's XBRL "frames" API, which returns one reported value per company for a concept and a calendar
period in a single call, so the whole US-listed universe costs about a dozen requests:
  https://data.sec.gov/api/xbrl/frames/{taxonomy}/{concept}/{unit}/{period}.json
and the ticker map https://www.sec.gov/files/company_tickers.json.

SEC fair-access rules: identify yourself in the User-Agent (name and contact email) and stay under 10
requests a second. Set SEC_USER_AGENT (e.g. "Meridian research ops@yourfirm.com"); a generic agent is used
otherwise and SEC may refuse it. Market cap = shares outstanding (cover page) x price from the look-through
holdings files; ownership = Meridian's dollar exposure / market cap (computed for the console).

Values are as filed (unaudited quarters included); duration items are the latest calendar year available
(CYyyyy frames); balance-sheet items are the latest quarter-end instant (CYyyyyQnI).
"""
from __future__ import annotations

import json
import os
import time
from datetime import date

import pandas as pd

from .base import DataSource, DataUnavailable, Request

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FRAME_URL = "https://data.sec.gov/api/xbrl/frames/{tax}/{concept}/{unit}/{period}.json"

# column -> concepts to try in order (taxonomy, concept, unit); first with data for a company wins
DURATION = {
    "revenue": [("us-gaap", "Revenues", "USD"), ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax", "USD"),
                ("us-gaap", "SalesRevenueNet", "USD")],
    "net_income": [("us-gaap", "NetIncomeLoss", "USD")],
    "operating_income": [("us-gaap", "OperatingIncomeLoss", "USD")],
    "operating_cash_flow": [("us-gaap", "NetCashProvidedByUsedInOperatingActivities", "USD")],
    "capex": [("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment", "USD")],
    "eps_diluted": [("us-gaap", "EarningsPerShareDiluted", "USD-per-shares")],
}
INSTANT = {
    "total_assets": [("us-gaap", "Assets", "USD")],
    "total_liabilities": [("us-gaap", "Liabilities", "USD")],
    "equity": [("us-gaap", "StockholdersEquity", "USD")],
    "cash": [("us-gaap", "CashAndCashEquivalentsAtCarryingValue", "USD")],
    "long_term_debt": [("us-gaap", "LongTermDebtNoncurrent", "USD"), ("us-gaap", "LongTermDebt", "USD")],
    "shares_outstanding": [("dei", "EntityCommonStockSharesOutstanding", "shares"),
                           ("us-gaap", "CommonStockSharesOutstanding", "shares")],
}
COLUMNS = ["ticker", "cik", "name", "fiscal_period", "balance_date", *DURATION, *INSTANT]


_UA: list[str] = []          # set from config (sources.sec_edgar.options.user_agent) when the source is built


def user_agent() -> str:
    """SEC_USER_AGENT (env / repository variable) wins, then the config option, then a generic agent."""
    return os.getenv("SEC_USER_AGENT") or (_UA[0] if _UA else "") or "Meridian research (github.com/alexeatondev/meridian)"


def _get(url: str) -> dict:
    from .public import http_get
    raw = http_get(url, timeout=60, headers={"User-Agent": user_agent()})   # SEC needs a declared agent
    time.sleep(0.15)                                       # well under SEC's 10 requests a second
    return json.loads(raw)


def _years_back(as_of: date, n: int = 3) -> list[str]:
    return [f"CY{as_of.year - k}" for k in range(1, n + 1)]


def _quarters_back(as_of: date, n: int = 6) -> list[str]:
    y, q = as_of.year, (as_of.month - 1) // 3          # last complete quarter
    out = []
    for _ in range(n):
        if q == 0:
            y, q = y - 1, 4
        out.append(f"CY{y}Q{q}I")
        q -= 1
    return out


def frames_to_frame(tickers: dict, frames: dict[str, tuple[str, list[dict]]]) -> pd.DataFrame:
    """tickers: SEC company_tickers.json; frames: column -> (period, data rows). Pure, for tests."""
    by_cik: dict[int, dict] = {}
    for v in tickers.values():
        by_cik.setdefault(int(v["cik_str"]), {"ticker": str(v["ticker"]).upper(), "name": v.get("title", "")})
    rows: dict[int, dict] = {}
    for col, (period, data) in frames.items():
        for d in data:
            cik = int(d["cik"])
            if cik not in by_cik:
                continue
            r = rows.setdefault(cik, {"cik": cik, **by_cik[cik]})
            if r.get(col) is None:
                r[col] = float(d["val"])
                if col in DURATION and not r.get("fiscal_period"):
                    r["fiscal_period"] = period
                if col in INSTANT and not r.get("balance_date"):
                    r["balance_date"] = d.get("end", period)
    df = pd.DataFrame(rows.values())
    for c in COLUMNS:
        if c not in df:
            df[c] = None
    return df[COLUMNS]


class EdgarSource(DataSource):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        if self.options.get("user_agent"):
            _UA[:] = [str(self.options["user_agent"])]

    def datasets(self):
        return {"fundamentals.edgar"}

    def fetch(self, req: Request) -> pd.DataFrame:
        as_of = date.fromisoformat(str(req.as_of or req.end or date.today())[:10])
        tickers = _get(TICKERS_URL)
        frames: dict[str, tuple[str, list[dict]]] = {}
        notes = []
        for spec, periods in ((DURATION, _years_back(as_of)), (INSTANT, _quarters_back(as_of))):
            for col, concepts in spec.items():
                got = None
                for period in periods:                     # newest period that has data
                    for tax, concept, unit in concepts:
                        try:
                            d = _get(FRAME_URL.format(tax=tax, concept=concept, unit=unit, period=period))
                        except DataUnavailable:
                            continue
                        if d.get("data"):
                            got = (period, d["data"])
                            break
                    if got:
                        break
                if got:
                    frames[col] = got
                else:
                    notes.append(f"{col}: no frame found")
        if not frames:
            raise DataUnavailable("SEC EDGAR: no frames returned. " + "; ".join(notes[:3]))
        df = frames_to_frame(tickers, frames)
        df["date"] = pd.Timestamp(as_of)
        if notes:
            df.attrs["warnings"] = notes
        return df
