"""Financial scenarios, break-even, cash runway and sensitivity, all read from the market simulation.

Month 1 is the first month of trading; setup and pre-opening costs are spent before it.
Scenarios are three actual replays of the agent-based simulation (not separate guesses): the replay whose
NPV sits at the 10th percentile (bad), the median (typical) and the 90th percentile (good). Each is a
coherent month-by-month story with its own inputs, so revenue, costs and cash add up.

Sensitivity: NPV across all replays is regressed on the inputs each replay drew. Moving one input from
its 10th to its 90th percentile while holding the others at their average gives the tornado bars.
"""
import numpy as np

from .. import priors as P

KEYS = ["market", "arpu", "var_pct", "fixed", "setup", "cac", "churn", "capacity", "p", "q", "satisfaction"]
UNIT = {"market": "people", "arpu": "AED/month", "var_pct": "%", "fixed": "AED/month", "setup": "AED", "cac": "AED", "churn": "%/month",
        "capacity": "customers", "p": "", "q": "", "satisfaction": ""}
NAME = {**P.NAMES, "market": "Buyers within reach", "arpu": "Spend per customer", "satisfaction": "Customer satisfaction"}


def _first(mask):
    idx = np.flatnonzero(mask)
    return int(idx[0]) + 1 if len(idx) else None


def scenario(sim, i, budget, open_months):
    pa = sim["paths"]
    rev, prof, cash = pa["revenue"][i], pa["profit"][i], pa["cash"][i]
    costs, cust, mk, new = pa["costs"][i], pa["customers"][i], pa["marketing"][i], pa["new"][i]
    T = len(rev)
    setup = float(sim["inputs"]["setup"][i])
    pre_open = .5 * float(sim["inputs"]["fixed"][i]) * open_months  # half the fixed costs during the months before opening
    be = _first(prof > 0)
    payback = _first(cash >= 0)
    low_t = int(np.argmin(cash)); low = float(cash[low_t])
    out_t = _first(cash < -budget) if budget else None
    yearly = [float(rev[y * 12:(y + 1) * 12].sum()) for y in range(int(np.ceil(T / 12)))]
    return dict(index=int(i), npv=float(sim["npv"][i]), setup=setup, pre_opening=pre_open, upfront=setup + pre_open, break_even_month=be, payback_month=payback, lowest_cash=low, lowest_cash_month=low_t + 1,
                runway_months=out_t - 1 if out_t else None, budget_lasts=out_t is None, revenue_by_year=yearly, customers_end=float(cust[-1]),
                inputs={k: float(sim["inputs"][k][i]) for k in KEYS if k in sim["inputs"]},
                monthly=dict(revenue=rev.round(0).tolist(), costs=costs.round(0).tolist(), marketing=mk.round(0).tolist(), profit=prof.round(0).tolist(),
                             cash=cash.round(0).tolist(), customers=cust.round(1).tolist(), new_customers=new.round(1).tolist()))


def scenarios(sim, budget, open_months):
    npv = sim["npv"]; order = np.argsort(npv); n = len(npv)
    pick = {"bad": order[int(round(.1 * (n - 1)))], "typical": order[int(round(.5 * (n - 1)))], "good": order[int(round(.9 * (n - 1)))]}
    return {k: scenario(sim, i, budget, open_months) for k, i in pick.items()}


def tornado(sim):
    d = sim["inputs"]; keys = [k for k in KEYS if k in d and np.std(d[k]) > 1e-12]
    X = np.column_stack([d[k] for k in keys]); y = sim["npv"]
    mu = X.mean(0); sd = X.std(0)
    Z = (X - mu) / sd
    coef, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(y)), Z]), y, rcond=None)
    base = float(np.mean(y)); rows = []
    for j, k in enumerate(keys):
        lo, hi = np.quantile(d[k], [.1, .9])
        b = coef[j + 1] / sd[j]
        rows.append(dict(key=k, name=NAME.get(k, k), unit=UNIT.get(k, ""), low_value=float(lo), high_value=float(hi),
                         npv_at_low=base + float(b * (lo - mu[j])), npv_at_high=base + float(b * (hi - mu[j])), swing=float(abs(b * (hi - lo)))))
    rows.sort(key=lambda r: -r["swing"])
    pred = np.column_stack([np.ones(len(y)), Z]) @ coef
    r2 = float(1 - np.sum((y - pred) ** 2) / max(np.sum((y - y.mean()) ** 2), 1e-12))
    return dict(base_npv=base, rows=rows, r2=r2)


def runway_now(cash_left, monthly_burn):
    """Months of cash left at the current burn (used by monitoring)."""
    if monthly_burn <= 0: return None
    return float(cash_left / monthly_burn)


def analyse(sim, S, unit, A, budget, open_months, horizon):
    sc = scenarios(sim, budget, open_months)
    t = tornado(sim)
    be_months = np.array([_first(sim["paths"]["profit"][i] > 0) or np.inf for i in range(sim["runs"])])
    out_t = np.array([_first(sim["paths"]["cash"][i] < -budget) or np.inf for i in range(sim["runs"])])
    return dict(scenarios=sc, tornado=t,
                break_even=dict(customers=unit["bep_customers"], contribution=unit["contribution"], capacity=A["capacity"]["likely"],
                                p_by_horizon=float(np.mean(np.isfinite(be_months))), median_month=float(np.median(be_months)) if np.isfinite(np.median(be_months)) else None),
                runway=dict(budget=budget, p_runs_out=float(np.mean(np.isfinite(out_t))), median_months_if_runs_out=float(np.median(out_t[np.isfinite(out_t)])) if np.isfinite(out_t).any() else None,
                            cash_need_p50=S["cash_need_p50"], cash_need_p90=S["cash_need_p90"]),
                open_months=open_months)
