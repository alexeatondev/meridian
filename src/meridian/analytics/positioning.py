"""Look-through positioning, risk-budget usage, portfolio metrics and weight adjustments.

Nodes are slash-joined paths of the taxonomy tree, e.g. "Equity", "Equity/Non-US/Emerging",
"Fixed Income/Short-dated/TIPS". Pivot views group leaves by a tag instead (e.g. size, maturity).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .. import REPO_ROOT

TAXONOMY_PATH = REPO_ROOT / "config" / "taxonomy.yaml"


@dataclass
class Taxonomy:
    raw: dict
    assets: list[str]

    @classmethod
    def load(cls, assets: list[str], path: Path = TAXONOMY_PATH) -> "Taxonomy":
        raw = yaml.safe_load(Path(path).read_text())
        for a in assets:
            fr = sum(l["fraction"] for l in raw["funds"].get(a, []))
            if abs(fr - 1) > 1e-9:
                raise ValueError(f"taxonomy: fractions for {a} sum to {fr}, expected 1")
        return cls(raw, assets)

    @property
    def leaves(self) -> list[dict]:
        out = []
        for a in self.assets:
            for l in self.raw["funds"][a]:
                out.append({"asset": a, "fraction": l["fraction"], "path": l["path"], "tags": l.get("tags", {})})
        return out

    def node_names(self) -> list[str]:
        """Depth-first order: each parent followed by its children (children in first-seen order)."""
        children: dict[str, list[str]] = {"": []}
        for l in self.leaves:
            for i in range(1, len(l["path"]) + 1):
                n, parent = "/".join(l["path"][:i]), "/".join(l["path"][:i - 1])
                children.setdefault(parent, [])
                if n not in children[parent]:
                    children[parent].append(n)
                children.setdefault(n, [])
        tops = [t for t in self.raw.get("top_levels", []) if t in children[""]] + \
               [t for t in children[""] if t not in self.raw.get("top_levels", [])]
        out: list[str] = []

        def walk(n):
            out.append(n)
            for c in children[n]:
                walk(c)
        for t in tops:
            walk(t)
        return out

    def node_matrix(self, nodes: list[str] | None = None) -> tuple[list[str], np.ndarray]:
        """M[node, asset] = fraction of the asset's weight that sits in the node."""
        nodes = nodes or self.node_names()
        M = np.zeros((len(nodes), len(self.assets)))
        for l in self.leaves:
            j = self.assets.index(l["asset"])
            for i in range(1, len(l["path"]) + 1):
                n = "/".join(l["path"][:i])
                if n in nodes:
                    M[nodes.index(n), j] += l["fraction"]
        return nodes, M

    def pivot_matrix(self, view: str) -> tuple[list[str], np.ndarray]:
        v = self.raw["views"][view]
        if v["by"] == "path":
            return self.node_matrix()
        groups = []
        for l in self.leaves:
            if l["path"][0] == v["filter"] and l["tags"].get(v["by"]) and l["tags"][v["by"]] not in groups:
                groups.append(l["tags"][v["by"]])
        M = np.zeros((len(groups), len(self.assets)))
        for l in self.leaves:
            if l["path"][0] == v["filter"] and l["tags"].get(v["by"]) in groups:
                M[groups.index(l["tags"][v["by"]]), self.assets.index(l["asset"])] += l["fraction"]
        return groups, M

    def market_weights(self) -> np.ndarray:
        mw = self.raw["market_benchmark"]["weights"]
        w = np.array([mw.get(a, 0.0) for a in self.assets])
        return w / w.sum()


# ---------------------------------------------------------------------------------------- risk budget
def active_risk_contributions(w, bench, cov) -> tuple[float, np.ndarray]:
    d = np.asarray(w) - np.asarray(bench)
    te2 = float(d @ cov @ d)
    if te2 <= 0:
        return 0.0, np.zeros_like(d)
    te = te2 ** 0.5
    return te, d * (cov @ d) / te                      # contributions sum to TE


def total_risk_contributions(w, cov) -> np.ndarray:
    w = np.asarray(w)
    v = float(np.sqrt(w @ cov @ w))
    return w * (cov @ w) / v if v > 0 else w * 0


