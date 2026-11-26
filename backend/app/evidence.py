"""Evidence ledger scoring.

Each record is weighted by how much it says about real customers in the target market:

    weight = type x verification x confidence x geography x sample size x recency

AI estimates and synthetic simulations have type weight 0: they are stored and shown, but they can
never raise confidence and are never presented as customer behaviour. Confidence per area combines
records like independent signals, 1 - prod(1 - weight), and is never lower than the credit the
assumption already has from measurements or sources.
"""
import datetime as dt

import numpy as np

TYPES = {  # key: (label, weight, is real-world evidence)
    "transactions": ("Observed transactions", 1.0, True),
    "behaviour": ("Observed customer behaviour", .85, True),
    "feedback": ("Direct customer feedback", .6, True),
    "quote": ("Written quote or price list", .7, True),
    "observation": ("Observed market data (listings, prices, reviews, searches)", .5, True),
    "secondary": ("Secondary research", .4, True),
    "ai": ("AI estimate", 0.0, False),
    "synthetic": ("Synthetic simulation", 0.0, False),
}
VERIFICATION = {"verified": ("Verified", 1.0), "partly": ("Partly verified", .6), "unverified": ("Not verified yet", .3), "disputed": ("Disputed", 0.0)}
CONFIDENCE = {"high": ("High", 1.0), "medium": ("Medium", .7), "low": ("Low", .4)}
GEOGRAPHY = {"target": ("Your target area", 1.0), "uae": ("Elsewhere in the UAE", .85), "gcc": ("GCC", .6), "global": ("Outside the GCC", .35)}
AREAS = {  # area: (label, importance in the overall confidence)
    "market": ("Demand and market size", .20), "pain": ("Customer problem", .10), "price": ("Price customers will pay", .15),
    "cac": ("Cost to win a customer", .15), "churn": ("Customer retention", .10), "fixed": ("Fixed costs", .08), "var_pct": ("Variable costs", .05),
    "setup": ("Setup costs", .05), "capacity": ("Capacity", .02), "competition": ("Competition", .05), "regulation": ("Licensing and rules", .05),
    "other": ("Other", 0.0),
}
VALUE_AREAS = {"price", "var_pct", "fixed", "setup", "cac", "churn", "capacity"}  # records here may carry a number that updates the forecast
SAMPLE_TYPES = {"transactions", "behaviour", "feedback"}
# Credit an assumption already has from its label (see compute.LABEL). AI and model estimates earn nothing.
LABEL_CREDIT = {"measured": 1.0, "benchmarked": .6, "web": .25, "founder": .1, "ai": 0.0, "critic": 0.0, "derived": 0.0, "prior": 0.0}
LABEL_AREA = {"market": "market", "price": "price", "cac": "cac", "churn": "churn", "fixed": "fixed", "var_pct": "var_pct", "setup": "setup", "capacity": "capacity"}


def _age_days(date_str, today=None):
    try:
        d = dt.date.fromisoformat(str(date_str)[:10])
    except (TypeError, ValueError):
        return None
    return ((today or dt.date.today()) - d).days


def weight(rec, today=None):
    """0-1 weight of one ledger record, with the factors that produced it."""
    t = TYPES.get(rec.get("ev_type"), ("", 0.0, False))[1]
    v = VERIFICATION.get(rec.get("verification") or "unverified", ("", .3))[1]
    c = CONFIDENCE.get(rec.get("confidence") or "medium", ("", .7))[1]
    g = GEOGRAPHY.get(rec.get("geography") or "uae", ("", .85))[1]
    n = rec.get("sample_size")
    if rec.get("ev_type") in SAMPLE_TYPES:
        s = float(max(.15, 1 - np.exp(-float(n) / 20))) if n else .3
    else:
        s = 1.0
    age = _age_days(rec.get("collected_on"), today)
    r = .6 if age is not None and age > 730 else .8 if age is not None and age > 365 else 1.0
    w = float(t * v * c * g * s * r)
    return w, dict(type=t, verification=v, confidence=c, geography=g, sample=s, recency=r)


def is_real(rec):
    return TYPES.get(rec.get("ev_type"), ("", 0, False))[2]


