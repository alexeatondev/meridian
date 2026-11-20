"""Info bubbles: plain-language help for metrics, columns and buttons (config/glossary.yaml)."""
from __future__ import annotations

from functools import lru_cache

import yaml

from . import REPO_ROOT

PATH = REPO_ROOT / "config" / "glossary.yaml"


@lru_cache(maxsize=1)
def load() -> dict[str, dict]:
    return yaml.safe_load(PATH.read_text()) if PATH.exists() else {}


def check() -> list[str]:
    """Problems: an entry without a title, text or labels, or a label claimed by two entries."""
    probs, seen = [], {}
    for k, e in load().items():
        for f in ("title", "text", "match"):
            if not e.get(f):
                probs.append(f"{k}: missing {f}")
        for m in e.get("match") or []:
            key = str(m).strip().rstrip(":").lower()
            if key in seen:
                probs.append(f"label '{m}' is in both {seen[key]} and {k}")
            seen[key] = k
    return probs
