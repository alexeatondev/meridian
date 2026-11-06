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

    def group_mask(self, group: str) -> np.ndarray:
        members = set(self.groups[group])
        return np.array([a in members for a in self.assets], dtype=float)


def load_policy(path: Path = POLICY_PATH) -> Policy:
    return Policy(yaml.safe_load(Path(path).read_text()))


def load_universe(path: Path = UNIVERSE_PATH) -> dict[str, dict]:
    return {a["id"]: a for a in yaml.safe_load(Path(path).read_text())["asset_classes"]}


def years_to_target(vintage: int, as_of_year_frac: float) -> float:
    return vintage - as_of_year_frac
