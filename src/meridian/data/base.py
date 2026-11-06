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
}


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
        validate(req.dataset, df)
        return Result(df, self.name, self.provider, self.transport, synthetic=self.transport == "generated")


def validate(dataset: str, df: pd.DataFrame) -> None:
    missing = [c for c in CANONICAL[dataset] if c not in df.columns]
    if missing:
        raise ValueError(f"{dataset}: provider returned frame missing columns {missing}")
    if df.empty:
        raise DataUnavailable(f"{dataset}: empty result")
