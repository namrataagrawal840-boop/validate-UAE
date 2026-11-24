"""Runs the whole decision funnel on a saved state. Deterministic: the same state
and seed always give the same result. AI agents are called before this (agents.py);
this module only does maths, so experiments and what-ifs recompute in seconds."""
import copy
import numpy as np
from . import priors as P
from .synth import market, fingerprint, check
from .funnel import market_stages as MS
from .funnel import checks as C
from .funnel.simulate import summary
from .funnel.abm import simulate_abm, friend_network
from .funnel import decide as D
from .funnel import validation as V
from .funnel import competition as CP

CREDIT = {"measured": 1.0, "benchmarked": .6, "web": .6, "founder": .3, "ai": .2, "critic": .2, "derived": .15, "prior": .1}
LABEL = {"measured": "Measured", "benchmarked": "Benchmarked (your source)", "web": "Benchmarked (web source)", "founder": "Founder input",
         "ai": "AI estimate", "critic": "AI estimate, cut by the critic", "derived": "Derived by the model", "prior": "Category prior"}
DEFAULT_SETTINGS = dict(runs=P.RUNS_MAIN, shocks=2, cycles=True, seasonality=True, seed=2027)


def tri(v):
    return (float(v["min"]), float(v["likely"]), float(v["max"]))


def build_assumptions(state):
    it = state["intake"]; t = P.TYPES[it["business_type"]]; ag = state.get("agents", {})
    A = {}
    for k in ["price", "var_pct", "fixed", "setup", "cac", "churn", "capacity"]:
        lo, mid, hi = t[k]; A[k] = dict(min=lo, likely=mid, max=hi, label="prior", source="Category prior for this business type (illustrative)")
    A["p"] = dict(min=t["p"] * .6, likely=t["p"], max=t["p"] * 1.5, label="prior", source="Category prior")
    A["q"] = dict(min=t["q"] * .6, likely=t["q"], max=t["q"] * 1.4, label="prior", source="Category prior")
    warnings = []
    fin = (ag.get("finance") or {}).get("fields", {})
    for k, v in fin.items():
        if k not in A or not v: continue
        lo, mid, hi = sorted([v["min"], v["likely"], v["max"]])
        plo, phi = (t[k][0] / 4, t[k][2] * 4) if k in t and isinstance(t[k], tuple) else (A[k]["min"] / 4, A[k]["max"] * 4)
        if not (plo <= mid <= phi):
            warnings.append(f"{P.NAMES[k]}: the finance agent's value {mid:,.4g} is far outside the normal range for this business type, so it was clipped.")
            mid = float(np.clip(mid, plo, phi)); lo = min(lo, mid); hi = max(hi, mid)
        A[k] = dict(min=lo, likely=mid, max=hi, label="web" if v.get("url") else "ai", source=v.get("source") or "Finance agent", url=v.get("url"))
    # Self-consistency: a second, independent AI estimate. If the two disagree a lot, the range is widened.
    cons = (ag.get("consistency") or {}).get("fields", {}); consistency = []
    for k, v in cons.items():
        if k not in A or A[k]["label"] not in ("ai", "web") or not v: continue
        r = max(v["likely"], A[k]["likely"]) / max(min(v["likely"], A[k]["likely"]), 1e-9)
        consistency.append(dict(key=k, name=P.NAMES[k], first=A[k]["likely"], second=v["likely"], ratio=float(r), widened=bool(r > 1.5)))
        if r > 1.5:
            A[k]["min"] = min(A[k]["min"], v["min"]); A[k]["max"] = max(A[k]["max"], v["max"])
            warnings.append(f"{P.NAMES[k]}: two independent AI estimates differ by {r:.1f}×, so the range was widened.")
    state["_consistency"] = consistency
    for k, key in (("price", "price"), ("fixed", "fixed"), ("setup", "setup_budget")):
        val = it.get(key)
        if val and float(val) > 0:
            val = float(val); a = A[k]; r = val / a["likely"]
            A[k] = dict(min=min(val, a["min"] * r), likely=val, max=max(val, a["max"] * r), label="founder", source="Your intake answer")
    cr = ag.get("critic") or {}
    up = float(np.clip(cr.get("cac_uplift", 1) or 1, 1, 1.8))
    if up > 1.001 and A["cac"]["label"] in ("ai", "web", "prior"):
        for f in ("min", "likely", "max"): A["cac"][f] *= up
        A["cac"]["label"] = "critic"; A["cac"]["source"] += f"; raised {up - 1:.0%} by the critic"
    for k, o in (state.get("overrides") or {}).items():
        if k in A: A[k] = {**A[k], **o}
    for v in state.get("applied") or []:
        V.apply_changes_A(A, v["changes"])
    return A, warnings


