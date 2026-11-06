"""Provider-agnostic data contracts.

Every provider, whatever the transport, returns pandas DataFrames in these canonical shapes.
Agents and analytics only ever see canonical data, so providers can be swapped freely.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd

# canonical dataset -> required columns
CANONICAL = {
    "returns.monthly": ["asset_id", "date", "ret"],                       # total return, decimal
    "macro.indicators": ["indicator", "date", "value"],
    "fundamentals.valuation": ["asset_id", "date", "cape", "dividend_yield", "earnings_growth"],
    "credit.ratings": ["entity_id", "agency", "rating", "outlook", "date"],
    "yields.current": ["asset_id", "date", "yield", "duration", "expected_loss"],
    # risk characteristics of each building-block fund (years); vendor feeds may add yield, oas, rating
    "fund.characteristics": ["asset_id", "date", "eff_duration", "spread_duration"],
    # look-through holdings of each building-block fund; weight = fraction of that fund (decimal).
    # Optional columns: ticker, asset_class, sector, country, duration, lines (positions aggregated)
    "holdings.lookthrough": ["asset_id", "fund_ticker", "date", "security_id", "name", "weight"],
}


# keys used to merge rows from several sources (higher-priority source wins per key)
MERGE_KEYS = {
    "returns.monthly": ["asset_id", "date"],
    "macro.indicators": ["indicator"],
    "fundamentals.valuation": ["asset_id"],
    "credit.ratings": ["entity_id", "agency"],
    "yields.current": ["asset_id"],
    "fund.characteristics": ["asset_id"],
    "holdings.lookthrough": ["asset_id", "fund_ticker", "security_id"],
}
TIME_SERIES = {"returns.monthly"}


class DataUnavailable(RuntimeError):
    """Raised when a source cannot serve a request (not configured, no creds, no coverage)."""


@dataclass
class Request:
    dataset: str
    assets: list[dict] = field(default_factory=list)   # universe entries (carry identifiers)
    start: str | None = None
    end: str | None = None
    as_of: str | None = None
    params: dict = field(default_factory=dict)


@dataclass
class Result:
    frame: pd.DataFrame
    source: str
    provider: str
    transport: str
    synthetic: bool = False
    notes: str = ""
    sources: dict = field(default_factory=dict)   # source name -> rows (or columns) contributed


class DataSource(ABC):
    def __init__(self, name: str, cfg: dict, connections: dict | None = None):
        self.name, self.cfg = name, cfg
        self.provider = cfg.get("provider", name)
        self.transport = cfg.get("transport", "direct")
        self.options = cfg.get("options", {}) or {}
        self.connections = connections or {}

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled", False))

    def supports(self, dataset: str) -> bool:
        return dataset in self.datasets()

    @abstractmethod
    def datasets(self) -> set[str]: ...

    @abstractmethod
    def fetch(self, req: Request) -> pd.DataFrame: ...

    def result(self, req: Request) -> Result:
        df = self.fetch(req)
        if df is None or df.empty:
            raise DataUnavailable(f"{self.name}: empty result for {req.dataset}")
        missing_keys = [k for k in MERGE_KEYS[req.dataset] if k not in df.columns]
        if missing_keys:
            raise DataUnavailable(f"{self.name}: frame missing key columns {missing_keys}")
        df = df.copy()
        df["_source"] = self.name
        return Result(df, self.name, self.provider, self.transport, synthetic=self.transport == "generated",
                      sources={self.name: len(df)})


def validate(dataset: str, df: pd.DataFrame) -> None:
    missing = [c for c in CANONICAL[dataset] if c not in df.columns]
    if missing:
        raise ValueError(f"{dataset}: provider returned frame missing columns {missing}")
    if df.empty:
        raise DataUnavailable(f"{dataset}: empty result")
