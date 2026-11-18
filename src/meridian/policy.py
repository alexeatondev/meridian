"""Policy-as-code loader and target-date glide path."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from . import REPO_ROOT

POLICY_PATH = REPO_ROOT / "policies" / "target_date_series.yaml"
UNIVERSE_PATH = REPO_ROOT / "config" / "universe.yaml"


@dataclass
class Policy:
    raw: dict

    @property
    def id(self) -> str:
        return f"{self.raw['policy_id']}@{self.raw['version']}"

    @property
    def assets(self) -> list[str]:
        return list(self.raw["glide_path"]["asset_order"])

    @property
    def groups(self) -> dict[str, list[str]]:
        return self.raw["groups"]

    @property
    def rules(self) -> list[dict]:
        return self.raw["rules"]

    @property
    def vintages(self) -> list[int]:
        return list(self.raw["series"]["vintages"])

    def neutral_weights(self, years_to_target: float) -> np.ndarray:
        """Strategic (glide path) weights for a given number of years to the target date."""
        anchors = np.array(self.raw["glide_path"]["anchors"], dtype=float)
        anchors = anchors[np.argsort(anchors[:, 0])]  # ascending years
        yrs, w = anchors[:, 0], anchors[:, 1:] / 100.0
        y = float(np.clip(years_to_target, yrs.min(), yrs.max()))
        out = np.array([np.interp(y, yrs, w[:, j]) for j in range(w.shape[1])])
        return out / out.sum()

    def glide_adjustment(self, vintage: int) -> dict:
        """Investment Committee glide-path adjustments approved in the app (exported into the policy file as
        `glide_adjustments` before an agent run). Returns {"delta": vector to add to the IPS glide path,
        "by_line": {line: {asset: pp}}, "ids": [...], "lines_differ": bool}. Shifts are funded, so each line's
        delta sums to zero. When the mutual fund and CIT lines differ, the run builds on their average and
        the Trading screen adds each line's own difference to the approved proposal."""
        ga = (self.raw.get("glide_adjustments") or {}).get("vintages") or {}
        d = ga.get(vintage) or ga.get(str(vintage)) or {}
        lines = {k: {a: float(x) for a, x in (v or {}).items()} for k, v in (d.get("by_line") or {}).items()}
        if not lines:
            return {"delta": np.zeros(len(self.assets)), "by_line": {}, "ids": [], "lines_differ": False}
        vecs = [np.array([lines[k].get(a, 0.0) for a in self.assets]) for k in sorted(lines)]
        unknown = sorted({a for v in lines.values() for a in v} - set(self.assets))
        if unknown:
            raise ValueError(f"glide_adjustments for {vintage}: unknown asset classes {unknown}")
        return {"delta": np.mean(vecs, axis=0), "by_line": lines, "ids": list(d.get("ids") or []),
                "lines_differ": any(not np.allclose(vecs[0], x, atol=1e-9) for x in vecs[1:]),
                "labels": list(d.get("labels") or [])}

    def adjusted_neutral(self, years_to_target: float, vintage: int) -> tuple[np.ndarray, np.ndarray, dict]:
        """(glide path including approved adjustments, IPS glide path, adjustment info)."""
        ips = self.neutral_weights(years_to_target)
        adj = self.glide_adjustment(vintage)
        n = np.clip(ips + adj["delta"], 0, None)
        return n / n.sum(), ips, adj

    def risk_budget(self, vintage: int) -> float:
        rb = self.raw.get("risk_budgets") or {}
        hard = float(rb.get("hard_max", self.raw["risk_objectives"]["tracking_error_budget_vs_neutral"]))
        v = (rb.get("vintages") or {}).get(vintage, (rb.get("vintages") or {}).get(str(vintage), rb.get("default", hard)))
        return min(float(v), hard)

    def group_mask(self, group: str) -> np.ndarray:
        members = set(self.groups[group])
        return np.array([a in members for a in self.assets], dtype=float)


def load_policy(path: Path = POLICY_PATH) -> Policy:
    return Policy(yaml.safe_load(Path(path).read_text()))


def load_universe(path: Path = UNIVERSE_PATH) -> dict[str, dict]:
    return {a["id"]: a for a in yaml.safe_load(Path(path).read_text())["asset_classes"]}


def years_to_target(vintage: int, as_of_year_frac: float) -> float:
    return vintage - as_of_year_frac
