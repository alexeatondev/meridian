"""Named glide paths (doc 17 §9, doc 07 §6).

A glide path is a table of anchors: years to the target date -> weight (%) per asset class, in the policy's
asset order. Weights between anchors are interpolated in a straight line, exactly like the IPS glide path in
the policy file. The IPS path ("ips") is the default every fund follows; the Investment Committee can approve
other named paths, version them and assign them to funds. The IPS bands are measured around the fund's path.
"""
from __future__ import annotations

import numpy as np

IPS_ID = "ips"


def interp(anchors: list[list[float]], years: float) -> np.ndarray:
    a = np.array(anchors, dtype=float)
    a = a[np.argsort(a[:, 0])]
    yrs, w = a[:, 0], a[:, 1:] / 100.0
    y = float(np.clip(years, yrs.min(), yrs.max()))
    out = np.array([np.interp(y, yrs, w[:, j]) for j in range(w.shape[1])])
    return out / out.sum()


def clean_anchors(anchors, n_assets: int) -> list[list[float]]:
    """Validate an anchor table. Raises ValueError with a message a person can act on."""
    if not isinstance(anchors, list) or len(anchors) < 2:
        raise ValueError("A glide path needs at least two anchor rows (for example 40 years and 0 years)")
    if len(anchors) > 30:
        raise ValueError("At most 30 anchor rows")
    out, seen = [], set()
    for i, row in enumerate(anchors, 1):
        if not isinstance(row, (list, tuple)) or len(row) != n_assets + 1:
            raise ValueError(f"Row {i}: expected years plus {n_assets} weights")
        try:
            vals = [float(x) for x in row]
        except (TypeError, ValueError):
            raise ValueError(f"Row {i}: every cell must be a number") from None
        y = vals[0]
        if not -30 <= y <= 60:
            raise ValueError(f"Row {i}: years to target must be between -30 and 60")
        if y in seen:
            raise ValueError(f"Row {i}: {y:g} years appears twice")
        seen.add(y)
        w = vals[1:]
        if any(x < 0 for x in w):
            raise ValueError(f"Row {i} ({y:g} years): weights can't be negative")
        if abs(sum(w) - 100) > 0.05:
            raise ValueError(f"Row {i} ({y:g} years): weights add to {sum(w):.2f}%, not 100%")
        out.append([round(y, 2)] + [round(x, 4) for x in w])
    return sorted(out, key=lambda r: -r[0])


def max_difference(anchors: list[list[float]], ips: list[list[float]], assets: list[str],
                   groups: dict[str, list[str]] | None = None) -> dict:
    """Largest gap between a path and the IPS path across years -10..45 (per asset and for equity)."""
    worst = {"pp": 0.0, "asset": "", "years": None, "equity_pp": 0.0, "equity_years": None}
    eq = [i for i, a in enumerate(assets) if a in set((groups or {}).get("equity", []))]
    for y in range(-10, 46):
        d = (interp(anchors, y) - interp(ips, y)) * 100
        j = int(np.argmax(np.abs(d)))
        if abs(d[j]) > abs(worst["pp"]):
            worst.update(pp=round(float(d[j]), 2), asset=assets[j], years=y)
        e = float(d[eq].sum()) if eq else 0.0
        if abs(e) > abs(worst["equity_pp"]):
            worst.update(equity_pp=round(e, 2), equity_years=y)
    return worst


def equity_curve(anchors: list[list[float]], assets: list[str], groups: dict, years=range(45, -11, -1)) -> list[list[float]]:
    eq = [i for i, a in enumerate(assets) if a in set(groups.get("equity", []))]
    return [[y, round(float(interp(anchors, y)[eq].sum()), 4)] for y in years]
