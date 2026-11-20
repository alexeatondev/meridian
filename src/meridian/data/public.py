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


def http_get(url: str, timeout: int = 30, retries: int = 1, headers: dict | None = None) -> bytes:
    import os
    import urllib.error
    if os.getenv("MERIDIAN_OFFLINE", "").lower() in ("1", "true", "yes"):
        raise NetworkUnavailable(f"offline mode (MERIDIAN_OFFLINE): not fetching {url.split('/')[2]}")
    last = None
    for i in range(retries + 1):
        try:
            if not url.startswith("https://"):     # public data sources only, never file:// or other schemes
                raise ValueError(f"Only https URLs are fetched: {url[:40]}")
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310 - scheme checked above
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
    API = "https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={key}&file_type=json"

    def datasets(self):
        o = self.options
        return {d for d, k in (("macro.indicators", "indicators"), ("yields.current", "yields"),
                               ("returns.monthly", "return_series")) if o.get(k)}

    def series(self, sid: str, end=None) -> pd.Series:
        """Uses the official FRED API when FRED_API_KEY is set (reliable from cloud runners);
        otherwise the keyless fredgraph CSV download."""
        import os
        key = os.getenv(self.options.get("api_key_env", "FRED_API_KEY"))
        if key:
            j = json.loads(http_get(self.API.format(sid=sid, key=key), timeout=60))
            obs = j.get("observations") or []
            s = pd.Series(pd.to_numeric([o["value"] for o in obs], errors="coerce"),
                          index=pd.to_datetime([o["date"] for o in obs])).dropna()
        else:
            s = parse_fred_csv(http_get(self.BASE + sid, timeout=60), sid)
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


# ============================================================================================ US Treasury
class TreasurySource(DataSource):
    """US Treasury daily par yield curve (home.treasury.gov), no key. Serves yields.current and the
    10y-2y curve indicator. options.yields: {asset_id: {tenor: '3 Mo'|'5 Yr'|..., duration, expected_loss}}"""
    URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
           "{y}/all?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv")

    def datasets(self):
        out = {"yields.current"} if self.options.get("yields") else set()
        return out | ({"macro.indicators"} if self.options.get("curve_indicator", True) else set())

    def curve(self, end) -> pd.DataFrame:
        end = pd.Timestamp(end)
        frames = []
        for y in (end.year, end.year - 1):
            try:
                frames.append(pd.read_csv(io.BytesIO(http_get(self.URL.format(y=y), timeout=60))))
            except NetworkUnavailable:
                raise
            except Exception:  # noqa: BLE001
                continue
        if not frames:
            raise DataUnavailable("Treasury: no yield curve data")
        df = pd.concat(frames)
        df["Date"] = pd.to_datetime(df["Date"])
        return df[df["Date"] <= end].sort_values("Date")

    def fetch(self, req: Request) -> pd.DataFrame:
        c = self.curve(req.as_of or req.end)
        last = c.iloc[-1]
        if req.dataset == "macro.indicators":
            return pd.DataFrame([{"indicator": "yield_curve_10y2y_bp", "date": last["Date"],
                                  "value": float((last["10 Yr"] - last["2 Yr"]) * 100), "series": "UST 10Y-2Y"}])
        rows = []
        for aid, spec in self.options["yields"].items():
            if req.assets and aid not in {a["id"] for a in req.assets}:
                continue
            rows.append({"asset_id": aid, "date": last["Date"], "yield": float(last[spec["tenor"]]) / 100,
                         "duration": float(spec.get("duration", 0)), "expected_loss": float(spec.get("expected_loss", 0)),
                         "series": f"UST {spec['tenor']}"})
        return pd.DataFrame(rows)


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
    # bars are stamped at exchange-local midnight on the 1st; normalize to a clean month-end date
    idx = (pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/New_York").tz_localize(None).normalize()
           + pd.offsets.MonthEnd(0))
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


