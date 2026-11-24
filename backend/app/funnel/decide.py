"""Stage 10 (optimise), the decision (recipe step 5), leak analysis (step 6)
and the audit (step 7)."""
import numpy as np
from scipy.optimize import linprog
from .. import priors as P


# ---------- Stage 10a: "Where should the marketing budget go?" linear programme ----------
def channel_mix(business_type, base_cac, monthly_budget, capacity_ratio=1.0):
    ch = P.TYPES[business_type]["channels"]
    n = len(ch)
    cost = []; ub = []; rows = []
    for name, mult, cap in ch:
        for tier, tm in ((1, 1.0), (2, 1.6)):  # second tier: diminishing returns, 60% dearer
            cost.append(base_cac * mult * tm); ub.append(max(1.0, cap * capacity_ratio)); rows.append((name, tier))
    c = -np.ones(len(cost))  # maximise customers won
    res = linprog(c, A_ub=[cost], b_ub=[monthly_budget], bounds=[(0, u) for u in ub], method="highs")
    x = res.x if res.success else np.zeros(len(cost))
    alloc = {}
    for (name, tier), xi, ci in zip(rows, x, cost):
        a = alloc.setdefault(name, dict(channel=name, customers=0.0, spend=0.0))
        a["customers"] += float(xi); a["spend"] += float(xi * ci)
    tot_c = sum(a["customers"] for a in alloc.values()); tot_s = sum(a["spend"] for a in alloc.values())
    for a in alloc.values():
        a["cac"] = a["spend"] / a["customers"] if a["customers"] > 1e-9 else None
    return dict(budget=float(monthly_budget), customers=float(tot_c), spend=float(tot_s), blended_cac=float(tot_s / tot_c) if tot_c else None,
                base_cac=float(base_cac), allocation=sorted(alloc.values(), key=lambda a: -a["spend"]), status=res.status)


def _scaled(inp, **mult):
    out = dict(inp)
    for k, f in mult.items():
        out[k] = tuple(v * f for v in inp[k])
    return out


# ---------- Stage 10b: launch options under the founder's limits ----------
def launch_options(inp, run, market_mult_by_price, focus_segment):
    """12 plans: 3 prices x lean/full x all buyers/beachhead segment. Every plan is
    replayed with the same random seed, so differences come from the plan, not luck."""
    res = []
    for pm, plabel in ((0.85, "15% lower price"), (1.0, "planned price"), (1.15, "15% higher price")):
        for scale in ("standard", "lean"):
            for focus in (False, True):
                # a different price changes who buys: the choice model is re-run at that price
                m = dict(arpu=pm, market=market_mult_by_price[pm])
                if scale == "lean": m.update(fixed=.7, setup=.5, capacity=.6)
                if focus: m.update(cac=.75, churn=.85)
                s = run(_scaled(inp, **m), runs=25, focus_segment=focus_segment if focus else None, keep_paths=False, journeys=False)
                name = f"{'Lean' if scale == 'lean' else 'Full'} launch, {plabel}{', beachhead segment first' if focus else ''}"
                res.append(dict(name=name, price_mult=pm, scale=scale, focus=focus, p_payback=s["p_payback"], p_ruin=s["p_ruin"],
                                npv_mean=float(np.mean(s["npv"])), cash_need_p90=float(np.quantile(s["peak_need"], .9)),
                                payback_median=(lambda v: None if not np.isfinite(v) else float(v))(float(np.median(s["payback"])))))
    return res


