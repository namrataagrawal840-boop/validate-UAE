"""Version history: a compact snapshot of what went in and what came out, each time a project is recalculated,
and a plain-language explanation of what changed between two snapshots."""
INPUTS = [("price", "Price per customer (AED/month)"), ("fixed", "Fixed costs (AED/month)"), ("setup", "Setup cost (AED)"), ("cac", "Cost to win a customer (AED)"),
          ("churn", "Monthly churn (%)"), ("var_pct", "Variable costs (%)"), ("capacity", "Capacity (customers)")]


def summary(r, state, ledger_count=0):
    A = r["assumptions"]; f = r["stages"]["forecast"]; pv = (r.get("finance") or {}).get("payback") or {}
    return dict(decision=(r.get("decision") or {}).get("code"), decision_label=(r.get("decision") or {}).get("label"),
                score=r["validation"]["score"], confidence=r["evidence"]["strength"], p_payback=f["p_payback"], p_ruin=f["p_ruin"], npv=f["npv_mean"],
                payback_typical=pv.get("typical"), payback_safe=pv.get("safe"), horizon=f["horizon"], budget=r["limits"]["budget"],
                inputs={k: dict(value=A[k]["likely"], label=A[k]["label"]) for k, _ in INPUTS if k in A},
                buyers=r["stages"]["classify"]["potential_used"], ledger=ledger_count, tests_done=sum(1 for t in (state.get("desk_tests") or {}).values() if t.get("status") == "done"),
                run=(r.get("run_info") or {}).get("input_hash"))


def diff(new, old):
    """What changed from `old` to `new`, biggest effect first, in plain words."""
    if not old: return dict(changes=["First version."], moved=False)
    ch = []
    for k, name in INPUTS:
        a, b = (old.get("inputs") or {}).get(k), (new.get("inputs") or {}).get(k)
        if a and b and abs(b["value"] - a["value"]) > 1e-9 * max(1, abs(a["value"])):
            src = " (now from evidence)" if b["label"] != a["label"] and b["label"] in ("measured", "benchmarked") else ""
            fmt = lambda x: f"{x:,.0f}" if abs(x) >= 100 else f"{x:.1f}"
            ch.append(f"{name}: {fmt(a['value'])} → {fmt(b['value'])}{src}")
    if abs((new.get("buyers") or 0) - (old.get("buyers") or 0)) > .02 * max(old.get("buyers") or 1, 1):
        ch.append(f"Buyers within reach: {old['buyers']:,.0f} → {new['buyers']:,.0f}")
    for k, name in (("horizon", "Payback time limit (months)"), ("budget", "Budget (AED)")):
        if old.get(k) != new.get(k): ch.append(f"{name}: {old.get(k):,} → {new.get(k):,}")
    if new.get("ledger", 0) != old.get("ledger", 0): ch.append(f"Evidence records: {old.get('ledger', 0)} → {new.get('ledger', 0)}")
    if new.get("tests_done", 0) != old.get("tests_done", 0): ch.append(f"Desk tests done: {old.get('tests_done', 0)} → {new.get('tests_done', 0)}")
    out = []
    if new.get("decision") != old.get("decision"):
        out.append(f"Decision moved: {old.get('decision_label')} → {new.get('decision_label')}.")
    pt = lambda x: f"month {x}" if x else "beyond the plan"
    if new.get("payback_typical") != old.get("payback_typical"):
        out.append(f"Typical payback: {pt(old.get('payback_typical'))} → {pt(new.get('payback_typical'))}.")
    if abs(new["confidence"] - old["confidence"]) >= .01:
        out.append(f"Evidence confidence: {old['confidence']:.0%} → {new['confidence']:.0%}.")
    return dict(changes=out + (ch or ["No inputs changed (settings or a rerun only)."]), moved=new.get("decision") != old.get("decision"))