def apply_experiments(state, A, coefs, m, it, price, comp_pos, prior_pain_share):
    ex = state.get("experiments") or []
    notes, evid = [], dict(conversion=None, pain=None, acceptance=None, churn=None, elasticity=None, ab=[], vw=None, usability=None, nps=None, sales=None)
    landing = [e for e in ex if e["kind"] == "landing"]
    pricing_pts = [(p["price"], p["n"], p["k"]) for e in ex if e["kind"] == "pricing" for p in e["points"]]
    if landing:
        n = sum(e["visitors"] for e in landing); k = sum(e["signups"] for e in landing); spend = sum(e["spend"] for e in landing)
        pay = np.average([e.get("pay_rate", 30) for e in landing], weights=[e["visitors"] for e in landing]) / 100
        a, b = C.beta_post(n, k); qs = np.random.default_rng(3).beta(a, b, 20000); q10, q50, q90 = np.quantile(qs, [.1, .5, .9])
        cpv = spend / n
        A["cac"] = dict(min=cpv / (q90 * pay), likely=cpv / (q50 * pay), max=cpv / (q10 * pay), label="measured", source=f"Landing-page test: {k} sign-ups from {n} visitors, AED {spend:,.0f}")
        evid["conversion"] = dict(n=n, k=k, mean=a / (a + b), a=a, b=b)
    if len({p for p, _, _ in pricing_pts}) >= 2:
        bv, _ = C.price_elasticity(pricing_pts); coefs["b_value"] = bv; evid["elasticity"] = bv
        notes.append(f"Price sensitivity fitted from your pricing test: value coefficient {bv:.2f}.")
    if pricing_pts:
        n = sum(x[1] for x in pricing_pts); k = sum(x[2] for x in pricing_pts); evid["acceptance"] = dict(n=n, k=k, mean=(1 + k) / (2 + n))
    for e in ex:
        if e["kind"] == "interviews":
            a, b = C.beta_post(e["n"], e["k"]); mean = a / (a + b)
            coefs["b0"] += 1.5 * (mean - prior_pain_share) * min(1, e["n"] / 10)
            evid["pain"] = dict(n=e["n"], k=e["k"], mean=mean, prior=prior_pain_share)
        if e["kind"] == "pilot":
            exposure = e["customers"] * e["months"]; a, b = C.beta_post(exposure, e["lost"]); qs = np.random.default_rng(5).beta(a, b, 20000)
            lo, mid, hi = np.quantile(qs, [.1, .5, .9]) * 100
            A["churn"] = dict(min=lo, likely=mid, max=hi, label="measured", source=f"Pilot: {e['lost']} of {e['customers']} customers left over {e['months']} months")
            evid["churn"] = dict(rate=mid)
        if e["kind"] == "pilot" and e.get("promoters") is not None:
            evid["nps"] = V.nps(e["promoters"], e.get("passives", 0), e.get("detractors", 0))
        if e["kind"] == "vanwestendorp":
            vw = V.van_westendorp(e["rows"]); k, n = V.accept_at(e["rows"], A["price"]["likely"]); vw.update(accept_k=k, accept_n=n); evid["vw"] = vw
            pricing_pts.append((A["price"]["likely"], n, k))
            n_all = sum(x[1] for x in pricing_pts); k_all = sum(x[2] for x in pricing_pts); evid["acceptance"] = dict(n=n_all, k=k_all, mean=(1 + k_all) / (2 + n_all))
        if e["kind"] == "usability":
            evid["usability"] = V.usability_test(e["users"], e["tasks_done"], e["tasks_total"], e.get("sus") or [])
        if e["kind"] == "sales":
            evid["sales"] = V.holt_forecast(e["sales"])
        if e["kind"] == "ab":
            evid["ab"].append(dict(name=e.get("name", "A/B test"), label_a=e.get("label_a", "A"), label_b=e.get("label_b", "B"), **C.ab_compare(e["nA"], e["kA"], e["nB"], e["kB"])))
    target = evid["conversion"]["mean"] if evid["conversion"] else (evid["acceptance"]["mean"] * .5 if evid["acceptance"] else None)
    if target is not None:
        delta = MS.calibrate_intercept(m, it, price, comp_pos, coefs, target); coefs["b0"] += delta
        notes.append(f"Adoption model calibrated to your measured rate of {target:.1%} (intercept shifted by {delta:+.2f}).")
    return evid, notes


