"""Asset hierarchy (levels 1-5) for glide-path changes and tilts: config/hierarchy.yaml."""
from __future__ import annotations

from functools import lru_cache

import yaml

from . import REPO_ROOT

PATH = REPO_ROOT / "config" / "hierarchy.yaml"
MARKET = REPO_ROOT / "config" / "market.yaml"


@lru_cache(maxsize=1)
def load() -> dict:
    return yaml.safe_load(PATH.read_text())


@lru_cache(maxsize=1)
def market() -> dict:
    """Market-cap reference mix (share of parent per hierarchy node) with sources: config/market.yaml."""
    return yaml.safe_load(MARKET.read_text()) if MARKET.exists() else {"nodes": {}}


def leaves(tree: list | None = None) -> list[str]:
    out = []
    for n in tree if tree is not None else load()["tree"]:
        out += [n["asset"]] if "asset" in n else leaves(n.get("children") or [])
    return out


def check(assets: list[str]) -> list[str]:
    """Problems: an asset class missing from the tree, or listed twice, or unknown."""
    lv = leaves()
    probs = [f"{a}: missing from config/hierarchy.yaml" for a in assets if a not in lv]
    probs += [f"{a}: listed {lv.count(a)} times" for a in set(lv) if lv.count(a) > 1]
    probs += [f"{a}: not a policy asset class" for a in set(lv) if a not in assets]
    return probs
