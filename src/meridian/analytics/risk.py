"""Risk analytics — fund-level risk metrics, risk decomposition, factor model, stress tests, risk
time series and holdings look-through.

Everything here is deterministic code (agents explain results, they never compute them). One risk model
is used everywhere so numbers tie out across screens:

  Σ  = Ledoit-Wolf covariance of monthly proxy total returns (the same estimator portfolio construction
       uses), annualized.
  f  = systematic factor returns built from proxy excess returns (config/risk.yaml -> factors).
  F  = Dᵀ Σ D, the factor covariance implied by Σ (factors are linear combinations f = Dᵀ r).
  B  = Σ D F⁻¹, the regression loadings of each asset on the factors under the same Σ.
  R  = Σ − B F Bᵀ, the residual ("specific"); a Schur complement, so it is never negative and factor +
       specific contributions add up exactly to total variance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist

import re

import numpy as np
import pandas as pd
import yaml

from .. import REPO_ROOT
from .core import ledoit_wolf_cov, sample_cov

RISK_CFG_PATH = REPO_ROOT / "config" / "risk.yaml"
RISK_HISTORY_PATH = REPO_ROOT / "data" / "risk" / "history.csv"
HEDGE_ASSET = "us_long_treasury"


def load_risk_config(path: Path = RISK_CFG_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text())


# ------------------------------------------------------------------------------------ characteristics
def characteristics(assets: list[str], chars: pd.DataFrame | None, holdings: pd.DataFrame | None,
                    cfg: dict, universe: dict | None = None) -> dict:
    """Effective and credit-spread duration per building block, with provenance.
    Priority: holdings look-through (per-line durations) > characteristics dataset > universe.yaml duration."""
    eff, spr, src = {}, {}, {}
    cidx = chars.set_index("asset_id") if chars is not None and not chars.empty else None
    for a in assets:
        if cidx is not None and a in cidx.index:
            row = cidx.loc[a]
            eff[a] = float(row.get("eff_duration", 0) or 0)
            spr[a] = float(row.get("spread_duration", 0) or 0)
            src[a] = f"{row.get('_source', 'characteristics')}" + (f": {row['citation']}" if isinstance(row.get("citation"), str) and row.get("citation") else "")
        else:
            d = float(((universe or {}).get(a) or {}).get("duration", 0) or 0)
            eff[a], spr[a], src[a] = d, 0.0, "universe.yaml duration (no characteristics source)"
    gov = {s.lower() for s in cfg["risk_model"].get("government_sectors", [])}
    if holdings is not None and not holdings.empty and "duration" in holdings:
        for a in assets:
            h = holdings[holdings["asset_id"] == a]
            if h.empty or eff.get(a, 0) <= 0 or h["duration"].notna().sum() == 0:
                continue                                    # equity / commodity funds keep 0 duration
            w = h["weight"].astype(float)
            dur = h["duration"].astype(float).fillna(0.0)
            tot = float(w.sum()) or 1.0
            is_gov = h["sector"].fillna("").str.lower().isin(gov) if "sector" in h else pd.Series(False, index=h.index)
            eff[a] = float((w * dur).sum() / tot)
            spr[a] = float((w * dur)[~is_gov].sum() / tot)
            funds = ", ".join(sorted(h["fund_ticker"].unique()))
            src[a] = f"holdings look-through ({funds}, {pd.Timestamp(h['date'].iloc[0]).date()})"
    return {"eff_duration": eff, "spread_duration": spr, "source": src}


# ------------------------------------------------------------------------------------ factor model
def factor_coefficients(cfg: dict, eff: dict) -> dict[str, dict[str, float]]:
    out = {}
    for f in cfg["factors"]:
        c = {k: float(v) for k, v in f["definition"].items()}
        if f.get("hedge_rates"):
            d = sum(v * eff.get(k, 0.0) for k, v in c.items())
            if eff.get(HEDGE_ASSET, 0) > 0:
                c[HEDGE_ASSET] = c.get(HEDGE_ASSET, 0.0) - d / eff[HEDGE_ASSET]
        out[f["id"]] = c
    return out


def factor_returns(excess: pd.DataFrame, coefs: dict) -> pd.DataFrame:
    return pd.DataFrame({fid: excess[list(c)].values @ np.array(list(c.values())) for fid, c in coefs.items()},
                        index=excess.index)


@dataclass
class RiskModel:
    assets: list[str]
    cov: np.ndarray                 # N×N annualized total-return covariance
    B: np.ndarray                   # N×K factor loadings
    F: np.ndarray                   # K×K annualized factor covariance
    factors: list[dict]             # [{id, name, family}]
    coefs: dict
    start: str
    end: str
    months: int
    shrinkage: float
    r2: dict = field(default_factory=dict)

    @property
    def resid(self) -> np.ndarray:
        return self.cov - self.B @ self.F @ self.B.T


def risk_model(rets: pd.DataFrame, cfg: dict, eff: dict, end=None) -> RiskModel:
    R = rets.loc[:end] if end is not None else rets
    win = cfg["risk_model"].get("window", "expanding")
    if isinstance(win, int):
        R = R.iloc[-win:]
    assets = list(R.columns)
    if cfg["risk_model"].get("covariance", "ledoit_wolf") == "sample":
        cov, shrink = sample_cov(R), 0.0
    else:
        cov, shrink = ledoit_wolf_cov(R)
    coefs = factor_coefficients(cfg, eff)
    # factor returns are linear in asset total returns: f = Dᵀ r (excess over cash folds into the cash row)
    D = np.zeros((len(assets), len(coefs)))
    for k, c in enumerate(coefs.values()):
        for a, v in c.items():
            D[assets.index(a), k] += v
            if "cash" in assets:
                D[assets.index("cash"), k] -= v
    # implied factor covariance and population regression loadings under the SAME Σ, so that
    # Σ − B F Bᵀ is a Schur complement (positive semi-definite): specific risk is never negative.
    F = D.T @ cov @ D
    B = cov @ D @ np.linalg.pinv(F)
    sys = np.einsum("ik,kl,il->i", B, F, B)
    r2 = {a: float(sys[i] / cov[i, i]) if cov[i, i] > 0 else 0.0 for i, a in enumerate(assets)}
    meta = [{"id": f["id"], "name": f["name"], "family": f.get("family", f["name"])} for f in cfg["factors"]]
    return RiskModel(assets, cov, B, F, meta, coefs, str(R.index[0].date()), str(R.index[-1].date()), len(R), shrink, r2)


# ------------------------------------------------------------------------------------ fund metrics
def fund_metrics(w, b, m: RiskModel, ch: dict, cfg: dict) -> dict:
    w, b = np.asarray(w, float), np.asarray(b, float)
    S = m.cov
    vol, bvol = float(np.sqrt(max(w @ S @ w, 0))), float(np.sqrt(max(b @ S @ b, 0)))
    d = w - b
    te = float(np.sqrt(max(d @ S @ d, 0)))
    sig = np.sqrt(np.diag(S))
    eff = np.array([ch["eff_duration"].get(a, 0.0) for a in m.assets])
    spr = np.array([ch["spread_duration"].get(a, 0.0) for a in m.assets])
    vc = cfg["risk_model"]["var"]
    z = NormalDist().inv_cdf(vc.get("confidence", 0.95))
    h = np.sqrt(vc.get("horizon_months", 1) / 12)
    div = lambda x, v: float(1 - v / (np.abs(x) @ sig)) if np.abs(x) @ sig > 0 else 0.0  # noqa: E731
    return {
        "total_risk": vol, "bench_total_risk": bvol, "active_risk": te,
        "eff_duration": float(w @ eff), "bench_eff_duration": float(b @ eff), "rel_duration": float(d @ eff),
        "spread_duration": float(w @ spr), "bench_spread_duration": float(b @ spr), "rel_spread_duration": float(d @ spr),
        "var": float(z * vol * h), "bench_var": float(z * bvol * h), "active_var": float(z * te * h),
        "diversification": div(w, vol), "bench_diversification": div(b, bvol),
        "var_confidence": vc.get("confidence", 0.95), "var_horizon_months": vc.get("horizon_months", 1),
    }


# ------------------------------------------------------------------------------------ risk breakdown
def risk_breakdown(w, b, m: RiskModel, tax=None) -> dict:
    """Contribution of each holding (and each taxonomy node) to total risk, vs the benchmark, and to
    active risk. Contributions are Euler allocations: they sum to total risk / tracking error."""
    w, b = np.asarray(w, float), np.asarray(b, float)
    S = m.cov
    vol, bvol = np.sqrt(w @ S @ w), np.sqrt(b @ S @ b)
    c = w * (S @ w) / vol if vol > 0 else w * 0
    cb = b * (S @ b) / bvol if bvol > 0 else b * 0
    d = w - b
    te = np.sqrt(max(d @ S @ d, 0))
    ca = d * (S @ d) / te if te > 0 else d * 0
    sig = np.sqrt(np.diag(S))
    assets = [{"asset": a, "weight": float(w[i]), "bench_weight": float(b[i]), "active_weight": float(d[i]),
               "standalone_vol": float(sig[i]), "risk_contribution": float(c[i]),
               "pct_total_risk": float(c[i] / vol) if vol > 0 else 0.0,
               "bench_pct_total_risk": float(cb[i] / bvol) if bvol > 0 else 0.0,
               "marginal_risk": float((S @ w)[i] / vol) if vol > 0 else 0.0,
               "active_risk_contribution": float(ca[i]),
               "pct_active_risk": float(ca[i] / te) if te > 0 else 0.0} for i, a in enumerate(m.assets)]
    nodes = []
    if tax is not None:
        names, M = tax.node_matrix()
        for i, n in enumerate(names):
            nodes.append({"node": n, "depth": n.count("/"), "weight": float(M[i] @ w), "bench_weight": float(M[i] @ b),
                          "pct_total_risk": float(M[i] @ c / vol) if vol > 0 else 0.0,
                          "bench_pct_total_risk": float(M[i] @ cb / bvol) if bvol > 0 else 0.0,
                          "pct_active_risk": float(M[i] @ ca / te) if te > 0 else 0.0})
    return {"assets": assets, "nodes": nodes, "note": "Taxonomy nodes split each fund's contribution in proportion to "
            "its look-through fractions (e.g. Core Bond long- vs short-dated)."}


# ------------------------------------------------------------------------------------ factor decomposition
def factor_decomposition(w, b, m: RiskModel) -> dict:
    w, b = np.asarray(w, float), np.asarray(b, float)
    d = w - b
    out = {}
    for label, x_w in (("total", w), ("benchmark", b), ("active", d)):
        var = float(x_w @ m.cov @ x_w)
        x = m.B.T @ x_w
        fc = x * (m.F @ x)
        spec = var - fc.sum()
        vol = np.sqrt(max(var, 0))
        out[label] = {"variance": var, "vol": float(vol),
                      "factors": [{**m.factors[k], "exposure": float(x[k]), "factor_vol": float(np.sqrt(m.F[k, k])),
                                   "pct": float(fc[k] / var) if var > 0 else 0.0,
                                   "contribution": float(fc[k] / vol) if vol > 0 else 0.0} for k in range(len(x))],
                      "specific": {"pct": float(spec / var) if var > 0 else 0.0, "contribution": float(spec / vol) if vol > 0 else 0.0}}
    fam = {}
    for f in out["total"]["factors"]:
        fam.setdefault(f["family"], 0.0)
        fam[f["family"]] += f["pct"]
    out["total"]["families"] = {**fam, "Specific": out["total"]["specific"]["pct"]}
    fa = {}
    for f in out["active"]["factors"]:
        fa[f["family"]] = fa.get(f["family"], 0.0) + f["pct"]
    out["active"]["families"] = {**fa, "Specific": out["active"]["specific"]["pct"]}
    return out


# ------------------------------------------------------------------------------------ stress tests
def _month_end(s: str) -> pd.Timestamp:
    return pd.Timestamp(str(s) + "-01") + pd.offsets.MonthEnd(0)


def conditional_factor_moves(m: RiskModel, shocks: dict[str, float], propagation: str = "correlated") -> np.ndarray:
    """Factor returns given shocks to a subset; the rest move by their conditional expectation."""
    ids = [f["id"] for f in m.factors]
    S = [ids.index(k) for k in shocks]
    f = np.zeros(len(ids))
    s = np.array([shocks[k] for k in shocks])
    f[S] = s
    if propagation == "correlated" and len(S) < len(ids):
        O = [i for i in range(len(ids)) if i not in S]
        Fss = m.F[np.ix_(S, S)]
        f[O] = m.F[np.ix_(O, S)] @ np.linalg.solve(Fss + 1e-12 * np.eye(len(S)), s)
    return f


def stress_tests(weights: dict, benches: dict, rets: pd.DataFrame, m: RiskModel, cfg: dict) -> dict:
    sc = cfg["stress"]
    ids = [f["id"] for f in m.factors]
    sd_m = np.sqrt(np.diag(m.F) / 12)

    def pv(r):
        return {str(v): {"portfolio": float(weights[v] @ r), "benchmark": float(benches[v] @ r),
                         "active": float((weights[v] - benches[v]) @ r)} for v in weights}

    hist = []
    for s in sc.get("historical", []):
        R = rets.loc[_month_end(s["start"]):_month_end(s["end"])]
        if R.empty:
            hist.append({**s, "start": str(s["start"]), "end": str(s["end"]), "available": False})
            continue
        cum = (1 + R).prod().values - 1
        hist.append({**s, "start": str(s["start"]), "end": str(s["end"]), "available": True, "months": len(R),
                     "asset_returns": dict(zip(m.assets, np.round(cum, 5).tolist())), "vintages": pv(cum)})
    hyp = []
    for s in sc.get("hypothetical", []):
        levels = []
        for sev in sc.get("severities", []):
            shocks = {k: float(np.sign(v) * sev["k"] * sd_m[ids.index(k)]) for k, v in s["shocks"].items()}
            f = conditional_factor_moves(m, shocks, s.get("propagation", "correlated"))
            r = m.B @ f
            levels.append({"k": sev["k"], "label": sev["label"], "note": sev.get("note", ""),
                           "factor_moves": dict(zip(ids, np.round(f, 5).tolist())),
                           "asset_returns": dict(zip(m.assets, np.round(r, 5).tolist())), "vintages": pv(r)})
        hyp.append({"id": s["id"], "name": s["name"], "shocks": s["shocks"], "levels": levels,
                    "propagation": s.get("propagation", "correlated")})
    worst = {}
    for v in weights:
        p = rets.values @ weights[v]
        worst[str(v)] = {"worst_month": float(p.min()), "worst_month_date": str(rets.index[int(p.argmin())].date())}
    return {"historical": hist, "hypothetical": hyp, "worst_month": worst,
            "method": "Historical: current weights × realized proxy returns compounded over the window (no "
                      "rebalancing). Hypothetical: shocked factors move k × their 1-month standard deviation; "
                      "other factors move by their conditional expectation (correlated); asset returns = B·f. "
                      "Linear (no convexity); proxies stand in for the building-block funds."}


# ------------------------------------------------------------------------------------ time series
def risk_snapshot_rows(as_of: str, run_id: str, vintage: int, met: dict, fd: dict, source: str) -> list[dict]:
    rows = [{"as_of": as_of, "vintage": int(vintage), "run_id": run_id, "source": source, "metric": k, "value": float(v)}
            for k, v in met.items() if isinstance(v, (int, float)) and not k.startswith("var_")]
    for f in fd["total"]["factors"]:
        rows.append({"as_of": as_of, "vintage": int(vintage), "run_id": run_id, "source": source,
                     "metric": f"factor:{f['id']}", "value": f["pct"]})
    rows.append({"as_of": as_of, "vintage": int(vintage), "run_id": run_id, "source": source,
                 "metric": "factor:specific", "value": fd["total"]["specific"]["pct"]})
    return rows


def risk_history(rets: pd.DataFrame, cfg: dict, ch: dict, policy, as_of: str, current: dict, run_id: str,
                 positions_fn=None, recorded: pd.DataFrame | None = None) -> list[dict]:
    """Month-end risk series for the last `history_months` months. Each point uses only data up to that
    month. Weights: recorded positions on or before the month (if any) else the glide path for that date;
    the as-of month uses this run's proposal. Recorded snapshots from earlier runs (point-in-time) take
    precedence over reconstruction for the same month and vintage."""
    H = int(cfg["risk_model"].get("history_months", 18))
    end = pd.Timestamp(as_of) + pd.offsets.MonthEnd(0)
    months = [d for d in rets.index if d <= end][-H:]
    rec = {}
    if recorded is not None and not recorded.empty:
        r = recorded.copy()
        r["me"] = pd.to_datetime(r["as_of"]) + pd.offsets.MonthEnd(0)
        r = r[r["run_id"] != run_id]
        for (me, v, rid), g in r.groupby(["me", "vintage", "run_id"]):
            rec[(me, int(v))] = (g["as_of"].max(), rid, dict(zip(g["metric"], g["value"])))
    out = []
    eff = ch["eff_duration"]
    for t in months:
        m = risk_model(rets, cfg, eff, end=t)
        frac = t.year + (t.dayofyear - 1) / 365.25
        for v in policy.vintages:
            b = policy.neutral_weights(v - frac)
            if (t, int(v)) in rec and t != months[-1]:
                ao, rid, vals = rec[(t, int(v))]
                out.append({"date": str(t.date()), "vintage": int(v), "source": f"recorded ({rid})",
                            **{k: vals[k] for k in vals if not k.startswith("factor:")},
                            "factors": {k.split(":", 1)[1]: vals[k] for k in vals if k.startswith("factor:")}})
                continue
            if t == months[-1] and str(v) in current:
                w, src = np.asarray(current[str(v)]), "this run (proposed)"
            else:
                w, src = None, None
                if positions_fn is not None:
                    wd, s = positions_fn(str(t.date()), v)
                    if wd is not None:
                        w, src = np.array([wd[a] for a in m.assets]), f"recorded positions {s}"
                if w is None:
                    w, src = b, "glide path (no recorded positions)"
            met = fund_metrics(w, b, m, ch, cfg)
            fd = factor_decomposition(w, b, m)
            out.append({"date": str(t.date()), "vintage": int(v), "source": src,
                        **{k: met[k] for k in met if not k.startswith("var_")},
                        "factors": {**{f["id"]: f["pct"] for f in fd["total"]["factors"]}, "specific": fd["total"]["specific"]["pct"]}})
    return out


def append_risk_history(rows: list[dict], path: Path = RISK_HISTORY_PATH) -> None:
    new = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = pd.read_csv(path)
        if not new.empty:
            old = old[~old["run_id"].isin(new["run_id"].unique())]
        new = pd.concat([old, new], ignore_index=True)
    new.to_csv(path, index=False)


# ------------------------------------------------------------------------------------ look-through
UST_PATTERN = r"^(?:UNITED STATES TREAS|U\.?S\.? TREAS|US TREAS|TREASURY|TBILL|T-BILL|TREAS )"
UST_NAME = "UNITED STATES TREASURY"


def normalize_issuers(h: pd.DataFrame) -> pd.DataFrame:
    """One issuer for US Treasury debt (finding F-4): the public holdings files name it many ways
    ("TREASURY NOTE", "TREASURY (CPI) NOTE", "TREASURY BILL", "TBILL TREASURY BILL", "(OLD)"…)."""
    h = h.copy()
    us = h["country"].str.upper().isin(["UNITED STATES", "US", "USA", ""])
    ust = us & h["name"].fillna("").str.upper().str.strip().str.contains(UST_PATTERN, regex=True)
    if ust.any():
        h.loc[ust, "name"] = UST_NAME
        h.loc[ust, "ticker"] = "UST"
        h.loc[ust, "sector"] = "Treasuries"
        h.loc[ust, "country"] = "United States"
        h.loc[ust, "security_id"] = "UST|United States|Treasury"
        h.loc[ust, "asset_class"] = "Fixed Income"
    return h


FIN_COLS = ["revenue", "net_income", "operating_income", "operating_cash_flow", "capex", "eps_diluted", "total_assets",
            "total_liabilities", "equity", "cash", "long_term_debt", "shares_outstanding"]


def lookthrough(holdings: pd.DataFrame | None, assets: list[str], universe: dict, return_proxy: dict,
                edgar: pd.DataFrame | None = None) -> dict:
    """Compact look-through structure for the console: a security index plus, per building block, the
    list of [security index, weight in fund, duration]. Portfolio exposure to a security =
    Σ_funds (fund weight in portfolio × security weight in fund) — computed client-side per vintage."""
    if holdings is None or holdings.empty:
        return {"available": False, "funds": {}, "securities": [],
                "note": "No holdings look-through loaded. Run the data refresh (iShares holdings) or plug in a "
                        "vendor holdings feed (holdings.lookthrough)."}
    h = holdings.copy()
    for c in ("ticker", "sector", "asset_class", "country"):
        if c not in h:
            h[c] = ""
        h[c] = h[c].fillna("").astype(str)
    if "duration" not in h:
        h["duration"] = np.nan
    h = normalize_issuers(h)
    sec = h.drop_duplicates("security_id")[["security_id", "ticker", "name", "sector", "asset_class", "country"]]
    sec = sec.reset_index(drop=True)
    idx = {s: i for i, s in enumerate(sec["security_id"])}
    funds = {}
    for a in assets:
        g = h[h["asset_id"] == a]
        if g.empty:
            continue
        # a security held by several blended proxies (e.g. IJH + IJR) is summed
        g2 = g.groupby("security_id", sort=False).agg(weight=("weight", "sum"), duration=("duration", "mean")).reset_index()
        g2 = g2.sort_values("weight", ascending=False)
        proxies = g.groupby("fund_ticker").agg(blend=("blend_weight", "first") if "blend_weight" in g else ("weight", "size"),
                                               date=("date", "first")).reset_index()
        funds[a] = {"proxies": [{"ticker": r.fund_ticker, "blend_weight": float(r.blend) if "blend_weight" in g else 1.0,
                                 "as_of": str(pd.Timestamp(r.date).date())} for r in proxies.itertuples()],
                    "return_proxy": return_proxy.get(a, ""), "lines": int(g["lines"].sum()) if "lines" in g else len(g),
                    "securities": len(g2), "coverage": float(g2["weight"].sum()),
                    "holdings": [[idx[s], round(float(w), 7), (None if pd.isna(d) else round(float(d), 2))]
                                 for s, w, d in zip(g2["security_id"], g2["weight"], g2["duration"])]}
    fin = _financials(h, sec, edgar)
    return {"available": True, "funds": funds, "financials": fin,
            "securities": sec[["ticker", "name", "sector", "asset_class", "country"]].values.tolist(),
            "as_of": str(pd.to_datetime(h["date"]).max().date()),
            "note": "Look-through uses public holdings of a proxy fund that tracks the same or a similar index as "
                    "each building block. Bond holdings are aggregated by issuer."}


def _financials(h: pd.DataFrame, sec: pd.DataFrame, edgar: pd.DataFrame | None) -> dict:
    """SEC EDGAR financials for US-listed equities in the look-through, keyed by security index.
    market_cap = SEC shares outstanding x last price in the holdings file. Only US equities are matched
    (a foreign listing can share a ticker with an unrelated US company)."""
    out = {"available": False, "rows": {}, "as_of": None, "columns": FIN_COLS,
           "note": "No SEC EDGAR financials loaded. The monthly data refresh pulls them (fundamentals.edgar)."}
    if edgar is None or edgar.empty:
        return out
    e = edgar.copy()
    # match on letters and digits only: iShares writes BRKB or BRK.B where SEC writes BRK-B
    e["ticker"] = e["ticker"].astype(str).str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
    e = e.drop_duplicates("ticker").set_index("ticker")
    price = (h.dropna(subset=["price"]).groupby("security_id")["price"].first() if "price" in h else pd.Series(dtype=float))
    rows = {}
    for i, r in sec.iterrows():
        if r["asset_class"] != "Equity" or r["country"] != "United States":
            continue
        t = re.sub(r"[^A-Z0-9]", "", str(r["ticker"]).upper())
        if t not in e.index:
            continue
        x = e.loc[t]
        d = {c: (None if c not in x or pd.isna(x[c]) else float(x[c])) for c in FIN_COLS}
        p = price.get(r["security_id"])
        d["price"] = None if p is None or pd.isna(p) else float(p)
        d["market_cap"] = d["shares_outstanding"] * d["price"] if d["shares_outstanding"] and d["price"] else None
        d["cik"] = int(x["cik"]) if "cik" in x and not pd.isna(x["cik"]) else None
        d["fiscal_period"] = None if pd.isna(x.get("fiscal_period")) else str(x.get("fiscal_period"))
        d["balance_date"] = None if pd.isna(x.get("balance_date")) else str(x.get("balance_date"))[:10]
        rows[str(i)] = d
    out.update({"available": bool(rows), "rows": rows,
                "as_of": str(pd.to_datetime(edgar["date"]).max().date()) if "date" in edgar else None,
                "note": "Financials as filed with the SEC (EDGAR XBRL): income and cash flow for the latest calendar year "
                        "reported, balance sheet at the latest quarter end. Market cap = shares outstanding on the latest "
                        "filing cover page x last price in the holdings file."})
    return out


# ------------------------------------------------------------------------------------ public payload
def model_payload(m: RiskModel, cfg: dict, ch: dict) -> dict:
    return {"assets": m.assets, "factors": m.factors, "B": np.round(m.B, 6).tolist(), "F": np.round(m.F, 8).tolist(),
            "coefficients": {k: {a: round(v, 4) for a, v in c.items()} for k, c in m.coefs.items()},
            "r2": {a: round(v, 3) for a, v in m.r2.items()}, "start": m.start, "end": m.end, "months": m.months,
            "shrinkage": round(m.shrinkage, 3), "sd_month": np.round(np.sqrt(np.diag(m.F) / 12), 6).tolist(),
            "characteristics": ch, "drivers": cfg["stress"].get("drivers", []),
            "severities": cfg["stress"].get("severities", []),
            "var": cfg["risk_model"]["var"], "history_months": cfg["risk_model"].get("history_months", 18),
            "description": "Ledoit-Wolf covariance of monthly proxy total returns (expanding window, same as portfolio "
                           "construction); systematic factors built from proxy excess returns; specific = residual."}