# ---------------------------------------------------------------------------------------- positioning
def positioning_table(tax: Taxonomy, cols: dict[str, np.ndarray], cov, neutral, te_budget: float,
                      view: str = "asset_class_tree") -> list[dict]:
    """Rows per node with each column's weight, active vs market, relative % vs market, and
    % of risk budget used (node's share of active risk vs the glide path, over the budget)."""
    names, M = tax.pivot_matrix(view)
    cur = cols["current"]
    te, c = active_risk_contributions(cur, neutral, cov)
    tot = total_risk_contributions(cur, cov)
    vol = float(np.sqrt(cur @ cov @ cur))
    rows = []
    for i, n in enumerate(names):
        r = {"node": n, "depth": n.count("/") if tax.raw["views"][view]["by"] == "path" else 0}
        for k, w in cols.items():
            r[k] = float(M[i] @ w)
        mkt = r.get("market", 0.0)
        r["active_vs_market"] = r["current"] - mkt
        r["relative_vs_market"] = (r["current"] / mkt - 1) if mkt > 1e-9 else None
        r["active_vs_glide"] = r["current"] - r.get("glide_path", 0.0)
        r["active_risk"] = float(M[i] @ c)
        r["risk_budget_used"] = float(M[i] @ c) / te_budget if te_budget else None
        r["share_of_total_risk"] = float(M[i] @ tot) / vol if vol else None
        rows.append(r)
    return rows


# ---------------------------------------------------------------------------------------- metrics
def portfolio_metrics(w, rets: pd.DataFrame, market_w, bench_w, rf: pd.Series | None, months: int | None = None) -> dict:
    R = rets.iloc[-months:] if months else rets
    p, m, b = R.values @ np.asarray(w), R.values @ np.asarray(market_w), R.values @ np.asarray(bench_w)
    rfv = (rf.reindex(R.index).fillna(rf.mean()).values if rf is not None else np.zeros(len(R)))
    ex_p, ex_m = p - rfv, m - rfv
    beta = float(np.cov(ex_p, ex_m)[0, 1] / np.var(ex_m, ddof=1))
    alpha = float((ex_p.mean() - beta * ex_m.mean()) * 12)
    ann = lambda x: float(np.prod(1 + x) ** (12 / len(x)) - 1)
    vol = float(p.std(ddof=1) * np.sqrt(12))
    downside = ex_p[ex_p < 0]
    wealth = np.cumprod(1 + p)
    up, dn = m > 0, m < 0
    te_m = float((p - m).std(ddof=1) * np.sqrt(12))
    te_b = float((p - b).std(ddof=1) * np.sqrt(12))
    return {
        "window_months": len(R), "start": str(R.index[0].date()), "end": str(R.index[-1].date()),
        "ann_return": ann(p), "ann_vol": vol, "sharpe": float(ex_p.mean() * 12 / vol) if vol else None,
        "sortino": float(ex_p.mean() * 12 / (np.sqrt((downside ** 2).mean()) * np.sqrt(12))) if len(downside) else None,
        "max_drawdown": float((wealth / np.maximum.accumulate(wealth) - 1).min()),
        "beta_vs_market": beta, "alpha_vs_market": alpha,
        "correlation_vs_market": float(np.corrcoef(p, m)[0, 1]), "r_squared": float(np.corrcoef(p, m)[0, 1] ** 2),
        "tracking_error_vs_market": te_m, "info_ratio_vs_market": float((p - m).mean() * 12 / te_m) if te_m else None,
        "tracking_error_vs_glide": te_b, "info_ratio_vs_glide": float((p - b).mean() * 12 / te_b) if te_b else None,
        "up_capture": float(p[up].mean() / m[up].mean()) if up.any() else None,
        "down_capture": float(p[dn].mean() / m[dn].mean()) if dn.any() else None,
        "market_ann_return": ann(m),
    }


# ---------------------------------------------------------------------------------------- adjustments
def node_row(tax: Taxonomy, n: str) -> np.ndarray:
    """Exposure row for a taxonomy node, or 'asset:<id>' for a single fund."""
    if n.startswith("asset:"):
        a = n.split(":", 1)[1]
        if a not in tax.assets:
            raise ValueError(f"Unknown asset '{a}'")
        return np.array([1.0 if x == a else 0.0 for x in tax.assets])
    names, M = tax.node_matrix()
    if n not in names:
        raise ValueError(f"Unknown node '{n}'. Examples: {names[:6]}")
    return M[names.index(n)]


