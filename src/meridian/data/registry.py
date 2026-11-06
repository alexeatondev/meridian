"""Routes canonical dataset requests to the first available source; snapshots results."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from .. import REPO_ROOT
from .base import DataUnavailable, Request, Result
from .providers import build_source

CONFIG_PATH = REPO_ROOT / "config" / "data_sources.yaml"


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

    def get(self, req: Request) -> Result:
        srcs = self.sources()
        route = self.cfg["routing"].get(req.dataset, [])
        for name in route:
            s = srcs[name]
            if not s.enabled or not s.supports(req.dataset):
                self.attempts.append({"dataset": req.dataset, "source": name, "status": "skipped"})
                continue
            try:
                res = s.result(req)
                self.attempts.append({"dataset": req.dataset, "source": name, "status": "ok",
                                      "synthetic": res.synthetic})
                return res
            except DataUnavailable as e:
                self.attempts.append({"dataset": req.dataset, "source": name, "status": f"unavailable: {e}"})
        raise DataUnavailable(f"No source could serve {req.dataset}; tried {route}")

    def status(self) -> list[dict]:
        out = []
        for n, s in self.sources().items():
            out.append({"source": n, "provider": s.provider, "transport": s.transport, "enabled": s.enabled,
                        "datasets": sorted(s.datasets()) if s.transport != "file" else "per-file",
                        "license_review": self.cfg.get("license_review", {}).get(s.provider, "n/a")})
        return out


def snapshot(results: dict[str, Result], out_dir: Path) -> dict:
    """Persist fetched data and return a manifest with content hashes (the run's data snapshot)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for ds, res in results.items():
        p = out_dir / f"{ds}.csv"
        res.frame.to_csv(p, index=False)
        manifest[ds] = {"source": res.source, "provider": res.provider, "transport": res.transport,
                        "synthetic": res.synthetic, "rows": len(res.frame),
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    snap_id = "snap_" + hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    (out_dir / "manifest.json").write_text(json.dumps({"snapshot_id": snap_id, "datasets": manifest}, indent=2))
    return {"snapshot_id": snap_id, "datasets": manifest}


def to_wide_returns(df: pd.DataFrame, order: list[str]) -> pd.DataFrame:
    w = df.pivot_table(index="date", columns="asset_id", values="ret").sort_index()
    return w[order].dropna()
