"""Deterministic analytics: statistics, capital market assumptions, covariance, risk.
LLM agents never do arithmetic; they call these functions and reason about the results."""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- statistics
def annual_stats(r: pd.DataFrame) -> pd.DataFrame:
    ann_ret = (1 + r).prod() ** (12 / len(r)) - 1
    vol = r.std() * np.sqrt(12)
    wealth = (1 + r).cumprod()
    mdd = (wealth / wealth.cummax() - 1).min()
    return pd.DataFrame({"ann_return": ann_ret, "ann_vol": vol, "max_drawdown": mdd,
                         "ret_12m": (1 + r.iloc[-12:]).prod() - 1})


# ---------------------------------------------------------------- covariance
def sample_cov(r: pd.DataFrame) -> np.ndarray:
    return r.cov().values * 12


def ledoit_wolf_cov(r: pd.DataFrame) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf shrinkage toward constant-correlation target. Returns (annualized cov, shrinkage)."""
    x = r.values - r.values.mean(0)
    t, n = x.shape
    s = x.T @ x / t
    sd = np.sqrt(np.diag(s))
    corr = s / np.outer(sd, sd)
    rbar = (corr.sum() - n) / (n * (n - 1))
    f = rbar * np.outer(sd, sd)
    np.fill_diagonal(f, np.diag(s))
    y = x ** 2
    pi_mat = y.T @ y / t - s ** 2
    pi_hat = pi_mat.sum()
    term1 = (x ** 3).T @ x / t
    term2 = np.outer(np.diag(s), np.ones(n)) * s
    theta = term1 - term2
    np.fill_diagonal(theta, 0)
    rho = np.diag(pi_mat).sum() + rbar * ((np.outer(1 / sd, sd) * theta).sum())
    gamma = np.linalg.norm(s - f, "fro") ** 2
    kappa = (pi_hat - rho) / gamma
    delta = float(np.clip(kappa / t, 0, 1))
    return (delta * f + (1 - delta) * s) * 12, delta


# ---------------------------------------------------------------- CMA methods
def cma_candidates(asset_ids, stats: pd.DataFrame, cov: np.ndarray, neutral: np.ndarray,
                   valuation: pd.DataFrame, yields: pd.DataFrame, rf: float, inflation: float,
                   regime: str, risk_aversion: float = 3.0) -> dict[str, dict[str, float]]:
    """Return {asset: {method: expected annual nominal return}} over a ~10y horizon."""
    implied = risk_aversion * cov @ neutral + rf            # reverse-optimized equilibrium (BL prior)
    regime_adj = {"expansion": 0.01, "recovery": 0.015, "late_cycle": -0.01, "recession": -0.02}.get(regime, 0)
    val = valuation.set_index("asset_id") if not valuation.empty else pd.DataFrame()
    yl = yields.set_index("asset_id") if not yields.empty else pd.DataFrame()
    out = {}
    for i, a in enumerate(asset_ids):
        hist = float(stats.loc[a, "ann_return"])
        m = {"historical": hist, "equilibrium": float(implied[i])}
        if a in val.index:  # equity-like: building block (Grinold-Kroner) and CAPE earnings yield
            v = val.loc[a]
            repricing = -0.25 * np.log(v["cape"] / 20.0) / 10   # partial mean reversion of CAPE to 20 over 10y
            m["building_block"] = float(v["dividend_yield"] + v["earnings_growth"] + inflation + repricing)
            m["cape_yield"] = float(1.0 / v["cape"] + inflation)
            m["regime_adjusted"] = hist + regime_adj
        elif a in yl.index:  # fixed income / cash: yield minus expected loss
            y = yl.loc[a]
            m["yield_based"] = float(y["yield"] - y["expected_loss"])
            m["regime_adjusted"] = float(y["yield"] - y["expected_loss"]) + (0.002 if regime in ("late_cycle", "recession") and y["duration"] > 5 else 0)
        out[a] = m
    return out


def auto_blend(methods: dict[str, float], weights: dict[str, float] | None = None) -> float:
    weights = weights or {k: 1.0 for k in methods}
    tot = sum(weights.get(k, 0) for k in methods)
    return sum(v * weights.get(k, 0) for k, v in methods.items()) / tot


# ---------------------------------------------------------------- risk
def port_vol(w, cov) -> float:
    return float(np.sqrt(w @ cov @ w))


def tracking_error(w, bench, cov) -> float:
    d = np.asarray(w) - np.asarray(bench)
    return float(np.sqrt(max(d @ cov @ d, 0)))


def effective_n(w) -> float:
    w = np.asarray(w)
    return float(1.0 / (w ** 2).sum())


def risk_contributions(w, cov) -> np.ndarray:
    w = np.asarray(w)
    v = port_vol(w, cov)
    return w * (cov @ w) / (v ** 2) if v > 0 else w * 0


def historical_backtest(w, rets: pd.DataFrame) -> dict:
    p = rets.values @ np.asarray(w)
    wealth = np.cumprod(1 + p)
    mdd = float((wealth / np.maximum.accumulate(wealth) - 1).min())
    ann = float(wealth[-1] ** (12 / len(p)) - 1)
    vol = float(p.std() * np.sqrt(12))
    return {"ann_return": ann, "ann_vol": vol, "max_drawdown": mdd, "worst_12m": float(
        pd.Series(p).rolling(12).apply(lambda x: np.prod(1 + x) - 1).min())}