# ---------- Step 5: one decision ----------
def decide(base, options, limits, evidence, hard_blockers):
    ok = lambda r: r["p_payback"] >= limits["min_payback"] and r["p_ruin"] <= limits["max_ruin"] and r["npv_mean"] > 0
    feasible = [o for o in options if ok(o)]
    best = max(feasible, key=lambda o: o["npv_mean"]) if feasible else max(options, key=lambda o: (o["p_payback"] - max(0, o["p_ruin"] - limits["max_ruin"]), o["npv_mean"]))
    reasons = []
    if hard_blockers:
        return dict(code="stop", label="Stop until the blockers are solved", best=best, reasons=[f"Hard limit: {b}" for b in hard_blockers], feasible=len(feasible))
    weak_evidence = evidence["strength"] < 0.35
    if ok(base):
        code = "test" if weak_evidence else "launch"
        reasons.append(f"The plan meets your limits: {base['p_payback']:.0%} chance of payback (you asked for {limits['min_payback']:.0%}) and {base['p_ruin']:.0%} chance of needing more cash than your budget (limit {limits['max_ruin']:.0%}).")
    elif feasible:
        code = "test" if weak_evidence else "pivot"
        reasons.append(f"The plan as described misses your limits ({base['p_payback']:.0%} payback chance, {base['p_ruin']:.0%} chance of running out of budget), but “{best['name']}” meets them ({best['p_payback']:.0%} and {best['p_ruin']:.0%}).")
    elif best["p_payback"] >= limits["min_payback"] - .15:
        code = "test"
        reasons.append(f"No tested option meets your limits, but the best (“{best['name']}”, {best['p_payback']:.0%} payback chance) is close. Evidence could tip it either way.")
    else:
        code = "stop"
        reasons.append(f"No tested option comes close: the best reaches only {best['p_payback']:.0%} payback chance against the {limits['min_payback']:.0%} you need.")
    if weak_evidence and code in ("test",) and (ok(base) or feasible):
        reasons.append(f"Evidence is thin: only {evidence['strength']:.0%} of the weight behind the inputs comes from sources or measurements. Run the experiments below before committing money.")
    labels = {"launch": "Launch", "pivot": "Launch with changes", "test": "Not sure yet: test first", "stop": "Stop or rethink the idea"}
    return dict(code=code, label=labels[code], best=best, reasons=reasons, feasible=len(feasible))


# ---------- Step 6: where does the funnel leak? ----------
LEAK_STAGE = {"market": ("Stage 4: will they buy?", "Landing-page test"), "arpu": ("Stage 5: how much will they spend?", "Pricing test at two prices"),
              "churn": ("Stage 6: how long do they stay?", "Pilot with 20 paying customers for 2 months"), "cac": ("Stage 10: cost to win customers", "Small paid-ads test"),
              "fixed": ("Finance: fixed costs", "Three real quotes for rent, staff and licence"), "setup": ("Finance: setup cost", "Fit-out and licence quotes"),
              "var_pct": ("Finance: variable costs", "Supplier quotes and commission terms"), "capacity": ("Operations: capacity", "Time a trial day of operations"),
              "q": ("Stage 7: word of mouth", "Referral test with first customers"), "p": ("Stage 7: marketing pull", "Small paid-ads test"),
              "satisfaction": ("Stage 6: satisfaction", "Customer interviews after first use")}


def leak(sim):
    d = sim["inputs"]; keys = [k for k in LEAK_STAGE if k in d and np.std(d[k]) > 0]
    X = np.column_stack([(d[k] - d[k].mean()) / d[k].std() for k in keys]); y = sim["npv"]
    ys = (y - y.mean()) / (y.std() or 1)
    coef, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(ys)), X]), ys, rcond=None)
    src = coef[1:]; pred = np.column_stack([np.ones(len(ys)), X]) @ coef
    r2 = float(1 - np.sum((ys - pred) ** 2) / np.sum((ys - ys.mean()) ** 2))
    share = src ** 2 / max(np.sum(src ** 2), 1e-12)
    pb = np.isfinite(sim["payback"])
    rows = []
    for k, c, s in zip(keys, src, share):
        q = np.quantile(d[k], [.25, .75])
        lowq, highq = d[k] <= q[0], d[k] >= q[1]
        rows.append(dict(key=k, name=P.NAMES.get(k, k), stage=LEAK_STAGE[k][0], experiment=LEAK_STAGE[k][1], src=float(c), variance_share=float(s),
                         p_payback_low_quarter=float(pb[lowq].mean()), p_payback_high_quarter=float(pb[highq].mean()),
                         low_value=float(q[0]), high_value=float(q[1])))
    rows.sort(key=lambda r: -r["variance_share"])
    return dict(r2=r2, rows=rows, other_share=float(max(0, 1 - r2)))


def kill_threshold(inp, run, limits, predicted_rate):
    """Find the conversion rate below which the payback chance falls under the founder's minimum."""
    mults = [.25, .45, .7, 1.0, 1.4, 2.0, 3.0]; ps = []
    for m in mults:
        s = run(_scaled(inp, market=m), runs=25, keep_paths=False, journeys=False)
        ps.append(s["p_payback"])
    target = limits["min_payback"]; cross = None
    for i in range(1, len(mults)):
        if ps[i - 1] < target <= ps[i]:
            f = (target - ps[i - 1]) / max(ps[i] - ps[i - 1], 1e-9); cross = mults[i - 1] + f * (mults[i] - mults[i - 1]); break
    if cross is None:
        cross = mults[0] if ps[0] >= target else None
    return dict(curve=[dict(mult=m, p_payback=p, rate=predicted_rate * m) for m, p in zip(mults, ps)], multiplier=cross,
                rate=None if cross is None else predicted_rate * cross)