def area_confidence(ledger, labels, today=None):
    """Confidence per area from the ledger, never below the credit from the assumption labels."""
    out = {}
    for a, (name, imp) in AREAS.items():
        ws = [weight(r, today)[0] for r in ledger if r.get("area") == a and is_real(r)]
        led = float(1 - np.prod([1 - w for w in ws])) if ws else 0.0
        lab = LABEL_CREDIT.get(labels.get(a), 0.0) if a in LABEL_AREA else 0.0
        out[a] = dict(name=name, importance=imp, ledger=led, label_credit=lab, confidence=max(led, lab), records=len(ws))
    return out


def overall(areas, optimism_flags=0):
    tot = sum(x["importance"] for x in areas.values())
    c = sum(x["importance"] * x["confidence"] for x in areas.values()) / tot
    return float(np.clip(c - .05 * optimism_flags, 0, 1))


def value_overrides(ledger, today=None):
    """Numbers from real evidence that update the forecast. The strongest record per assumption wins.
    Observed transactions or behaviour -> 'measured'; feedback or secondary research -> 'benchmarked'.
    AI estimates, simulations and disputed records never change the forecast."""
    best = {}
    for r in ledger:
        a = r.get("area")
        if a not in VALUE_AREAS or r.get("value_likely") is None or not is_real(r) or r.get("verification") == "disputed": continue
        w = weight(r, today)[0]
        if w <= 0 or (a in best and best[a][0] >= w): continue
        lo, mid, hi = r.get("value_min"), float(r["value_likely"]), r.get("value_max")
        lo = float(lo) if lo is not None else mid * .85; hi = float(hi) if hi is not None else mid * 1.15
        lo, mid, hi = sorted([lo, mid, hi])
        label = "measured" if r["ev_type"] in ("transactions", "behaviour") else "benchmarked"
        src = f"Evidence ledger: {(r.get('claim') or '')[:80]}" + (f" ({r['source_url']})" if r.get("source_url") else "")
        best[a] = (w, dict(min=lo, likely=mid, max=hi, label=label, source=src, evidence_id=r.get("id")))
    return {a: v for a, (w, v) in best.items()}


def from_experiment(e, intake=None):
    """Ledger record for a result entered in the validation lab (linked by experiment_id)."""
    today = e.get("date") or dt.date.today().isoformat()
    where = e.get("geography") or "target"
    base = dict(experiment_id=e.get("id"), hypothesis_id=e.get("hypothesis_id"), collected_on=today, geography=where, verification="partly",
                confidence="medium", source_url=e.get("source_url") or "", limitations=e.get("limitations") or "Self-reported by the founder.")
    k = e["kind"]
    if k == "landing":
        return dict(base, claim=f"{e['signups']} of {e['visitors']} visitors signed up ({e['signups'] / max(e['visitors'], 1):.1%})", area="market", ev_type="behaviour",
                    sample_size=int(e["visitors"]), description=f"Landing-page or ad test; AED {e['spend']:,.0f} spent.",
                    limitations=base["limitations"] + " Sign-ups are interest, not payment.")
    if k == "pricing":
        n = sum(p["n"] for p in e["points"]); kk = sum(p["k"] for p in e["points"])
        pts = "; ".join(f"AED {p['price']:,.0f}: {p['k']}/{p['n']}" for p in e["points"])
        return dict(base, claim=f"{kk} of {n} accepted the price ({pts})", area="price", ev_type="feedback", sample_size=int(n), description="Pricing test.",
                    limitations=base["limitations"] + " Stated willingness, not payment.")
    if k == "vanwestendorp":
        return dict(base, claim=f"Van Westendorp price survey, {len(e['rows'])} respondents", area="price", ev_type="feedback", sample_size=len(e["rows"]),
                    description="Four price questions per respondent.", limitations=base["limitations"] + " Survey answers, not purchases.")
    if k == "interviews":
        return dict(base, claim=f"{e['k']} of {e['n']} interviewees described the problem as serious", area="pain", ev_type="feedback", sample_size=int(e["n"]),
                    description="Customer interviews.", limitations=base["limitations"] + " Small samples and leading questions can overstate the problem.")
    if k == "pilot":
        return dict(base, claim=f"{e['lost']} of {e['customers']} paying customers left over {e['months']:g} months", area="churn", ev_type="transactions",
                    sample_size=int(e["customers"]), description="Paid pilot.", limitations=base["limitations"] + " Early customers are often keener than later ones.")
    if k == "usability":
        return dict(base, claim=f"{e['tasks_done']} of {e['tasks_total']} tasks completed by {e['users']} users", area="other", ev_type="behaviour",
                    sample_size=int(e["users"]), description="Usability test" + (f", SUS scores {', '.join(f'{x:g}' for x in e['sus'])}" if e.get("sus") else "") + ".")
    if k == "sales":
        return dict(base, claim=f"{len(e['sales'])} months of sales, latest AED {e['sales'][-1]:,.0f}", area="market", ev_type="transactions", sample_size=len(e["sales"]),
                    description="Monthly revenue entered by the founder.", limitations=base["limitations"] + " Check against bank statements.")
    if k == "ab":
        return dict(base, claim=f"A/B test: A {e['kA']}/{e['nA']}, B {e['kB']}/{e['nB']}", area="market", ev_type="behaviour", sample_size=int(e["nA"] + e["nB"]),
                    description=e.get("name") or "A/B test.")
    return dict(base, claim=f"{k} result", area="other", ev_type="behaviour", description="Experiment result.")