def comp_position(c):
    f = c.get("forces") or {}
    fa = np.mean([float(np.clip(f.get(k, 3.5), 1, 5)) for k in ["rivalry", "new_entrants", "substitutes", "buyer_power", "supplier_power"]]) if f else 3.5
    d = c.get("differentiation")
    diff = float(np.clip(40 if d is None else d, 0, 100))
    return float(np.clip(-(fa - 3) / 2 * .6 + (diff - 50) / 50 * .4, -1, 1)), float(fa), diff


def usability_score(ag):
    u = ag.get("usability")
    if not u: return None, None, None
    steps = float(np.clip(u.get("steps_to_first_value", 4), 1, 15)); sev = sum(int(np.clip(i.get("severity", 1), 1, 3)) for i in u.get("issues", []))
    return float(np.clip(100 - 8 * max(0, steps - 3) - 6 * sev, 0, 100)), steps, sev


def compute(state, light=False):
    it = state["intake"]; bt = it["business_type"]; t = P.TYPES[bt]; ag = state.get("agents", {})
    st = {**DEFAULT_SETTINGS, **(state.get("settings") or {})}
    seed = int(st["seed"]); horizon = int(it.get("horizon_months") or 36)
    limits = dict(budget=float(it.get("budget_aed") or 500_000), min_payback=float(it.get("min_payback_probability") or .6),
                  max_ruin=float(it.get("max_ruin_probability") or .2))
    m = market(seed, bt)
    A, warnings = build_assumptions(state)
    agc = ag.get("competition") or {}
    comp = CP.analyse(state, bt, f"{(ag.get('orch') or {}).get('neutral_brief') or it['idea']} {it.get('target_customer') or ''}", A["price"]["likely"], t["price"][1],
                      ai_forces=agc.get("forces"), ai_diff=agc.get("differentiation"), your_features=state.get("your_features"))
    comp_pos, fa, diff = comp_position(comp)
    coefs = dict(P.CHOICE_MODEL)
    price = A["price"]["likely"]
    desc = MS.describe(m, it)
    evid, notes = apply_experiments(state, A, coefs, m, it, price, comp_pos, desc["pain_high_share"])
    price = A["price"]["likely"]

    # Stage 4 classify + stage 5 regress
    p_adopt = MS.adoption(m, it, price, comp_pos, coefs)
    pot = MS.market_potential(m, it, p_adopt)
    spend = MS.spend_model(m, it, price, p_adopt, seed)
    seg = MS.segment(m, it, seed)
    segs = MS.segment_profiles(m, seg, p_adopt, spend["arpu_i"], it)
    adopters = p_adopt > 0
    w = p_adopt[adopters]
    pain_adopt = float(np.average(m["pain"][adopters], weights=w)) if w.sum() > 0 else .5
    value_ratio = float(np.exp(np.average(np.log(MS.wtp(m)[adopters] / price), weights=w))) if w.sum() > 0 else 1
    us, steps, sev = usability_score(ag)
    if evid["usability"]: us = evid["usability"]["score"]
    sat_model = float(np.clip(.35 + .25 * (pain_adopt - .5) * 2 + .2 * np.tanh(np.log(value_ratio)) + .2 * (((us if us is not None else 60) - 50) / 50), .1, .95))
    sat = float(st["satisfaction"]) if st.get("satisfaction") is not None else evid["nps"]["satisfaction"] if evid["nps"] else sat_model
    haircut = float(np.clip((ag.get("critic") or {}).get("market_haircut", 1) or 1, .4, 1))
    market_label = "measured" if evid["conversion"] else "derived"
    pot_used = pot["potential"] * haircut

    # Stage 3 anomaly on the plan's assumptions
    anom = C.anomaly(A, bt, seed)

    # Uncertainty follows evidence: an uncalibrated choice model gets a wide range, a measured one a narrow range
    mlo, mhi = ((.7, 1.3) if evid["conversion"] else (.55, 1.4) if evid["acceptance"] else (.35, 1.6))
    alo, ahi = ((.9, 1.1) if evid["acceptance"] else (.75, 1.15))
    inp = dict(market=(pot_used * mlo, pot_used, pot_used * mhi), arpu=(spend["expected_arpu"] * alo, spend["expected_arpu"], spend["expected_arpu"] * ahi),
               satisfaction=(max(.05, sat - .15), sat, min(.97, sat + .12)), **{k: tri(A[k]) for k in ["var_pct", "fixed", "setup", "cac", "churn", "capacity", "p", "q"]}, rivalry=float((comp["forces"] or {}).get("rivalry", 3.0)))
    for v in state.get("applied") or []:
        inp = V.change_inp(inp, {k: x for k, x in v["changes"].items() if k in ("market", "satisfaction")})
    sim_kw = dict(seed=seed, horizon=horizon, shocks=st["shocks"], cycles=st["cycles"], seasonality=st["seasonality"], season=t["season"], budget=limits["budget"], open_months=t["open_months"])
    pop = agent_population(m, it, p_adopt, spend["arpu_i"], seg, pot, spend["expected_arpu"], A["capacity"]["likely"], seed)
    run = lambda i, **kw: simulate_abm(i, pop, **{**sim_kw, **kw})
    sim = run(inp, runs=st["runs"])
    S = summary(sim); S["abm"] = sim["abm"]
    km = C.kaplan_meier(np.where(np.isfinite(sim["payback"]), sim["payback"], horizon + 1), np.isfinite(sim["payback"]).astype(int), horizon)
    surv = C.customer_survival(segs[:4], A["churn"]["likely"], sat, horizon)
    contrib = spend["expected_arpu"] * (1 - A["var_pct"]["likely"] / 100)
    bep_customers = A["fixed"]["likely"] / max(contrib, 1e-9)
    ltv = contrib / max(A["churn"]["likely"] / 100 * (1.5 - sat), 1e-4)

    # Evidence strength (credit by label) minus optimism flags
    lbl = {**{k: A[k]["label"] for k in ["var_pct", "fixed", "setup", "cac", "churn", "capacity"]}, "price": A["price"]["label"], "market": market_label}
    strength = float(np.clip(np.mean([CREDIT[v] for v in lbl.values()]) - .05 * anom["optimistic_count"], 0, 1))
    mix = {}
    for v in lbl.values(): mix[v] = mix.get(v, 0) + 1
    evidence = dict(strength=strength, labels=lbl, mix=mix)

    result = dict(intake=it, settings=st, limits=limits, warnings=warnings + notes, assumptions={k: {**v, "label_text": LABEL[v["label"]], "name": P.NAMES[k]} for k, v in A.items()},
                  choice_model=coefs, comp_position=comp_pos)
    result["stages"] = stages = {}
    stages["describe"] = desc
    stages["segment"] = dict(k=seg["k"], bic=seg["bic"], segments=segs)
    stages["anomaly"] = anom
    stages["classify"] = dict(potential=pot, potential_used=pot_used, haircut=haircut, mean_adoption=pot["mean_adoption"], coefs=coefs, value_ratio=value_ratio, pain_adopters=pain_adopt,
                              label=market_label, calibrated=bool(evid["conversion"] or evid["acceptance"]))
    stages["regress"] = dict(expected_arpu=spend["expected_arpu"], r2=spend["r2"], drivers=spend["drivers"], planned_price=price)
    stages["survival"] = dict(customers=surv, payback_curve=km, satisfaction=sat)
    stages["forecast"] = S
    docs = C.split_docs(it.get("evidence_text", "")) + [e.get("quote", "") for e in (ag.get("customer") or {}).get("evidence", [])]
    stages["text"] = C.text_topics(docs, (ag.get("orch") or {}).get("neutral_brief") or it["idea"], seed)
    rate = pot["mean_adoption"]
    stages["experiments"] = dict(evidence=evid, predicted_conversion=rate, sample_size_landing=C.sample_size(max(rate, .005)), sample_size_pricing=C.sample_size(.3, .3))
    unit = dict(arpu=spend["expected_arpu"], contribution=contrib, bep_customers=bep_customers, payback_months_per_customer=A["cac"]["likely"] / max(contrib, 1e-9),
                ltv=ltv, ltv_cac=ltv / max(A["cac"]["likely"], 1e-9), satisfaction=sat)
    result["unit"] = unit

    # Scores for the plain-words checks
    sc = dict(market=float(np.clip(50 + 30 * np.log10(max(pot_used / max(bep_customers, 1), 1e-3)), 0, 100)),
              customers=float(np.clip(100 * (.35 * min(1, rate / .25) + .35 * pain_adopt + .3 / (1 + np.exp(-2 * np.log(value_ratio)))), 0, 100)),
              competition=float(np.clip(.6 * (100 - (fa - 1) * 25) + .4 * diff, 0, 100)),
              money=float(np.clip(60 * S["p_payback"] + 40 * (1 - S["p_ruin"]), 0, 100)),
              usability=us, evidence=strength * 100)
    result["scores"] = sc
    result["evidence"] = evidence
    result["validation"] = V.validation_score(sc, strength, len((ag.get("critic") or {}).get("weak_claims") or []), S["p_payback"])
    result["market_sizing"] = V.market_sizing(desc, pot, spend["expected_arpu"], S["customers_end_p50"], ag.get("market"))
    fidx = np.where(p_adopt > 0)[0][:6000]
    result["value"] = V.customer_value(ag, value_ratio, pain_adopt, price, MS.wtp(m)[fidx])
    result["value"]["usability"] = dict(score=us, steps=steps, severity=sev, measured=evid["usability"], journey=(ag.get("usability") or {}).get("flow_steps", []),
                                        issues=(ag.get("usability") or {}).get("issues", []), suggestions=(ag.get("usability") or {}).get("suggestions", []))
    result["consistency"] = state.get("_consistency", [])
    orch = ag.get("orch") or {}
    result["idea"] = dict(brief=orch.get("neutral_brief") or it["idea"], canvas=orch.get("lean_canvas") or default_canvas(it, A),
                          canvas_source="ai" if orch.get("lean_canvas") else "template", assumptions=orch.get("key_assumptions") or DEFAULT_ASSUMPTIONS,
                          rubric=(ag.get("critic") or {}).get("rubric") or [], applied=state.get("applied") or [])
    result["competition"] = {**comp, "force_avg": fa, "differentiation": diff, "rivalry": inp["rivalry"]}
    if light:
        return result

    # Stage 10: optimise
    base_row = dict(name="Your plan as described", p_payback=S["p_payback"], p_ruin=S["p_ruin"], npv_mean=S["npv_mean"], cash_need_p90=S["cash_need_p90"], payback_median=S["payback_median"])
    mm = {}
    for pm in (.85, 1.0, 1.15):
        pa2 = MS.adoption(m, it, price * pm, comp_pos, coefs); mm[pm] = float(pa2.sum() / max(p_adopt.sum(), 1e-9))
    best_share = segs[0]["share"] if segs else .3
    import concurrent.futures as cf
    pool_ex = cf.ThreadPoolExecutor(max_workers=2)  # launch plans and the stop-rule search run side by side
    fut_opts = pool_ex.submit(D.launch_options, inp, run, mm, segs[0]["id"] if segs else None)
    fut_kill = pool_ex.submit(D.kill_threshold, inp, run, limits, rate)
    applied_ids = {v["id"] for v in state.get("applied") or []}
    pm_market = lambda f: float(MS.adoption(m, it, price * f, comp_pos, coefs).sum() / max(p_adopt.sum(), 1e-9))
    fut_var = pool_ex.submit(V.rank_variants, [v for v in V.all_variants(ag) if v["id"] not in applied_ids], inp, run, pm_market)
    opts = fut_opts.result()
    first_year_new = float(np.median(sim["paths"]["customers"][:, min(11, horizon - 1)]))
    budget_month = float(it.get("marketing_budget_aed") or max(2000, A["cac"]["likely"] * max(first_year_new / 12 * 1.5, 20)))
    mix_lp = D.channel_mix(bt, A["cac"]["likely"], budget_month, A["capacity"]["likely"] / t["capacity"][1])
    blockers = [b for b in ((ag.get("regulation") or {}).get("hard_blockers") or []) if b]
    if A["capacity"]["likely"] < bep_customers:
        blockers.append(f"Capacity ({A['capacity']['likely']:,.0f} customers) is below the {bep_customers:,.0f} customers needed to cover fixed costs.")
    decision = D.decide(base_row, opts, limits, evidence, blockers)
    stages["optimise"] = dict(options=sorted(opts, key=lambda o: -o["npv_mean"]), channel_mix=mix_lp, base=base_row)
    result["decision"] = decision

    # Step 6: leaks and kill criteria
    lk = D.leak(sim)
    kill = fut_kill.result(); result["improve"] = fut_var.result(); pool_ex.shutdown()
    result["leak"] = lk; result["kill"] = kill
    result["kit"] = V.experiment_kit(it, ag, price, stages["experiments"]["sample_size_landing"], rate)

    # Step 7: audit
    null_state = dict(intake={**it, "price": None, "fixed": None, "setup_budget": None}, agents={}, settings=st)
    null_res = compute(null_state, light=True) if ag else None
    placebo_state = copy.deepcopy(state); placebo_state["agents"] = {k: v for k, v in ag.items() if k in ("competition",)}
    placebo_state["intake"] = {**it, "price": None, "fixed": None, "setup_budget": None}
    placebo = compute(placebo_state, light=True) if (ag or any(it.get(k) for k in ("price", "fixed", "setup_budget"))) else None
    stress = summary(run(inp, runs=60, keep_paths=False, journeys=False, shocks=3))
    m2 = market(seed, bt)
    result["audit"] = dict(
        synthetic=dict(fingerprint=fingerprint(m2), check=check(m2), independent=True,
                       note="The simulated market is built only from the business type, the UAE population structure and the random seed. It never reads your idea, your numbers or the AI's numbers."),
        base_rate=None if null_res is None else dict(p_payback=null_res["stages"]["forecast"]["p_payback"], npv_mean=null_res["stages"]["forecast"]["npv_mean"]),
        claims_dependence=None if placebo is None else dict(p_payback_without_claims=placebo["stages"]["forecast"]["p_payback"], change=S["p_payback"] - placebo["stages"]["forecast"]["p_payback"]),
        stress=dict(p_payback=stress["p_payback"], p_ruin=stress["p_ruin"]),
        concentration=dict(top_segment=segs[0]["name"] if segs else None, top_share=segs[0]["value_share"] if segs else None),
        optimism_flags=anom["optimistic_count"], neutral_brief=bool((ag.get("orch") or {}).get("neutral_brief")))
    result["kill_criteria"] = kill_criteria(result, limits)
    result["next_steps"] = next_steps(result)
    return result


