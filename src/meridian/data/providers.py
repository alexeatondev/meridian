"""Concrete data sources. Vendor SDKs are imported lazily so nothing is required until enabled."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from .base import DataSource, DataUnavailable, Request

# --------------------------------------------------------------------------------------------
# Synthetic (pilot only). Deterministic, documented assumptions; every output is labeled.
# --------------------------------------------------------------------------------------------
# (annual mean total return, annual vol, factor loadings on [equity, rates, credit, inflation])
SYNTH_ASSUMPTIONS = {
    "us_large_cap":      (0.095, 0.155, [1.00, 0.05, 0.10, 0.00]),
    "us_small_mid_cap":  (0.100, 0.195, [1.15, 0.00, 0.20, 0.05]),
    "intl_developed_eq": (0.080, 0.165, [0.90, 0.05, 0.10, 0.10]),
    "emerging_eq":       (0.090, 0.215, [1.05, 0.00, 0.25, 0.25]),
    "global_reits":      (0.085, 0.195, [0.85, 0.35, 0.20, 0.20]),
    "commodities":       (0.045, 0.165, [0.30, -0.15, 0.10, 0.90]),
    "us_core_bond":      (0.042, 0.045, [0.00, 0.95, 0.15, -0.10]),
    "us_long_treasury":  (0.048, 0.120, [-0.20, 1.00, -0.10, -0.15]),
    "us_tips_short":     (0.035, 0.030, [0.00, 0.40, 0.00, 0.60]),
    "us_high_yield":     (0.062, 0.090, [0.55, 0.20, 0.80, 0.00]),
    "intl_bond_hedged":  (0.038, 0.040, [0.00, 0.90, 0.10, -0.05]),
    "em_debt":           (0.060, 0.095, [0.40, 0.45, 0.70, 0.10]),
    "cash":              (0.028, 0.006, [0.00, 0.05, 0.00, 0.05]),
}
SYNTH_VALUATION = {  # cape, dividend yield, real earnings growth (equity-like only)
    "us_large_cap": (34.0, 0.013, 0.025), "us_small_mid_cap": (22.0, 0.014, 0.022),
    "intl_developed_eq": (18.0, 0.030, 0.015), "emerging_eq": (15.0, 0.028, 0.030),
    "global_reits": (21.0, 0.038, 0.010),
}
SYNTH_YIELDS = {  # yield to worst, duration, expected annual credit loss
    "us_core_bond": (0.0445, 6.0, 0.0010), "us_long_treasury": (0.0475, 15.5, 0.0),
    "us_tips_short": (0.0390, 2.5, 0.0), "us_high_yield": (0.0690, 3.3, 0.0150),
    "intl_bond_hedged": (0.0420, 7.0, 0.0005), "em_debt": (0.0660, 7.0, 0.0090),
    "cash": (0.0385, 0.25, 0.0), "commodities": (0.0385, 0.0, 0.0),
}


class SyntheticSource(DataSource):
    def datasets(self):
        return {"returns.monthly", "macro.indicators", "fundamentals.valuation", "yields.current"}

    def fetch(self, req: Request) -> pd.DataFrame:
        seed = int(self.options.get("seed", 0))
        end = pd.Timestamp(req.end or req.as_of or "2026-10-31") + pd.offsets.MonthEnd(0)
        start = pd.Timestamp(req.start or self.options.get("start", "1999-01-31")) + pd.offsets.MonthEnd(0)
        dates = pd.date_range(start, end, freq="ME")
        ids = [a["id"] for a in req.assets] or list(SYNTH_ASSUMPTIONS)
        if req.dataset == "returns.monthly":
            rng = np.random.default_rng(seed)
            n = len(dates)
            factors = rng.standard_normal((n, 4))
            rows = []
            for aid in ids:
                mu, vol, load = SYNTH_ASSUMPTIONS[aid]
                load = np.array(load)
                sys = factors @ load
                sys_var = float(load @ load)
                idio_w = np.sqrt(max(1.0 - min(sys_var, 0.95), 0.05))
                z = (sys / np.sqrt(max(sys_var, 1e-9)) * np.sqrt(min(sys_var, 0.95))
                     + idio_w * rng.standard_normal(n))
                z = z / z.std()
                r = mu / 12 + vol / np.sqrt(12) * z
                rows.append(pd.DataFrame({"asset_id": aid, "date": dates, "ret": r}))
            return pd.concat(rows, ignore_index=True)
        if req.dataset == "macro.indicators":
            d = dates[-1]
            vals = {"real_gdp_growth_yoy": 1.6, "cpi_yoy": 2.9, "core_cpi_yoy": 2.8, "unemployment_rate": 4.4,
                    "unemployment_change_6m": 0.3, "policy_rate": 3.75, "policy_rate_change_6m": -0.50,
                    "ig_spread_bp": 95, "hy_spread_bp": 330, "yield_curve_10y2y_bp": 45, "pmi": 49.2}
            return pd.DataFrame([{"indicator": k, "date": d, "value": v} for k, v in vals.items()])
        if req.dataset == "fundamentals.valuation":
            return pd.DataFrame([{"asset_id": a, "date": dates[-1], "cape": c, "dividend_yield": dy,
                                  "earnings_growth": g} for a, (c, dy, g) in SYNTH_VALUATION.items() if a in ids])
        if req.dataset == "yields.current":
            return pd.DataFrame([{"asset_id": a, "date": dates[-1], "yield": y, "duration": dur,
                                  "expected_loss": el} for a, (y, dur, el) in SYNTH_YIELDS.items() if a in ids])
        raise DataUnavailable(req.dataset)


# --------------------------------------------------------------------------------------------
# File drops (Parquet/CSV) — one file per canonical dataset, e.g. data/drops/returns.monthly.parquet
# --------------------------------------------------------------------------------------------
class FileSource(DataSource):
    def _root(self) -> Path:
        from .. import REPO_ROOT
        r = Path(self.options.get("root", "./data/drops"))
        return r if r.is_absolute() else REPO_ROOT / r

    def datasets(self):
        root = self._root()
        return {p.stem for p in root.glob("*.*")} if root.exists() else set()

    def fetch(self, req: Request) -> pd.DataFrame:
        root = self._root()
        for ext, reader in ((".parquet", pd.read_parquet), (".csv", pd.read_csv)):
            p = root / f"{req.dataset}{ext}"
            if p.exists():
                df = reader(p)
                if "date" in df:
                    df["date"] = pd.to_datetime(df["date"])
                if req.assets and "asset_id" in df:
                    df = df[df["asset_id"].isin([a["id"] for a in req.assets])]
                if "_source" in df:          # cache files keep upstream provenance
                    df = df.rename(columns={"_source": "_upstream"})
                if req.end and "date" in df and req.dataset == "returns.monthly":
                    df = df[df["date"] <= pd.Timestamp(req.end) + pd.offsets.MonthEnd(0)]
                return df
        raise DataUnavailable(f"No file for {req.dataset} in {root}")


# --------------------------------------------------------------------------------------------
# Snowflake transport — works for ANY provider whose data lands in Snowflake (Marketplace share or
# internal data product). Dataset SQL + key mapping live in config/data_sources.yaml.
# --------------------------------------------------------------------------------------------
class SnowflakeSource(DataSource):
    def datasets(self):
        return set((self.cfg.get("datasets") or {}).keys())

    def _connect(self):
        try:
            import snowflake.connector  # type: ignore
        except ImportError as e:
            raise DataUnavailable("pip install 'meridian[snowflake]' to use Snowflake sources") from e
        conn_cfg = self.connections[self.cfg["connection"]]
        need = [conn_cfg["account_env"], conn_cfg["user_env"], conn_cfg["private_key_path_env"]]
        if any(not os.getenv(v) for v in need):
            raise DataUnavailable(f"Snowflake credentials not set: {need}")
        from cryptography.hazmat.primitives import serialization  # type: ignore
        key = serialization.load_pem_private_key(Path(os.environ[need[2]]).read_bytes(), password=None)
        pkb = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
        return snowflake.connector.connect(
            account=os.environ[need[0]], user=os.environ[need[1]], private_key=pkb,
            role=conn_cfg.get("role"), warehouse=conn_cfg.get("warehouse"), database=conn_cfg.get("database"))

    def fetch(self, req: Request) -> pd.DataFrame:
        spec = self.cfg["datasets"][req.dataset]
        key_field = spec.get("key_field", "snowflake_key")
        keymap = {a["identifiers"].get(key_field): a["id"] for a in req.assets if a["identifiers"].get(key_field)}
        params = {"start": req.start, "end": req.end, "as_of": req.as_of or req.end, **req.params}
        sql = spec["sql"]
        if "%(asset_keys)s" in sql:
            placeholders = ", ".join(f"%(k{i})s" for i in range(len(keymap)))
            sql = sql.replace("%(asset_keys)s", placeholders)
            params.update({f"k{i}": k for i, k in enumerate(keymap)})
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            df = cur.fetch_pandas_all()
        df.columns = [c.lower() for c in df.columns]
        if "asset_id" in df and keymap:
            df["asset_id"] = df["asset_id"].map(keymap).fillna(df["asset_id"])
        if "date" in df:
            df["date"] = pd.to_datetime(df["date"])
        return df


# --------------------------------------------------------------------------------------------
# Bloomberg direct (Desktop API / Server API via blpapi)
# --------------------------------------------------------------------------------------------
class BloombergSource(DataSource):
    def datasets(self):
        return {"returns.monthly"}

    def fetch(self, req: Request) -> pd.DataFrame:
        try:
            import blpapi  # type: ignore
        except ImportError as e:
            raise DataUnavailable("blpapi not installed / no Bloomberg terminal or B-PIPE session") from e
        field_ = self.options.get("field_total_return", "TOT_RETURN_INDEX_GROSS_DVDS")
        opts = blpapi.SessionOptions()
        opts.setServerHost(self.options.get("host", "localhost"))
        opts.setServerPort(int(self.options.get("port", 8194)))
        session = blpapi.Session(opts)
        if not session.start() or not session.openService("//blp/refdata"):
            raise DataUnavailable("Could not start Bloomberg session")
        svc = session.getService("//blp/refdata")
        rq = svc.createRequest("HistoricalDataRequest")
        tick2id = {a["identifiers"]["bloomberg"]: a["id"] for a in req.assets if a["identifiers"].get("bloomberg")}
        for t in tick2id:
            rq.getElement("securities").appendValue(t)
        rq.getElement("fields").appendValue(field_)
        rq.set("periodicitySelection", "MONTHLY")
        rq.set("startDate", pd.Timestamp(req.start or "1999-01-01").strftime("%Y%m%d"))
        rq.set("endDate", pd.Timestamp(req.end or req.as_of).strftime("%Y%m%d"))
        session.sendRequest(rq)
        rows = []
        while True:
            ev = session.nextEvent(5000)
            for msg in ev:
                if msg.hasElement("securityData"):
                    sd = msg.getElement("securityData")
                    tkr = sd.getElementAsString("security")
                    fd = sd.getElement("fieldData")
                    for i in range(fd.numValues()):
                        p = fd.getValueAsElement(i)
                        rows.append((tick2id[tkr], pd.Timestamp(p.getElementAsDatetime("date")),
                                     p.getElementAsFloat(field_)))
            if ev.eventType() == blpapi.Event.RESPONSE:
                break
        session.stop()
        lv = pd.DataFrame(rows, columns=["asset_id", "date", "level"]).sort_values(["asset_id", "date"])
        lv["ret"] = lv.groupby("asset_id")["level"].pct_change()
        return lv.dropna()[["asset_id", "date", "ret"]]


# --------------------------------------------------------------------------------------------
# FactSet direct (FactSet Prices API). Endpoint/fields to be confirmed against your subscription.
# --------------------------------------------------------------------------------------------
class FactSetSource(DataSource):
    def datasets(self):
        return {"returns.monthly"}

    def fetch(self, req: Request) -> pd.DataFrame:
        user, key = os.getenv(self.options.get("username_env", "")), os.getenv(self.options.get("api_key_env", ""))
        if not (user and key):
            raise DataUnavailable("FactSet credentials not set")
        import requests  # type: ignore
        id2a = {a["identifiers"]["factset"]: a["id"] for a in req.assets if a["identifiers"].get("factset")}
        r = requests.post(f"{self.options['base_url']}/content/factset-prices/v1/returns",
                          auth=(user, key), timeout=60,
                          json={"ids": list(id2a), "startDate": req.start, "endDate": req.end or req.as_of,
                                "frequency": "AM", "dividendAdjust": "EXDATE_C"})
        r.raise_for_status()
        df = pd.DataFrame(r.json().get("data", []))
        df = df.rename(columns={"requestId": "asset_id", "totalReturn": "ret"})
        df["asset_id"] = df["asset_id"].map(id2a)
        df["date"] = pd.to_datetime(df["date"])
        df["ret"] = df["ret"] / 100.0
        return df[["asset_id", "date", "ret"]]


# --------------------------------------------------------------------------------------------
# Generic REST adapter for rating agencies / S&P direct feeds. Each vendor's API differs and is
# licensed per contract; supply endpoint + field mapping in options once the contract is in place.
# Recommended path for Moody's / S&P / Fitch is Snowflake delivery (SnowflakeSource).
# --------------------------------------------------------------------------------------------
class RestSource(DataSource):
    def datasets(self):
        return set((self.options.get("datasets") or {}).keys())

    def fetch(self, req: Request) -> pd.DataFrame:
        base, key = os.getenv(self.options.get("base_url_env", "")), os.getenv(self.options.get("api_key_env", ""))
        spec = (self.options.get("datasets") or {}).get(req.dataset)
        if not (base and key and spec):
            raise DataUnavailable(f"{self.name}: endpoint/credentials/mapping not configured")
        import requests  # type: ignore
        r = requests.get(base + spec["path"], headers={"Authorization": f"Bearer {key}"},
                         params=spec.get("params", {}), timeout=60)
        r.raise_for_status()
        df = pd.json_normalize(r.json(), record_path=spec.get("record_path"))
        return df.rename(columns=spec.get("columns", {}))


SOURCE_TYPES = {
    ("synthetic", "generated"): SyntheticSource,
    ("file", "file"): FileSource,
    ("bloomberg", "direct"): BloombergSource,
    ("factset", "direct"): FactSetSource,
}


def build_source(name: str, cfg: dict, connections: dict) -> DataSource:
    from .public import CsvUrlSource, FredSource, ManualSource, YahooSource
    public = {"fred": FredSource, "yahoo": YahooSource, "manual": ManualSource, "csv_url": CsvUrlSource}
    if cfg.get("provider") in public:
        return public[cfg["provider"]](name, cfg, connections)
    if cfg.get("transport") == "snowflake":
        return SnowflakeSource(name, cfg, connections)
    cls = SOURCE_TYPES.get((cfg.get("provider"), cfg.get("transport")))
    if cls is None and cfg.get("transport") == "direct":
        cls = RestSource   # moodys / fitch / sp_global direct feeds
    if cls is None:
        raise ValueError(f"No adapter for provider={cfg.get('provider')} transport={cfg.get('transport')}")
    return cls(name, cfg, connections)
