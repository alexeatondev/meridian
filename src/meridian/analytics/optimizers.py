"""Portfolio construction (PC) methods for a glide-path fund.

Every method builds a *tilt* around the glide-path neutral inside the policy's bands and the
tracking-error budget, so every candidate is policy-feasible by construction. The compliance
engine re-checks independently anyway.
"""
from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np


@dataclass
class Bounds:
    lo: np.ndarray
    hi: np.ndarray
    group_masks: list[tuple[np.ndarray, float, float]]   # (mask, lo, hi)
    te_max: float


def _base_constraints(w, b: Bounds, neutral, cov):
    cons = [cp.sum(w) == 1, w >= b.lo, w <= b.hi]
    for m, lo, hi in b.group_masks:
        cons += [m @ w >= lo, m @ w <= hi]
    d = w - neutral
    cons.append(cp.quad_form(d, cp.psd_wrap(cov)) <= b.te_max ** 2)
    return cons


def _solve(obj, cons, w, fallback):
    prob = cp.Problem(obj, cons)
    try:
        prob.solve(solver=cp.CLARABEL)
    except Exception:
        prob.solve()
    if w.value is None or prob.status not in ("optimal", "optimal_inaccurate"):
        return np.asarray(fallback), f"infeasible ({prob.status}); returned neutral"
    x = np.clip(np.asarray(w.value).ravel(), 0, None)
    return x / x.sum(), prob.status


def glide_path_neutral(mu, cov, neutral, b):
    return np.asarray(neutral), "neutral"


def max_sharpe_tilt(mu, cov, neutral, b, rf=0.0385, gamma=4.0):
    w = cp.Variable(len(mu))
    obj = cp.Maximize((mu - rf) @ w - gamma / 2 * cp.quad_form(w, cp.psd_wrap(cov)))
    return _solve(obj, _base_constraints(w, b, neutral, cov), w, neutral)


def min_variance_tilt(mu, cov, neutral, b):
    w = cp.Variable(len(mu))
    obj = cp.Minimize(cp.quad_form(w, cp.psd_wrap(cov)))
    return _solve(obj, _base_constraints(w, b, neutral, cov), w, neutral)


def black_litterman_tilt(mu, cov, neutral, b, rf=0.0385, tau=0.05, risk_aversion=3.0):
    """Blend equilibrium prior with CMA views (identity pick matrix, view uncertainty ∝ tau*diag Σ)."""
    pi = risk_aversion * cov @ neutral + rf
    ts = tau * cov
    omega = np.diag(np.diag(ts))
    post = np.linalg.solve(np.linalg.inv(ts) + np.linalg.inv(omega),
                           np.linalg.inv(ts) @ pi + np.linalg.inv(omega) @ mu)
    return max_sharpe_tilt(post, cov, neutral, b, rf=rf, gamma=risk_aversion)


def max_diversification_tilt(mu, cov, neutral, b):
    """Maximize diversification ratio via the standard transformation (min variance of sigma-scaled weights)."""
    sig = np.sqrt(np.diag(cov))
    w = cp.Variable(len(mu))
    obj = cp.Minimize(cp.quad_form(w, cp.psd_wrap(cov)) - 2 * 0.05 * sig @ w)
    return _solve(obj, _base_constraints(w, b, neutral, cov), w, neutral)


def risk_budget_tilt(mu, cov, neutral, b):
    """Move toward equal risk contribution *within* each of the equity and fixed-income buckets,
    keeping the bucket totals of the neutral (preserves the glide path's equity share)."""
    sig = np.sqrt(np.diag(cov))
    target = np.array(neutral, dtype=float)
    for m, _, _ in b.group_masks[:1]:     # first group mask = equity
        for mask in (m, 1 - m):
            idx = mask.astype(bool) & (np.asarray(neutral) > 0)
            if idx.sum() == 0:
                continue
            inv = 1 / sig[idx]
            target[idx] = neutral[idx].sum() * inv / inv.sum()
    w = cp.Variable(len(mu))
    obj = cp.Minimize(cp.sum_squares(w - target))
    return _solve(obj, _base_constraints(w, b, neutral, cov), w, neutral)


def adversarial_diversifier(mu, cov, neutral, b, centroid=None, rf=0.0385, sharpe_floor_ratio=0.75):
    """Paper §3.4: the most orthogonal feasible portfolio to the other candidates' centroid,
    subject to a return floor. Linearized: maximize distance from centroid in the direction away from it."""
    centroid = np.asarray(neutral if centroid is None else centroid)
    w_ms, _ = max_sharpe_tilt(mu, cov, neutral, b, rf=rf)
    floor = rf + sharpe_floor_ratio * (mu @ w_ms - rf)
    direction = np.sign(centroid - np.asarray(neutral))
    direction[direction == 0] = 1
    w = cp.Variable(len(mu))
    cons = _base_constraints(w, b, neutral, cov) + [mu @ w >= floor]
    obj = cp.Maximize(-direction @ (w - centroid))
    return _solve(obj, cons, w, neutral)


PC_METHODS = {
    "glide_path_neutral": ("heuristic", glide_path_neutral),
    "max_sharpe_tilt": ("return_optimized", max_sharpe_tilt),
    "black_litterman_tilt": ("return_optimized", black_litterman_tilt),
    "min_variance_tilt": ("risk_structured", min_variance_tilt),
    "max_diversification_tilt": ("risk_structured", max_diversification_tilt),
    "risk_budget_tilt": ("risk_structured", risk_budget_tilt),
}