def adjustment_constraints(w, tax: Taxonomy, node: str, mode: str, value: float, funded_from: str | None = None):
    """Linear constraints A w = b describing the requested change.
    - the node moves to its target (absolute) or by `value` (relative);
    - with `funded_from`, the funding node gives exactly that amount and every top-level group not involved is held;
    - weights sum to 1. Rows that are implied by others are dropped."""
    w = np.asarray(w, float)
    r = node_row(tax, node)
    cur = float(r @ w)
    delta = (value - cur) if mode == "absolute" else value
    rows, b = [r], [cur + delta]
    if funded_from:
        f = node_row(tax, funded_from)
        def _is_asset(x): return x.startswith("asset:")
        if (not _is_asset(node) and not _is_asset(funded_from)
                and (node == funded_from or node.startswith(funded_from + "/") or funded_from.startswith(node + "/"))):
            raise ValueError("node and funded_from overlap")
        if _is_asset(node) != _is_asset(funded_from):
            a, other = (node, funded_from) if _is_asset(node) else (funded_from, node)
            if node_row(tax, other)[tax.assets.index(a.split(":", 1)[1])] > 0:
                raise ValueError("node and funded_from overlap")
        if delta > float(f @ w) + 1e-12:
            raise ValueError(f"Funding node has only {float(f @ w):.2%} to give")
        rows.append(f); b.append(float(f @ w) - delta)
        for t in tax.raw["top_levels"]:
            tr = node_row(tax, t)
            if not ((tr * r).any() or (tr * f).any()):
                rows.append(tr); b.append(float(tr @ w))
    if cur + delta < -1e-12:
        raise ValueError(f"Cannot reduce '{node}' by more than its weight ({cur:.2%})")
    rows.append(np.ones(len(w))); b.append(1.0)
    A, bb = np.array(rows), np.array(b)
    # drop linearly dependent rows (keep the earlier ones)
    keep = []
    for i in range(len(A)):
        if np.linalg.matrix_rank(A[keep + [i]]) == len(keep) + 1:
            keep.append(i)
    return A[keep], bb[keep], delta


def _min_norm_active_set(w, A, b, max_iter: int = 30):
    """Minimum-norm change subject to A x = b, with funds that would go negative pinned at zero and the
    problem re-solved (simple active set). Mirrors the Console preview exactly."""
    n = len(w)
    zero: list[int] = []
    for _ in range(max_iter):
        rows = [*A] + [np.eye(n)[i] for i in zero]
        rhs = [*b] + [0.0] * len(zero)
        Z = np.array(rows)
        keep = []
        for i in range(len(Z)):
            if np.linalg.matrix_rank(Z[keep + [i]]) == len(keep) + 1:
                keep.append(i)
        Z, r = Z[keep], np.array(rhs)[keep]
        try:
            x = w + Z.T @ np.linalg.solve(Z @ Z.T, r - Z @ w)
        except np.linalg.LinAlgError:
            return None
        neg = [i for i in range(n) if x[i] < -1e-10 and i not in zero]
        if not neg:
            return x
        zero += neg
    return None


def apply_adjustment(w, tax: Taxonomy, node: str, mode: str, value: float, funded_from: str | None = None) -> np.ndarray:
    """Change a node's total weight absolutely (value = target, e.g. 0.30) or relatively (value = change, e.g.
    +0.02 = +2pp), optionally funded from another node, with the smallest possible change to fund weights.
    Closed-form minimum-norm solution (same math as the Console preview); if it would need a negative weight,
    a constrained optimizer finds the nearest feasible long-only solution."""
    w = np.asarray(w, float)
    A, b, _ = adjustment_constraints(w, tax, node, mode, value, funded_from)
    x = _min_norm_active_set(w, A, b)
    if x is None or x.min() < -1e-9:
        import cvxpy as cp
        v = cp.Variable(len(w))
        prob = cp.Problem(cp.Minimize(cp.sum_squares(v - w)), [A @ v == b, v >= 0])
        prob.solve()
        if v.value is None or prob.status not in ("optimal", "optimal_inaccurate"):
            raise ValueError("Requested change is not achievable with long-only weights")
        x = np.asarray(v.value).ravel()
    x = np.clip(x, 0, None)
    return x / x.sum()


def parse_adjustment(spec: str) -> dict:
    """'Equity=78%'  |  'Equity=+1.5pp'  |  'Fixed Income/Short-dated=+2pp from Fixed Income/Long-dated'"""
    left, right = spec.split("=", 1)
    funded = None
    if " from " in right:
        right, funded = right.split(" from ", 1)
        funded = funded.strip()
    right = right.strip().lower()
    if right.endswith("pp"):
        return {"node": left.strip(), "mode": "relative", "value": float(right[:-2]) / 100, "funded_from": funded}
    if right.endswith("%"):
        return {"node": left.strip(), "mode": "absolute", "value": float(right[:-1]) / 100, "funded_from": funded}
    raise ValueError("Use '<node>=<x>%' (absolute) or '<node>=+/-<x>pp' (relative)")