# ============================================================================================ iShares
ISHARES_URLS = ("https://www.ishares.com/us/products/{pid}/x/latest-holdings.csv",           # current (2026)
                "https://www.ishares.com/us/products/{pid}/fund/1467271812596.ajax"
                "?fileType=csv&fileName={ticker}_holdings&dataType=fund",
                "https://www.ishares.com/us/products/{pid}/{slug}/1467271812596.ajax"
                "?fileType=csv&fileName={ticker}_holdings&dataType=fund")


def _num(x) -> float:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    s = str(x).replace(",", "").replace("%", "").strip()
    if s in ("", "-", "--", "N/A"):
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def parse_ishares_holdings(raw: bytes) -> tuple[pd.DataFrame, str | None]:
    """iShares holdings CSV: a few preamble lines ('Fund Holdings as of,"Nov 05, 2026"'), a header row
    starting with 'Ticker' (equity funds) or 'Name' (bond funds have no ticker column), the positions,
    then a disclaimer footer. Columns vary by asset class."""
    text = raw.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    as_of = None
    start = None
    for i, l in enumerate(lines[:40]):
        if l.lower().startswith("fund holdings as of"):
            m = l.split(",", 1)[1].strip().strip('"') if "," in l else ""
            try:
                as_of = str(pd.Timestamp(m).date())
            except Exception:  # noqa: BLE001
                as_of = None
        h = l.lstrip('"')
        if (h.startswith("Ticker") or h.startswith("Name")) and "Name" in l and "Weight" in l:
            start = i
            break
    if start is None:
        snippet = " | ".join(x.strip()[:80] for x in lines[:4])
        raise DataUnavailable(f"iShares: holdings header row not found (format changed or not a holdings file); "
                              f"{len(raw)} bytes, starts: {snippet!r}")
    # parse everything after the header with a real CSV parser (quoted fields may contain line breaks);
    # the disclaimer footer becomes rows without a numeric weight and is dropped by aggregate_holdings
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), dtype=str, on_bad_lines="skip", skip_blank_lines=True)
    df.columns = [c.strip() for c in df.columns]
    return df, as_of


