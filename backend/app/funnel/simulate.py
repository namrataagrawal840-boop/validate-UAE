"""Aggregate cash-flow model (kept as a fast cross-check and for its helpers).

The app's Stage 7 now uses the agent-based simulation in abm.py.

Thousands of futures are simulated at once (vectorised with NumPy). Each future
draws its uncertain inputs from triangular ranges, then runs month by month:
Bass diffusion demand, satisfaction-adjusted word of mouth and churn, a capacity
ceiling, Markov economic regimes, UAE seasons (summer, Ramadan) and random
shocks (Poisson arrivals). Cash, payback, NPV and peak cash need are tracked.
"""
import numpy as np
from .. import priors as P

SHOCK_KEYS = list(P.SHOCKS)


def tri(rng, spec, n):
    lo, mid, hi = float(spec[0]), float(spec[1]), float(spec[2])
    lo, hi = min(lo, mid), max(hi, mid)
    if hi - lo < 1e-12:
        return np.full(n, mid)
    return rng.triangular(lo, mid, hi, n)


def simulate(inp, *, runs=2000, seed=2027, horizon=36, shocks=2, cycles=True, seasonality=True,
             season="online", budget=None, keep_paths=True, open_months=0, ramp_months=6):
    """inp: dict of (low, likely, high) for market, arpu, var_pct, fixed, setup, cac, churn,
    capacity, p, q, satisfaction. Same seed -> same random futures (common random numbers)."""
    rng = np.random.default_rng(seed)
    R, T = int(runs), int(horizon)
    d = {k: tri(rng, inp[k], R) for k in ["market", "arpu", "var_pct", "fixed", "setup", "cac", "churn", "capacity", "p", "q", "satisfaction"]}
    d["satisfaction"] = np.clip(d["satisfaction"], 0.02, 0.98)
    M = np.maximum(d["market"], 1.0)
    cap = np.maximum(d["capacity"], 1.0)
    qe = d["q"] * (0.5 + d["satisfaction"])
    ce = d["churn"] / 100 * (1.5 - d["satisfaction"])
    vp = np.clip(d["var_pct"], 0, 95) / 100
    summer, ramadan = P.SEASON.get(season, P.SEASON["online"])
    lam = P.SHOCK_RATE[int(shocks)]
    w = np.array([P.SHOCKS[k]["weight"] for k in SHOCK_KEYS]); w = w / w.sum()
    dm_k = np.array([P.SHOCKS[k]["dm"] for k in SHOCK_KEYS]); cm_k = np.array([P.SHOCKS[k]["cm"] for k in SHOCK_KEYS])
    fm_k = np.array([P.SHOCKS[k]["fm"] for k in SHOCK_KEYS]); dur_k = np.array([P.SHOCKS[k]["months"] for k in SHOCK_KEYS])
    one_k = np.array([P.SHOCKS[k]["one_off"] for k in SHOCK_KEYS])
    Pm = np.array(P.REGIMES["P"]); cum = Pm.cumsum(1); rmult = np.array(P.REGIMES["mult"])
    r_month = (1 + P.ANNUAL_DISCOUNT_RATE) ** (1 / 12) - 1

    N = np.zeros(R); cash = -d["setup"].copy(); npv = -d["setup"].copy()
    regime = np.zeros(R, dtype=int); rem = np.zeros((R, len(SHOCK_KEYS)))
    payback = np.full(R, np.inf); op_be = np.full(R, np.inf); low = cash.copy()
    shock_count = np.zeros(len(SHOCK_KEYS), dtype=int)
    paths = {k: np.zeros((R, T)) for k in ["cash", "customers", "revenue", "profit"]} if keep_paths else None
    # Before opening: licence, fit-out and hiring. Half the fixed costs are paid, no revenue.
    for _ in range(int(open_months)):
        pre = -0.5 * d["fixed"]
        cash = cash + pre; npv = npv + pre; low = np.minimum(low, cash)
    for t in range(T):
        aware = min(1.0, (t + 1) / ramp_months) if ramp_months else 1.0  # awareness builds over the first months
        if cycles:
            u = rng.random(R)
            regime = (u[:, None] > cum[regime]).sum(1).clip(0, 2)
        hit = rng.random(R) < lam
        kind = rng.choice(len(SHOCK_KEYS), R, p=w)
        oneoff = np.zeros(R)
        if hit.any():
            idx = np.where(hit)[0]
            rem[idx, kind[idx]] = np.maximum(rem[idx, kind[idx]], dur_k[kind[idx]])
            oneoff[idx] = one_k[kind[idx]]
            np.add.at(shock_count, kind[idx], 1)
        active = rem > 0
        dm = np.prod(np.where(active, dm_k, 1.0), 1); cm = np.prod(np.where(active, cm_k, 1.0), 1); fm = np.prod(np.where(active, fm_k, 1.0), 1)
        rem = np.maximum(rem - 1, 0)
        if cycles:
            dm = dm * rmult[regime]
        if seasonality:
            cal, yr = t % 12, P.START_YEAR + t // 12
            if 5 <= cal <= 7: dm = dm * summer
            if P.RAMADAN_MONTH.get(yr) == cal: dm = dm * ramadan
        dm = dm * np.exp(rng.normal(0, .15, R))
        new = np.maximum(0, (d["p"] * aware + qe * N / M) * (M - N)) * dm
        lost = N * np.clip(ce * cm, 0, 1)
        new = np.minimum(new, np.maximum(0, cap - (N - lost)))
        N = np.clip(N - lost + new, 0, np.minimum(M, cap))
        revenue = N * d["arpu"]
        profit = revenue * (1 - vp) - d["fixed"] * fm - new * d["cac"] - oneoff * d["fixed"]
        cash = cash + profit
        npv = npv + profit / (1 + r_month) ** (t + 1)
        payback = np.where(np.isinf(payback) & (cash >= 0), t + 1, payback)
        op_be = np.where(np.isinf(op_be) & (profit > 0) & (t > 0), t + 1, op_be)
        low = np.minimum(low, cash)
        if keep_paths:
            paths["cash"][:, t] = cash; paths["customers"][:, t] = N; paths["revenue"][:, t] = revenue; paths["profit"][:, t] = profit
    peak_need = -np.minimum(low, 0)
    out = dict(runs=R, horizon=T, inputs=d, npv=npv, payback=payback, op_breakeven=op_be, peak_need=peak_need, final_cash=cash,
               final_customers=N, shock_count=dict(zip(SHOCK_KEYS, shock_count.tolist())))
    out["p_payback"] = float(np.mean(np.isfinite(payback)))
    out["ruin"] = (peak_need > budget) if budget else np.zeros(R, dtype=bool)
    out["p_ruin"] = float(np.mean(out["ruin"]))
    out["paths"] = paths
    return out