def system_records(result, state):
    """Read-only rows that show what the AI and the simulation contributed. They carry zero weight."""
    rows = []
    A = result["assumptions"]
    for k, a in A.items():
        if a["label"] in ("ai", "critic", "web"):
            rows.append(dict(claim=f"{a['name']}: about {a['likely']:,.4g}", area=LABEL_AREA.get(k, "other"), ev_type="ai" if a["label"] != "web" else "secondary",
                             description=a.get("source") or "", source_url=a.get("url") or "", verification="unverified", confidence="low", geography="uae",
                             limitations="Found or estimated by an AI agent; not checked by you." + (" Counts only as unverified secondary research." if a["label"] == "web" else " Never counts as evidence."),
                             system=True))
    f = result["stages"]["forecast"]
    rows.append(dict(claim=f"{f['p_payback']:.0%} of {f['runs']} simulated futures pay back within {f['horizon']} months", area="market", ev_type="synthetic",
                     description="Agent-based market simulation on a synthetic UAE population.", verification="unverified", confidence="low", geography="target",
                     limitations="Simulated people, not real customers. Shows what follows from the assumptions; does not test them.", system=True))
    return rows


def gaps(areas, leak_rows=None, top=6):
    """Evidence gaps ranked by importance x missing confidence. Importance uses the leak analysis where available."""
    from .funnel.decide import LEAK_STAGE
    share = {("market" if r["key"] in ("market", "p", "q") else "price" if r["key"] == "arpu" else r["key"]): r["variance_share"] for r in (leak_rows or [])}
    how = HOW
    rows = []
    for a, x in areas.items():
        if a == "other" or x["importance"] == 0: continue
        imp = max(x["importance"], share.get(a, 0))
        miss = 1 - x["confidence"]
        if miss < .15: continue
        rows.append(dict(area=a, name=x["name"], confidence=x["confidence"], priority=float(imp * miss), how=how.get(a, LEAK_STAGE.get(a, ("", "Collect evidence"))[1]),
                         where="Run a test" if a in LAB_AREAS else "Evidence ledger"))
    rows.sort(key=lambda r: -r["priority"])
    return rows[:top]


LAB_AREAS = {"market", "pain", "price", "cac", "churn", "fixed", "var_pct", "setup", "capacity", "regulation", "competition"}  # all have a desk test
HOW = {"market": "Count competitors' reviews and measure Google search demand (desk tests)", "pain": "Read what people already complain about in public posts (desk test)",
       "price": "Check what 5 competitors charge (desk test)", "cac": "Look up what an ad click costs in Keyword Planner (desk test)",
       "churn": "Find a published churn figure for your category (desk test)", "fixed": "Three written rent quotes plus staff costs (desk test)",
       "var_pct": "Supplier price lists and platform commission (desk test)", "setup": "Fit-out, equipment and licence quotes (desk test)",
       "capacity": "Time a trial run of your operation (desk test)", "competition": "Check 5 competitors' prices and offers (desk test)",
       "regulation": "Confirm the licence activity and fee with the authority (desk test)"}
