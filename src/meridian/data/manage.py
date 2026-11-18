"""Plug/unplug sources and refresh the point-in-time cache. Edits keep comments in data_sources.yaml."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .. import REPO_ROOT
from ..policy import load_universe
from .base import DataUnavailable, Request
from .public import write_cache
from .registry import CONFIG_PATH, DataRegistry

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.width = 200

REFRESH_DATASETS = ["returns.monthly", "macro.indicators", "yields.current", "fundamentals.valuation",
                    "fund.characteristics", "holdings.lookthrough", "fundamentals.edgar"]


def _load(path: Path = CONFIG_PATH):
    with open(path) as f:
        return _yaml.load(f)


def _save(doc, path: Path = CONFIG_PATH):
    with open(path, "w") as f:
        _yaml.dump(doc, f)


def set_enabled(name: str, enabled: bool, path: Path = CONFIG_PATH) -> None:
    doc = _load(path)
    if name not in doc["sources"]:
        raise SystemExit(f"Unknown source '{name}'. Known: {', '.join(doc['sources'])}")
    doc["sources"][name]["enabled"] = enabled
    _save(doc, path)


def set_route(dataset: str, sources: list[str], mode: str = "merge", fallback: list[str] | None = None,
              path: Path = CONFIG_PATH) -> None:
    doc = _load(path)
    unknown = [s for s in sources + (fallback or []) if s not in doc["sources"]]
    if unknown:
        raise SystemExit(f"Unknown source(s): {unknown}")
    if mode == "first" and not fallback:
        doc["routing"][dataset] = CommentedSeq(sources)
    else:
        m = CommentedMap()
        m["mode"], m["sources"] = mode, CommentedSeq(sources)
        if fallback:
            m["fallback"] = CommentedSeq(fallback)
        doc["routing"][dataset] = m
    _save(doc, path)


def add_source(name: str, provider: str, transport: str, options: dict | None = None, enabled: bool = True,
               path: Path = CONFIG_PATH) -> None:
    doc = _load(path)
    if name in doc["sources"]:
        raise SystemExit(f"Source '{name}' already exists")
    m = CommentedMap()
    m["provider"], m["transport"], m["enabled"] = provider, transport, enabled
    if options:
        m["options"] = options
    doc["sources"][name] = m
    _save(doc, path)


def test_source(name: str, as_of: str | None = None) -> list[dict]:
    reg = DataRegistry.from_config()
    src = reg.sources()[name]
    u = list(load_universe().values())
    as_of = as_of or datetime.now(timezone.utc).date().isoformat()
    out = []
    for ds in sorted(src.datasets()):
        try:
            df = src.result(Request(ds, u, start="2020-01-31", end=as_of, as_of=as_of)).frame
            keys = df["asset_id"].nunique() if "asset_id" in df else len(df)
            out.append({"dataset": ds, "status": "ok", "rows": len(df), "keys": int(keys),
                        "warnings": (df.attrs.get("warnings") or [])[:3]})
        except DataUnavailable as e:
            out.append({"dataset": ds, "status": f"unavailable: {e}"})
    return out


def refresh(as_of: str | None = None, root: Path | None = None, start: str = "1990-01-31") -> dict:
    """Fetch every dataset from live sources only (no cache, no synthetic) and write data/cache.
    A dataset that fails keeps its previous cache file. Git history of data/cache = point-in-time record."""
    as_of = as_of or datetime.now(timezone.utc).date().isoformat()
    root = root or REPO_ROOT / "data" / "cache"
    reg = DataRegistry.from_config()
    u = list(load_universe().values())
    frames, status = {}, {}
    for ds in REFRESH_DATASETS:
        try:
            r = reg.get(Request(ds, u, start=start, end=as_of, as_of=as_of), exclude_transports={"file", "generated"})
            df = r.frame
            if ds == "returns.monthly":  # only complete months
                df = df[df["date"] <= pd.Timestamp(as_of) - pd.offsets.MonthEnd(1) + pd.offsets.MonthEnd(0)]
            frames[ds] = df
            status[ds] = {"status": "ok", "rows": len(df), "sources": r.sources}
        except DataUnavailable as e:
            status[ds] = {"status": f"kept previous cache: {e}"}
    meta = {"refreshed_at": datetime.now(timezone.utc).isoformat(), "as_of": as_of, "datasets": status,
            "attempts": reg.attempts}
    if frames:
        write_cache(frames, root, meta)
    return meta
