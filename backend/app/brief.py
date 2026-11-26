"""Decision brief: the reasons, the strongest evidence, the weakest assumptions, financial risks,
missing evidence and the next five actions. Built only from the computed result, the ledger and the
hypotheses; nothing here changes the numbers."""
from . import evidence as EV
from . import lab as LB
from . import priors as P

CODE_LABEL = {"launch": "Launch", "pivot": "Pivot: launch with changes", "test": "Test first", "stop": "Stop"}
PLAIN = {"launch": "The plan meets your limits and enough of it rests on real evidence.",
         "pivot": "The plan as described misses your limits, but a changed plan meets them.",
         "test": "The answer depends on assumptions that have not been tested yet. Cheap tests first.",
         "stop": "Even the best version tested falls well short of your limits, or something blocks it."}


def build(r, state):
    ledger = state.get("ledger") or []; hyps = state.get("hypotheses") or []; ex = state.get("experiments") or []
    f = r["stages"]["forecast"]; L = r["limits"]; ev = r["evidence"]; fin = r.get("finance") or {}
    price = r["assumptions"]["price"]["likely"]
    hev = [(h, LB.evaluate(dict(h, price=price), ex)) for h in hyps]

    # Strongest supporting evidence: real records by weight
    strong = sorted(((EV.weight(x)[0], x) for x in ledger if EV.is_real(x)), key=lambda t: -t[0])
    strongest = [dict(claim=x.get("claim"), type=EV.TYPES[x["ev_type"]][0], weight=w, area=EV.AREAS.get(x.get("area"), ("Other",))[0],
                      verification=EV.VERIFICATION.get(x.get("verification") or "unverified")[0], url=x.get("source_url") or "") for w, x in strong[:5] if w > 0]
    strongest += [dict(claim=h["statement"], type="Validated hypothesis", weight=e["probability"] or 0, area=EV.AREAS.get(h.get("area"), ("Other",))[0],
                       verification=f"{e['n']:,} observations", url="") for h, e in hev if e["status"] == "validated"]

    # Weakest assumptions: low confidence where it matters, optimistic outliers, disproved hypotheses
    weakest = [dict(name=g["name"], why=f"Only {g['confidence']:.0%} confidence; it carries a large share of the decision.", fix=g["how"]) for g in ev.get("gaps", [])[:4]]
    def optimism(a):
        low_good = P.OPTIMISTIC_DIRECTION.get(a.get("key"), 1) < 0 or any(w in a["name"].lower() for w in ("cost", "churn"))
        share = (1 - a["percentile"]) if not low_good else a["percentile"]
        side = "lower" if low_good else "higher"
        return f"Your value {a['value']:,.4g} is {side} than in {1 - share:.0%} of comparable plans (typical {a['typical']:,.4g}): unusually optimistic."
    weakest += [dict(name=a["name"], why=optimism(a), fix="Back it with a quote, a test or a source.") for a in r["stages"]["anomaly"]["per_assumption"] if a["optimistic"]][:2]
    weakest = [dict(name=h["statement"], why=f"Disproved: actual {e['actual']:.1%} vs threshold {e['threshold']:.1%}.", fix="Change the offer, price or audience, then retest.")
               for h, e in hev if e["status"] == "invalidated"] + weakest

    # Financial risks
    risks = []
    if f["p_ruin"] > L["max_ruin"]:
        risks.append(f"{f['p_ruin']:.0%} chance of needing more than your AED {L['budget']:,.0f} budget (your limit is {L['max_ruin']:.0%}).")
    elif f["p_ruin"] > 0:
        risks.append(f"{f['p_ruin']:.0%} chance of needing more than your budget, within your {L['max_ruin']:.0%} limit.")
    risks.append(f"Keep about AED {f['cash_need_p90']:,.0f} available: that covers the cash dip in 90% of simulated futures.")
    sc = (fin.get("scenarios") or {}).get("bad")
    if sc:
        risks.append(f"In the bad case (1 in 10 futures) value is AED {sc['npv']:,.0f}" + (f" and the budget runs out after {sc['runway_months']} months." if sc["runway_months"] else
                     f", cash bottoms out at AED {sc['lowest_cash']:,.0f} in month {sc['lowest_cash_month']}."))
    t = (fin.get("tornado") or {}).get("rows") or []
    if t:
        risks.append(f"{t[0]['name']} moves the value most: AED {min(t[0]['npv_at_low'], t[0]['npv_at_high']):,.0f} to {max(t[0]['npv_at_low'], t[0]['npv_at_high']):,.0f} across its likely range.")
    be = (fin.get("break_even") or {})
    if be and be.get("customers", 0) > be.get("capacity", 1e9):
        risks.append(f"Break-even needs {be['customers']:,.0f} customers but capacity is {be['capacity']:,.0f}.")
    st_ = r["audit"]["stress"]
    risks.append(f"With heavy shocks the payback chance drops to {st_['p_payback']:.0%}.")

    # Missing evidence: important areas with no real records and no measured input
    missing = [dict(area=a, name=x["name"], how=EV.HOW.get(a, "Collect evidence"))
               for a, x in ev["areas"].items() if x["importance"] >= .05 and x["records"] == 0 and x["label_credit"] < .6]

    # Reasons, in plain words
    plural = lambda n, one, many: f"{n} {one if n == 1 else many}"
    reasons = [x for x in r["decision"]["reasons"] if not x.startswith("Evidence is thin")]
    nrec = plural(ev["real_records"], "real-world evidence record", "real-world evidence records")
    if ev["strength"] < .35 and r["decision"].get("desk_route"):
        reasons.append(f"Evidence confidence is {ev['strength']:.0%} ({nrec}): below 35%, but the key numbers are desk-checked. AI estimates and simulations add nothing to it.")
    elif ev["strength"] < .35:
        reasons.append(f"Evidence confidence is {ev['strength']:.0%} ({nrec}). A launch call needs 35%, or the three numbers that move the answer most each checked by a desk test. "
                       "AI estimates and simulations add nothing to it.")
    else:
        reasons.append(f"Evidence confidence is {ev['strength']:.0%}, from {nrec}. AI estimates and simulations add nothing to it.")
    dis = [h for h, e in hev if e["status"] == "invalidated"]; val = [h for h, e in hev if e["status"] == "validated"]
    if val: reasons.append(f"{plural(len(val), 'hypothesis', 'hypotheses')} validated by your own tests.")
    if dis: reasons.append(f"{plural(len(dis), 'hypothesis', 'hypotheses')} disproved by your own tests; the forecast already reflects those results.")

    # Next five actions
    acts = []
    for h, e in hev:
        if e["status"] in ("planned", "needs more data", "inconclusive"):
            acts.append(dict(action=f"Finish testing: {h['statement']}", why=f"{e['n']:,} of {e['needed']:,} observations collected.", where="Validation lab"))
    for h in dis:
        acts.append(dict(action=f"Rework the plan around the disproved hypothesis: {h['statement'][:90]}", why="A core assumption failed its test.", where="Improve my idea"))
    if r["decision"]["code"] in ("pivot", "test") and r["decision"].get("best") and r["decision"]["best"]["name"] != "Your plan as described":
        b = r["decision"]["best"]
        acts.append(dict(action=f"Consider the launch plan “{b['name']}”", why=(f"Typical payback month {round(b['payback_median'])} vs " + (f"month {round(f['payback_median'])}" if f.get('payback_median') else "beyond the plan") + " now; "
                     if b.get('payback_median') else "") + f"{b['p_payback']:.0%} vs {f['p_payback']:.0%} of futures paid back in time.", where="Funnel (all 10 stages)"))
    for g in ev.get("gaps", []):
        if not any(h.get("area") == g["area"] for h, _ in hev):
            acts.append(dict(action=f"{g['how']} ({g['name'].lower()})", why=f"Biggest evidence gap: {g['confidence']:.0%} confidence.", where=g.get("where", "Validation lab")))
    unver = [x for x in ledger if EV.is_real(x) and (x.get("verification") or "unverified") == "unverified"]
    if unver:
        acts.append(dict(action=f"Check and verify {plural(len(unver), 'unverified evidence record', 'unverified evidence records')}", why="Verified evidence counts more than three times as much.", where="Evidence ledger"))
    if f["p_ruin"] > L["max_ruin"]:
        acts.append(dict(action=f"Secure about AED {f['cash_need_p90']:,.0f} or cut setup and fixed costs", why="Budget risk is above your limit.", where="Financials"))
    acts.append(dict(action="Write down your stop rules and the date you will review them", why="Decide in advance what result would make you stop.", where="Decision"))
    seen, next5 = set(), []
    for a in acts:
        if a["action"] in seen: continue
        seen.add(a["action"]); next5.append(a)
        if len(next5) == 5: break

    v = r["validation"]
    return dict(code=r["decision"]["code"], label=CODE_LABEL[r["decision"]["code"]], plain=PLAIN[r["decision"]["code"]], reasons=reasons,
                score=v["score"], score_low=v["low"], score_high=v["high"], confidence=ev["strength"],
                strongest=strongest[:6], weakest=weakest[:6], risks=risks, missing=missing, next5=next5,
                hypotheses=dict(total=len(hyps), validated=len(val), disproved=len(dis)))