def bands(arr, qs=(.1, .5, .9)):
    q = np.quantile(arr, qs, axis=0)
    return {"p10": q[0].round(2).tolist(), "p50": q[1].round(2).tolist(), "p90": q[2].round(2).tolist()}


def summary(sim):
    pb = sim["payback"]; fin = np.isfinite(pb)
    med = float(np.median(np.where(fin, pb, np.inf)))
    res = dict(runs=sim["runs"], horizon=sim["horizon"], p_payback=sim["p_payback"], p_ruin=sim["p_ruin"],
               payback_median=None if not np.isfinite(med) else med,
               op_breakeven_median=(lambda m: None if not np.isfinite(m) else m)(float(np.median(sim["op_breakeven"]))),
               npv_mean=float(np.mean(sim["npv"])), npv_p10=float(np.quantile(sim["npv"], .1)), npv_p90=float(np.quantile(sim["npv"], .9)),
               cash_need_p50=float(np.median(sim["peak_need"])), cash_need_p90=float(np.quantile(sim["peak_need"], .9)),
               customers_end_p50=float(np.median(sim["final_customers"])), shock_count=sim["shock_count"],
               shocks_per_run=float(sum(sim["shock_count"].values()) / sim["runs"]))
    if sim["paths"] is not None:
        res["bands"] = {k: bands(v) for k, v in sim["paths"].items()}
    return res