def aggregate_holdings(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize iShares columns and aggregate to one row per security (equities) or issuer (bonds:
    iShares 'Ticker' on bond lines is the issuer ticker). Durations are weight-averaged."""
    col = {c.lower().strip(): c for c in df.columns}

    def g(*names):
        for n in names:                                   # exact (case-insensitive) first
            if n in col:
                return col[n]
        for n in names:                                   # then "contains", e.g. 'weight (%)' vs 'weight %'
            for k, c in col.items():
                if n.split(" (")[0] in k:
                    return c
        return None
    if g("weight (%)", "weight") is None:
        raise DataUnavailable(f"iShares: no weight column; columns = {list(df.columns)[:20]}")
    out = pd.DataFrame({
        "ticker": df[g("ticker")].fillna("").str.strip() if g("ticker") else "",
        "name": df[g("name")].fillna("").str.strip() if g("name") else "",
        "sector": df[g("sector")].fillna("").str.strip() if g("sector") else "",
        "asset_class": df[g("asset class")].fillna("").str.strip() if g("asset class") else "",
        "country": df[g("location", "location of risk")].fillna("").str.strip() if g("location", "location of risk") else "",
        "weight": df[g("weight (%)", "weight")].map(_num) / 100.0,
        "duration": df[g("duration", "effective duration", "mod. duration")].map(_num) if g("duration", "effective duration", "mod. duration") else np.nan,
        # last price per share (equities): with SEC shares outstanding gives market cap on Look-through
        "price": df[col["price"]].map(_num) if "price" in col else np.nan,
    })
    # iShares rounds 'Weight (%)' to 0.01%, which loses ~20% of a fund with thousands of tiny lines (AGG).
    # Market values are exact: derive weights from them when they are present and sum to something sensible.
    mvc = g("market value")
    if mvc is not None:
        mv = df[mvc].map(_num)
        tot = mv.sum(skipna=True)
        if tot > 0 and mv.notna().sum() >= 0.9 * out["weight"].notna().sum():
            out["weight"] = (mv / tot).where(out["weight"].notna(), np.nan)
    out = out[out["weight"].notna()]
    out["ticker"] = out["ticker"].replace({"-": "", "--": ""})
    is_bond = out["asset_class"].str.contains("Fixed Income", case=False, na=False)
    key = np.where(out["ticker"] != "", out["ticker"], out["name"].str.upper().str[:40])
    # the same ticker can be a stock and a bond issuer (JPM): keep them apart by asset class
    out["security_id"] = [f"{k}|{c}|{ac}" for k, c, ac in zip(key, out["country"], out["asset_class"])]
    out["dw"] = out["duration"].fillna(0) * out["weight"]
    out["lines"] = 1
    out["_bond"] = is_bond
    # largest line names the aggregate (e.g. 'TREASURY NOTE' for issuer T)
    out = out.sort_values("weight", ascending=False)
    agg = out.groupby("security_id", sort=False).agg(
        ticker=("ticker", "first"), name=("name", "first"), sector=("sector", "first"),
        asset_class=("asset_class", "first"), country=("country", "first"),
        weight=("weight", "sum"), dw=("dw", "sum"), lines=("lines", "sum"), bond=("_bond", "max"),
        price=("price", "first")).reset_index()
    agg.loc[agg["bond"], "price"] = np.nan                 # a bond price is per 100 face, not per share
    agg["duration"] = np.where(agg["bond"] & (agg["weight"].abs() > 1e-12), agg["dw"] / agg["weight"].where(agg["weight"] != 0, 1), np.nan)
    return agg.drop(columns=["dw", "bond"])


class IsharesSource(DataSource):
    """Daily look-through holdings of iShares ETFs (public CSV on ishares.com).
    universe.yaml -> identifiers.holdings: [{provider: ishares, ticker: AGG, product_id: 239458, weight: 1.0}]
    A blend of several funds (weights summing to 1) can stand in for one building block."""

    def datasets(self):
        return {"holdings.lookthrough"}

    def fetch(self, req: Request) -> pd.DataFrame:
        frames, notes = [], []
        for a in req.assets:
            for h in (a.get("identifiers", {}).get("holdings") or []):
                if h.get("provider") != "ishares":
                    continue
                try:
                    df = as_of = None
                    errs = []
                    for tmpl in ISHARES_URLS:
                        url = tmpl.format(pid=h["product_id"], ticker=h["ticker"], slug=h.get("slug", "fund"))
                        try:
                            df, as_of = parse_ishares_holdings(http_get(url, timeout=60))
                            break
                        except NetworkUnavailable:
                            raise
                        except DataUnavailable as e:
                            errs.append(str(e))
                    if df is None:
                        raise DataUnavailable(errs[0])
                    agg = aggregate_holdings(df)
                except NetworkUnavailable:
                    raise
                except DataUnavailable as e:
                    notes.append(f"{h['ticker']}: {e}")
                    continue
                except Exception as e:  # noqa: BLE001
                    cols = list(df.columns)[:20] if df is not None else None
                    notes.append(f"{h['ticker']}: parse error {type(e).__name__}: {e}; columns={cols}")
                    continue
                agg["weight"] = agg["weight"] * float(h.get("weight", 1.0))
                agg["asset_id"], agg["fund_ticker"] = a["id"], h["ticker"]
                agg["date"] = pd.Timestamp(as_of or req.as_of or datetime.now(timezone.utc).date())
                agg["blend_weight"] = float(h.get("weight", 1.0))
                frames.append(agg)
                time.sleep(0.5)
        if not frames:
            raise DataUnavailable("iShares: no holdings retrieved. " + "; ".join(notes[:3]))
        out = pd.concat(frames, ignore_index=True)
        if notes:
            out.attrs["warnings"] = notes
        return out


def write_cache(frames: dict[str, pd.DataFrame], root: Path, meta: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for ds, df in frames.items():
        df.to_csv(root / f"{ds}.csv", index=False)
    (root / "manifest.json").write_text(json.dumps(meta, indent=2, default=str))
    return root
