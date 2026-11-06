"""Free / public data sources.

- FredSource      — Federal Reserve Economic Data (St. Louis Fed). Macro indicators, Treasury and credit
                    yields, T-bill returns. No API key (fredgraph.csv endpoint).
- YahooSource     — Yahoo Finance chart endpoint. Monthly dividend-adjusted total returns for the proxy
                    funds/ETFs in config/universe.yaml, spliced across a list of tickers to extend history.
                    Unofficial endpoint; personal/non-commercial terms. Replace before production.
- ManualSource    — Hand-maintained inputs (config/manual_inputs.yaml) with a source and as-of date per value,
                    e.g. CAPE from Multpl/Shiller. Fields left null are filled by lower-priority sources.
- CsvUrlSource    — Any HTTP(S) CSV, mapped to a canonical dataset by config (plug in new free sources
                    without code).

All fetching uses the standard library. Network errors raise DataUnavailable so routing falls through.
"""
from __future__ import annotations

import io
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .. import REPO_ROOT
from .base import DataSource, DataUnavailable, Request

UA = "Mozilla/5.0 (compatible; meridian-data/0.1)"


class NetworkUnavailable(DataUnavailable):
    """Host unreachable (no internet, proxy refusal, DNS) — distinct from a missing series/ticker."""


def http_get(url: str, timeout: int = 30, retries: int = 1) -> bytes:
    import urllib.error
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:          # server answered: series/ticker problem, or rate limit
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                break
        except Exception as e:  # noqa: BLE001     # could not reach the host
            raise NetworkUnavailable(f"cannot reach {url.split('/')[2]}: {type(e).__name__}") from e
        time.sleep(2.0 * (i + 1))
    raise DataUnavailable(f"GET failed {url}: {type(last).__name__}: {last}")


# ============================================================================================ FRED
def parse_fred_csv(raw: bytes, series: str) -> pd.Series:
    df = pd.read_csv(io.BytesIO(raw))
    date_col = df.columns[0]                       # 'observation_date' (current) or 'DATE' (older)
    val_col = series if series in df.columns else df.columns[1]
    s = pd.to_numeric(df[val_col], errors="coerce")  # '.' = missing
    s.index = pd.to_datetime(df[date_col])
    return s.dropna()


class FredSource(DataSource):
    """Config options:
         indicators: {name: {series: ID, transform: level|yoy_pct|diff_6m|x100, periods: int}}
         yields:     {asset_id: {series: ID | [IDs averaged], duration: float, expected_loss: float}}
         return_series: {asset_id: {series: ID}}  # annualized % yield -> monthly return (T-bills)
    """
    BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="

    def datasets(self):
        o = self.options
        return {d for d, k in (("macro.indicators", "indicators"), ("yields.current", "yields"),
                               ("returns.monthly", "return_series")) if o.get(k)}

    def series(self, sid: str, end=None) -> pd.Series:
        s = parse_fred_csv(http_get(self.BASE + sid), sid)
        return s[s.index <= pd.Timestamp(end)] if end is not None else s

    def fetch(self, req: Request) -> pd.DataFrame:
        end = pd.Timestamp(req.as_of or req.end or datetime.now(timezone.utc).date())
        rows, missing = [], []
        if req.dataset == "macro.indicators":
            for name, spec in self.options["indicators"].items():
                try:
                    s = self.series(spec["series"], end)
                except NetworkUnavailable:
                    raise
                except DataUnavailable:
                    missing.append(spec["series"])
                    continue
                if spec.get("frequency") == "M":
                    s = s.resample("ME").last().dropna()
                t, n = spec.get("transform", "level"), int(spec.get("periods", 12))
                if t == "yoy_pct":
                    v = (s.iloc[-1] / s.iloc[-1 - n] - 1) * 100
                elif t == "diff":
                    v = s.iloc[-1] - s.iloc[-1 - n]
                elif t == "x100":
                    v = s.iloc[-1] * 100
                else:
                    v = s.iloc[-1]
                rows.append({"indicator": name, "date": s.index[-1], "value": float(v), "series": spec["series"]})
        elif req.dataset == "yields.current":
            wanted = {a["id"] for a in req.assets} or set(self.options["yields"])
            for aid, spec in self.options["yields"].items():
                if aid not in wanted:
                    continue
                ids = spec["series"] if isinstance(spec["series"], list) else [spec["series"]]
                try:
                    vals = [self.series(i, end) for i in ids]
                except NetworkUnavailable:
                    raise
                except DataUnavailable:
                    missing += ids
                    continue
                rows.append({"asset_id": aid, "date": max(v.index[-1] for v in vals),
                             "yield": float(np.mean([v.iloc[-1] for v in vals]) / 100),
                             "duration": float(spec.get("duration", 0)), "expected_loss": float(spec.get("expected_loss", 0)),
                             "series": ",".join(ids)})
        elif req.dataset == "returns.monthly":
            wanted = {a["id"] for a in req.assets}
            for aid, spec in self.options["return_series"].items():
                if wanted and aid not in wanted:
                    continue
                s = self.series(spec["series"], end).resample("ME").mean().dropna() / 100
                r = s.shift(1) / 12                     # earn last month's annualized bill yield
                start = pd.Timestamp(req.start or "1990-01-31")
                r = r[(r.index >= start)].dropna()
                rows += [{"asset_id": aid, "date": d, "ret": float(v)} for d, v in r.items()]
        if not rows:
            raise DataUnavailable(f"FRED: nothing retrieved for {req.dataset}; missing {missing}")
        df = pd.DataFrame(rows)
        if missing:
            df.attrs["warnings"] = [f"FRED series unavailable: {missing}"]
        return df