def agent_population(m, it, p_adopt, arpu_i, seg, pot, arpu_base, capacity, seed):
    """Pick the agents for the agent-based simulation from the blinded synthetic market:
    category buyers in the focus area. Enough agents are used that your capacity is
    represented by at least about 40 of them (1,500 to 5,000 agents)."""
    from . import priors as PP
    idx = np.where(p_adopt > 0)[0]
    pool = pot["potential"] / max(p_adopt[idx].mean(), 1e-9)       # real people within reach
    n = int(np.clip(pool * 40 / max(capacity, 1), 1500, min(PP.MAX_AGENTS, len(idx))))
    rng = np.random.default_rng([seed, 5]); pick = rng.choice(idx, n, replace=False)
    labels = seg["labels"][pick]
    order = np.lexsort((m["digital"][pick], m["emirate"][pick], labels))
    em = [e[0] for e in PP.EMIRATES]; inc = [b[0] for b in PP.INCOME_BANDS]
    desc = [f"{inc[m['income_band'][i]]}-income, age {int(m['age'][i])}, {em[m['emirate'][i]]}, {'mostly online' if m['digital'][i] > .6 else 'mostly in person' if m['digital'][i] < .4 else 'online and in person'}" for i in pick]
    return dict(p_buy=p_adopt[pick], arpu=arpu_i[pick], seg=labels, wtp=MS.wtp(m)[pick], desc=desc, scale=pool / n,
                nbrs=friend_network(n, order, seed), market_base=pot["potential"], arpu_base=arpu_base)


