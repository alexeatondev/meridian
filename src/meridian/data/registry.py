"""Routes canonical dataset requests to one or many sources and snapshots the result.

Routing modes (config/data_sources.yaml -> routing.<dataset>):
  - list of sources            -> mode "first": first enabled source that succeeds serves everything.
  - {mode: merge, sources: [...]} -> every enabled source is asked; results are combined by key with the
    earlier source winning. Time series fill gaps in time (e.g. Yahoo for recent years, a cache or another
    vendor for older history); snapshots fill gaps per column (e.g. CAPE from manual inputs, dividend yield
    from a vendor). Every row carries `_source`, so lineage shows exactly which source supplied what.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from .. import REPO_ROOT
from .base import CANONICAL, MERGE_KEYS, TIME_SERIES, DataUnavailable, Request, Result, validate
from .providers import build_source

CONFIG_PATH = REPO_ROOT / "config" / "data_sources.yaml"


def route_spec(cfg: dict, dataset: str) -> tuple[str, list[str], list[str]]:
    """Returns (mode, sources, fallback). Fallback sources are used only for what the main sources could not
    supply: whole missing assets for time series (never to patch holes inside a real history), and missing
    keys/fields for snapshots."""
    r = cfg["routing"].get(dataset, [])
    if isinstance(r, dict):
        return r.get("mode", "first"), list(r.get("sources", [])), list(r.get("fallback", []))
    return "first", list(r), []


def merge_frames(dataset: str, frames: list[pd.DataFrame]) -> pd.DataFrame:
    keys = MERGE_KEYS[dataset]
    if dataset in TIME_SERIES:
        df = pd.concat(frames, ignore_index=True)
        return df.drop_duplicates(subset=keys, keep="first").sort_values(keys).reset_index(drop=True)
    # snapshot datasets: per-key, per-column coalesce in priority order
    out: dict[tuple, dict] = {}
    for f in frames:
        for rec in f.to_dict("records"):
            k = tuple(rec[c] for c in keys)
            cur = out.setdefault(k, {"_source": rec["_source"], "_fields": {}})
            for col, val in rec.items():
                if col in ("_source",):
                    continue
                if cur.get(col) is None or (isinstance(cur.get(col), float) and pd.isna(cur.get(col))):
                    if val is not None and not (isinstance(val, float) and pd.isna(val)):
                        cur[col] = val
                        if col not in keys:
                            cur["_fields"][col] = rec["_source"]
    rows = []
    for rec in out.values():
        srcs = sorted(set(rec.pop("_fields").values())) or [rec["_source"]]
        rec["_source"] = "+".join(srcs)
        rows.append(rec)
    return pd.DataFrame(rows)


@dataclass
class DataRegistry:
    cfg: dict
    attempts: list[dict] = field(default_factory=list)

    @classmethod
    def from_config(cls, path: Path = CONFIG_PATH, overrides: dict | None = None) -> "DataRegistry":
        cfg = yaml.safe_load(Path(path).read_text())
        for name, enabled in (overrides or {}).items():
            cfg["sources"][name]["enabled"] = enabled
        return cls(cfg)

    def sources(self):
        conns = self.cfg.get("connections", {})
        return {n: build_source(n, c, conns) for n, c in self.cfg["sources"].items()}

    def _try(self, srcs, name, req, exclude_transports):
        if name not in srcs:
            self.attempts.append({"dataset": req.dataset, "source": name, "status": "not configured"})
            return None
        s = srcs[name]
        if not s.enabled or not s.supports(req.dataset) or (exclude_transports and s.transport in exclude_transports):
            self.attempts.append({"dataset": req.dataset, "source": name, "status": "skipped"})
            return None
        try:
            res = s.result(req)
        except DataUnavailable as e:
            self.attempts.append({"dataset": req.dataset, "source": name, "status": f"unavailable: {str(e)[:300]}"})
            return None
        warn = res.frame.attrs.get("warnings")
        self.attempts.append({"dataset": req.dataset, "source": name, "status": "ok", "rows": len(res.frame),
                              "synthetic": res.synthetic, **({"warnings": warn[:5]} if warn else {})})
        return res

    def get(self, req: Request, exclude_transports: set[str] | None = None) -> Result:
        srcs = self.sources()
        mode, route, fallback = route_spec(self.cfg, req.dataset)
        got: list[Result] = []
        for name in route:
            res = self._try(srcs, name, req, exclude_transports)
            if res is not None:
                got.append(res)
                if mode == "first":
                    break
        # fallback tier: only for assets/keys the main sources did not cover
        if fallback:
            covered = set()
            if got and "asset_id" in got[0].frame:
                covered = set(pd.concat([g.frame for g in got])["asset_id"].unique())
            missing_assets = [a for a in req.assets if a["id"] not in covered]
            need = (not got) or (missing_assets if req.dataset in TIME_SERIES else True)
            if need:
                freq = req if (not got or req.dataset not in TIME_SERIES) else Request(
                    req.dataset, missing_assets, req.start, req.end, req.as_of, req.params)
                for name in fallback:
                    res = self._try(srcs, name, freq, exclude_transports)
                    if res is not None:
                        got.append(res)
                        break
        if not got:
            raise DataUnavailable(f"No source could serve {req.dataset}; tried {route + fallback}")
        df = got[0].frame if len(got) == 1 else merge_frames(req.dataset, [g.frame for g in got])
        validate(req.dataset, df)
        synth_names = {g.source for g in got if g.synthetic}
        contrib = df["_source"].value_counts().to_dict()
        synthetic_rows = int(sum(n for s, n in contrib.items() if any(x in synth_names for x in s.split("+"))))
        synthetic_assets = sorted(df.loc[df["_source"].str.contains("|".join(synth_names)), "asset_id"].unique().tolist()) \
            if synth_names and "asset_id" in df else []
        lead = got[0]
        return Result(df, "+".join(g.source for g in got), lead.provider, lead.transport,
                      synthetic=synthetic_rows > 0, sources=contrib,
                      notes=f"mode={mode}; synthetic_rows={synthetic_rows}/{len(df)}"
                            + (f"; synthetic_assets={synthetic_assets}" if synthetic_assets else ""))

    def status(self) -> list[dict]:
        out = []
        for n, s in self.sources().items():
            try:
                ds = sorted(s.datasets())
            except Exception:  # noqa: BLE001
                ds = []
            out.append({"source": n, "provider": s.provider, "transport": s.transport, "enabled": s.enabled,
                        "datasets": ds, "license_review": self.cfg.get("license_review", {}).get(s.provider, "n/a")})
        return out


def snapshot(results: dict[str, Result], out_dir: Path) -> dict:
    """Persist fetched data and return a manifest with content hashes (the run's data snapshot)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for ds, res in results.items():
        p = out_dir / f"{ds}.csv"
        res.frame.to_csv(p, index=False)
        manifest[ds] = {"source": res.source, "provider": res.provider, "transport": res.transport,
                        "synthetic": res.synthetic, "rows": len(res.frame), "contributions": res.sources,
                        "notes": res.notes, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    snap_id = "snap_" + hashlib.sha256(json.dumps(manifest, sort_keys=True, default=str).encode()).hexdigest()[:16]
    (out_dir / "manifest.json").write_text(json.dumps({"snapshot_id": snap_id, "datasets": manifest}, indent=2, default=str))
    return {"snapshot_id": snap_id, "datasets": manifest}


def to_wide_returns(df: pd.DataFrame, order: list[str]) -> pd.DataFrame:
    w = df.pivot_table(index="date", columns="asset_id", values="ret").sort_index()
    return w[order].dropna()


__all__ = ["CANONICAL", "DataRegistry", "snapshot", "to_wide_returns", "route_spec", "merge_frames"]