# ============================================================================================ Yahoo
def parse_yahoo_chart(raw: bytes) -> pd.Series:
    j = json.loads(raw)
    res = (j.get("chart") or {}).get("result") or []
    if not res:
        raise DataUnavailable(f"Yahoo: empty chart ({(j.get('chart') or {}).get('error')})")
    r = res[0]
    ts = r.get("timestamp") or []
    adj = ((r.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []
    if not ts or not adj:
        raise DataUnavailable("Yahoo: no adjclose")
    idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert(None) + pd.offsets.MonthEnd(0)
    s = pd.Series(adj, index=idx, dtype="float64").dropna()
    return s[~s.index.duplicated(keep="last")]


def splice_returns(series_by_priority: list[pd.Series]) -> pd.Series:
    """Primary series wins where it exists; earlier history filled from the next proxy, and so on."""
    out = None
    for s in series_by_priority:
        if s is None or s.empty:
            continue
        out = s if out is None else out.combine_first(s)
    return out if out is not None else pd.Series(dtype="float64")


class YahooSource(DataSource):
    BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?period1={p1}&period2={p2}&interval=1mo&events=div%7Csplit"

    def datasets(self):
        return {"returns.monthly"}

    def prices(self, ticker: str, start, end) -> pd.Series:
        p1 = int(pd.Timestamp(start).timestamp()) - 40 * 86400
        p2 = int((pd.Timestamp(end) + pd.Timedelta(days=5)).timestamp())
        return parse_yahoo_chart(http_get(self.BASE.format(t=ticker, p1=p1, p2=p2)))

    def fetch(self, req: Request) -> pd.DataFrame:
        end = pd.Timestamp(req.end or req.as_of) + pd.offsets.MonthEnd(0)
        start = pd.Timestamp(req.start or "1999-01-31")
        rows, notes = [], []
        for a in req.assets:
            tickers = a["identifiers"].get("yahoo") or []
            tickers = [tickers] if isinstance(tickers, str) else tickers
            rets = []
            for t in tickers:
                try:
                    px = self.prices(t, start, end)
                    r = px.pct_change().dropna()
                    rets.append(r[(r.index <= end)])
                except NetworkUnavailable:
                    raise
                except DataUnavailable as e:
                    notes.append(f"{t}: {e}")
            s = splice_returns(rets)
            if s.empty:
                continue
            s = s[s.index >= start]
            rows += [{"asset_id": a["id"], "date": d, "ret": float(v)} for d, v in s.items()]
        if not rows:
            raise DataUnavailable("Yahoo: no tickers retrieved. " + "; ".join(notes[:3]))
        df = pd.DataFrame(rows)
        if notes:
            df.attrs["warnings"] = notes
        return df


# ============================================================================================ Manual
class ManualSource(DataSource):
    def _load(self) -> dict:
        p = REPO_ROOT / self.options.get("path", "config/manual_inputs.yaml")
        return yaml.safe_load(p.read_text()) if p.exists() else {}

    def datasets(self):
        return set(self._load().keys())

    def fetch(self, req: Request) -> pd.DataFrame:
        block = self._load().get(req.dataset) or {}
        rows = []
        for key, rec in block.items():
            vals = {k: v for k, v in rec.items() if k not in ("source", "as_of", "note")}
            if all(v is None for v in vals.values()):
                continue
            id_col = "asset_id" if req.dataset != "macro.indicators" else "indicator"
            rows.append({id_col: key, "date": pd.Timestamp(str(rec.get("as_of", req.as_of))), **vals,
                         "citation": rec.get("source", "")})
        if not rows:
            raise DataUnavailable(f"manual: no values for {req.dataset}")
        return pd.DataFrame(rows)


# ============================================================================================ CSV URL
class CsvUrlSource(DataSource):
    """options.datasets.<canonical>: {url: str, columns: {canonical_col: csv_col}, asset_id: optional constant}"""

    def datasets(self):
        return set((self.options.get("datasets") or {}).keys())

    def fetch(self, req: Request) -> pd.DataFrame:
        spec = self.options["datasets"][req.dataset]
        df = pd.read_csv(io.BytesIO(http_get(spec["url"])))
        df = df.rename(columns={v: k for k, v in spec.get("columns", {}).items()})
        for k, v in (spec.get("constants") or {}).items():
            df[k] = v
        if "date" in df:
            df["date"] = pd.to_datetime(df["date"])
        return df


def write_cache(frames: dict[str, pd.DataFrame], root: Path, meta: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for ds, df in frames.items():
        df.to_csv(root / f"{ds}.csv", index=False)
    (root / "manifest.json").write_text(json.dumps(meta, indent=2, default=str))
    return root