DEFAULT_ASSUMPTIONS = ["Customers feel the problem strongly enough to switch", "Enough of them accept the planned price",
                       "Customers can be won at the planned cost", "Customers keep buying month after month", "Costs stay within the plan"]


def default_canvas(it, A):
    t = P.TYPES[it["business_type"]]
    return dict(problem="To be confirmed with customer interviews", customer_segments=it.get("target_customer") or f"Category buyers in {it.get('emirate')}",
                unique_value="To be defined", solution=it["idea"][:200], channels=", ".join(c[0] for c in t["channels"][:3]),
                revenue_streams=f"About AED {A['price']['likely']:,.0f} per customer per month", cost_structure=f"About AED {A['fixed']['likely']:,.0f} fixed a month; setup AED {A['setup']['likely']:,.0f}",
                key_metrics="New customers a month, churn, cost to win a customer, payback", unfair_advantage="Not identified yet")


def kill_criteria(r, limits):
    out = []
    k = r["kill"]
    if k["rate"]:
        out.append(f"Stop if the landing-page sign-up rate is below {k['rate']:.1%} after at least {r['stages']['experiments']['sample_size_landing']:,} visitors: below that, the payback chance falls under your {limits['min_payback']:.0%}.")
    top = r["leak"]["rows"][:2]
    for row in top:
        bad = row["p_payback_low_quarter"] if row["key"] in ("market", "arpu", "capacity", "q", "p", "satisfaction") else row["p_payback_high_quarter"]
        worse = "below" if row["key"] in ("market", "arpu", "capacity", "q", "p", "satisfaction") else "above"
        val = row["low_value"] if worse == "below" else row["high_value"]
        k = row["key"]
        shown = (f"AED {val:,.0f}" if k in ("fixed", "setup", "cac", "arpu") else f"{val:.1f}%" if k in ("churn", "var_pct") else
                 f"{val:.0%}" if k == "satisfaction" else f"{val:.4f}" if k in ("p", "q") else f"{val:,.0f}")
        out.append(f"Re-think if {row['name'][0].lower() + row['name'][1:]} turns out {worse} about {shown}: in those futures the payback chance is only {bad:.0%}.")
    return out


def next_steps(r):
    steps = []
    for row in r["leak"]["rows"][:3]:
        steps.append(dict(stage=row["stage"], experiment=row["experiment"], why=f"Explains {row['variance_share']:.0%} of the uncertainty in profit."))
    return steps


def what_if(state, overrides, settings):
    """Simulation lab: rerun only the forecast with changed inputs (fast)."""
    s = copy.deepcopy(state); s["overrides"] = {**(s.get("overrides") or {}), **overrides}; s["settings"] = {**(s.get("settings") or {}), **settings}
    r = compute(s, light=True)
    return dict(forecast=r["stages"]["forecast"], unit=r["unit"], scores=r["scores"])
