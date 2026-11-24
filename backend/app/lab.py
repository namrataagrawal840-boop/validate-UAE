"""Validation lab: hypotheses, experiment plans, materials, and evaluation of results against expectations.

A hypothesis states one measurable thing about the business, the value the model expects, and the
threshold that would make it true. Only recorded results (experiments linked to the hypothesis) can
change its status; generating a plan or materials never does.

Evaluation is Bayesian: for rates, a Beta(1 + k, 1 + n - k) posterior gives P(rate meets threshold).
Status: validated if that probability >= 0.9, invalidated if <= 0.1, otherwise inconclusive; "needs
more data" while the sample is below the minimum in the plan.
"""
import numpy as np
from scipy.stats import beta as Beta, norm

from .funnel import checks as C

METRICS = {  # key: (label, area, method, direction, unit, minimum sample)
    "signup_rate": ("Visitor sign-up rate", "market", "landing", ">=", "rate", 100),
    "price_acceptance": ("Share who accept the price", "price", "pricing", ">=", "rate", 30),
    "pain_share": ("Share with a serious problem", "pain", "interviews", ">=", "rate", 8),
    "monthly_churn": ("Monthly customer churn", "churn", "pilot", "<=", "rate", 10),
    "task_success": ("Usability task success", "other", "usability", ">=", "rate", 5),
    "ab_b_better": ("Chance version B beats A", "market", "ab", ">=", "prob", 200),
    "sales_growth": ("Average monthly sales growth", "market", "sales", ">=", "growth", 4),
}
METHOD_LABEL = {"landing": "Landing page or ad test", "pricing": "Pricing test", "vanwestendorp": "Van Westendorp price survey", "interviews": "Customer interviews",
                "pilot": "Paid pilot", "usability": "Usability test", "ab": "A/B test", "sales": "Real sales"}


def expected_values(r):
    """What the current model predicts for each metric (the 'expected' side of expected vs actual)."""
    A = r["assumptions"]
    return dict(signup_rate=float(r["stages"]["experiments"]["predicted_conversion"]), price_acceptance=float(r["value"]["wtp_hist"]["share_above_price"]),
                pain_share=float(r["stages"]["describe"]["pain_high_share"]), monthly_churn=float(A["churn"]["likely"] / 100), task_success=.8,
                ab_b_better=.5, sales_growth=.05)


def default_threshold(metric, r):
    exp = expected_values(r)[metric]
    if metric == "signup_rate":
        k = (r.get("kill") or {}).get("rate")
        return float(k) if k else round(exp * .7, 4)
    return {"price_acceptance": .30, "pain_share": .40, "monthly_churn": round(exp * 1.25, 4), "task_success": .80, "ab_b_better": .95, "sales_growth": .03}[metric]


def suggestions(r):
    """Hypotheses suggested by the biggest evidence gaps. Suggestions are text only and change nothing."""
    it = r["intake"]; who = (it.get("target_customer") or "target customers").strip(); price = r["assumptions"]["price"]["likely"]
    if len(who) > 1 and who[0].isupper() and not who[1].isupper(): who = who[0].lower() + who[1:]  # "Parents who…" -> "parents who…"
    by_area = {"market": "signup_rate", "price": "price_acceptance", "pain": "pain_share", "churn": "monthly_churn", "cac": "signup_rate"}
    text = dict(signup_rate=lambda t: f"At least {t:.1%} of {who} who visit the landing page will join the waitlist.",
                price_acceptance=lambda t: f"At least {t:.0%} of {who} will accept a price of AED {price:,.0f} a month.",
                pain_share=lambda t: f"At least {t:.0%} of {who} we interview will describe the problem as serious and frequent.",
                monthly_churn=lambda t: f"Pilot customers will leave at no more than {t:.1%} a month.")
    out, seen = [], set()
    for g in r["evidence"].get("gaps", []):
        m = by_area.get(g["area"])
        if not m or m in seen: continue
        seen.add(m); t = default_threshold(m, r)
        out.append(dict(statement=text[m](t), metric=m, area=METRICS[m][1], method=METRICS[m][2], threshold=t, expected=expected_values(r)[m], why=f"Closes the gap in {g['name'].lower()}."))
    for m in ("pain_share", "signup_rate", "price_acceptance"):
        if m not in seen and len(out) < 4:
            t = default_threshold(m, r); seen.add(m)
            out.append(dict(statement=text[m](t), metric=m, area=METRICS[m][1], method=METRICS[m][2], threshold=t, expected=expected_values(r)[m], why="Core assumption of the plan."))
    return out


def min_sample(metric, expected, threshold):
    label, area, method, direction, unit, floor = METRICS[metric]
    if unit == "rate" and metric in ("signup_rate", "price_acceptance", "pain_share", "task_success"):
        gap = max(abs(threshold - expected), .02)
        p = float(np.clip((threshold + expected) / 2, .01, .99))
        n = int(np.ceil((1.645 ** 2) * p * (1 - p) / (gap / 1.5) ** 2))  # 90% margin of error = two thirds of the gap, so the result can tell them apart
        return int(max(floor, min(n, 5000)))
    if metric == "ab_b_better":
        return int(max(floor, C.sample_size(max(expected, .02)) * 2))
    return floor


def plan(h, r, kit):
    """A step-by-step experiment plan for one hypothesis. Deterministic: same inputs, same plan."""
    m = h["metric"]; label, area, method, direction, unit, floor = METRICS[m]
    n = min_sample(m, h.get("expected") or 0, h["threshold"])
    A = r["assumptions"]; cpv = max(A["cac"]["likely"] * max(r["stages"]["experiments"]["predicted_conversion"], .005) * .3, 1.5)
    thr = f"{h['threshold']:.1%}" if unit in ("rate", "prob", "growth") else f"{h['threshold']:g}"
    steps = {
        "landing": [f"Publish the landing page below with one clear call to action and a waitlist form.",
                    f"Buy targeted ads (Instagram, Google or WhatsApp groups) until at least {n:,} people from the target group have visited.",
                    "Count unique visitors and completed sign-ups. Ignore your own and friends' visits.",
                    "Record visitors, sign-ups and ad spend in the form below."],
        "pricing": [f"Ask at least {n} target customers whether they would pay AED {A['price']['likely']:,.0f} a month; ask a second group about a second price.",
                    "Ask for a commitment (deposit or pre-order) where possible: a 'yes' with money is stronger than a verbal yes.",
                    "Record how many were asked and how many accepted at each price."],
        "interviews": [f"Recruit {n}-{n + 5} people who match the target customer and have faced the problem recently.",
                       "Use the questionnaire below. Ask about past behaviour, not opinions about your idea. Don't pitch until the end.",
                       "After each interview, mark whether they described the problem as serious and frequent (spent money or time trying to solve it).",
                       "Record the totals below and add notes to the evidence ledger."],
        "pilot": [f"Sign up at least {n} paying customers for a limited pilot (2-3 months).", "Track every customer who stops paying and why.",
                  "Ask each pilot customer the 0-10 recommendation question at the end (NPS).", "Record customers, months and leavers below."],
        "usability": [f"Ask {max(n, 5)} target users to complete 3-5 key tasks (sign up, order, pay) while thinking aloud.", "Count tasks completed without help.",
                      "Have each tester answer the 10 SUS questions and record the scores."],
        "ab": [f"Run two versions (A and B) of the page or ad with an even traffic split until each has about {n // 2:,} visitors.", "Change only one thing between versions.",
               "Record visitors and conversions for both."],
        "sales": ["Record monthly revenue from bank or payment-provider statements, oldest first, for at least 4 months."],
    }[method]
    cost = n * cpv if method in ("landing", "ab") else 0
    weeks = {"landing": 2, "ab": 3, "pricing": 2, "interviews": 2, "pilot": 10, "usability": 1, "sales": 16}[method]
    return dict(goal=h["statement"], method=METHOD_LABEL[method], metric=label, success=f"{label} {direction} {thr}", sample_size=n,
                duration_weeks=weeks, budget_aed=round(cost, -1) if cost else 0, steps=steps,
                stop_rule=f"If the result is clearly on the wrong side of {thr} after {n} observations, treat the hypothesis as disproved and revisit the plan.",
                bias_checks=["Recruit outside friends and family", "Fix the success threshold before seeing results (it is saved now)",
                             "Count everyone you asked, including those who said no", "Note where and when you collected the data (limitations)"],
                materials=dict(landing="landing" in (method, "ab"), interview=method == "interviews", survey=method in ("pricing", "interviews")))


def questionnaire(h, r, kit):
    it = r["intake"]; who = it.get("target_customer") or "the customer"
    q = ["Warm-up: tell me a little about yourself and your week.",
         *kit["interview"],
         "What have you spent (money or time) trying to solve this in the last 3 months?",
         "If you could wave a magic wand, what would the perfect solution do?",
         "Is there anyone else involved in deciding or paying for this?",
         "Can I follow up with you when we have something to try? (note yes/no)"]
    return dict(title=f"Interview guide: {h['statement'][:80]}", intro=f"For {who}. 20-30 minutes. Ask about real past events; avoid describing your idea until the last question.",
                questions=q, scoring="After the interview, mark 'serious problem' only if they have actively tried to solve it (spent money or time) in the last 3 months.")


def survey(h, r, kit):
    return dict(title="Customer survey", screening=["Do you live in the UAE? (yes/no)", f"Have you faced this problem in the last 3 months? (yes/no)"],
                questions=kit["survey"], note="Send to at least 30 people who pass the screening questions. The first four questions are the Van Westendorp price questions.")


def evaluate(h, experiments):
    """Compare actual results linked to the hypothesis with the threshold and the model's expectation."""
    m = h["metric"]; label, area, method, direction, unit, floor = METRICS[m]
    ex = [e for e in experiments if e.get("hypothesis_id") == h["id"]]
    n = k = 0; actual = None; prob = None; detail = ""
    thr = h["threshold"]
    if m in ("signup_rate", "price_acceptance", "pain_share", "task_success", "monthly_churn"):
        for e in ex:
            if m == "signup_rate" and e["kind"] == "landing": n += e["visitors"]; k += e["signups"]
            if m == "price_acceptance" and e["kind"] == "pricing":
                for p in e["points"]: n += p["n"]; k += p["k"]
            if m == "price_acceptance" and e["kind"] == "vanwestendorp":
                from .funnel.validation import accept_at
                kk, nn = accept_at(e["rows"], h.get("price") or 0) if h.get("price") else (0, 0); n += nn; k += kk
            if m == "pain_share" and e["kind"] == "interviews": n += e["n"]; k += e["k"]
            if m == "task_success" and e["kind"] == "usability": n += e["tasks_total"]; k += e["tasks_done"]
            if m == "monthly_churn" and e["kind"] == "pilot": n += int(round(e["customers"] * e["months"])); k += e["lost"]
        if n:
            a, b = C.beta_post(n, k); actual = k / n
            prob = float(Beta.sf(thr, a, b)) if direction == ">=" else float(Beta.cdf(thr, a, b))
            lo, hi = Beta.ppf([.05, .95], a, b); detail = f"{k} of {n}; 90% interval {lo:.1%} to {hi:.1%}"
    elif m == "ab_b_better":
        abs_ = [e for e in ex if e["kind"] == "ab"]
        if abs_:
            e = abs_[-1]; c = C.ab_compare(e["nA"], e["kA"], e["nB"], e["kB"]); n = e["nA"] + e["nB"]
            actual = c["p_b_better"]; prob = 1.0 if actual >= thr else 0.0 if actual <= 1 - thr else .5
            detail = f"A {c['rate_a']:.1%} vs B {c['rate_b']:.1%}; lift {c['lift_mean']:+.0%}"
    elif m == "sales_growth":
        s = [e for e in ex if e["kind"] == "sales"]
        if s:
            v = np.array(s[-1]["sales"], float); n = len(v)
            g = np.diff(np.log(np.maximum(v, 1))); actual = float(np.exp(g.mean()) - 1)
            se = g.std(ddof=1) / np.sqrt(len(g)) if len(g) > 1 else 1
            prob = float(norm.sf((np.log1p(thr) - g.mean()) / max(se, 1e-6))); detail = f"{n} months"
    need = min_sample(m, h.get("expected") or 0, thr)
    if actual is None: status = "planned"
    elif n < need and (prob is None or .02 < prob < .98): status = "needs more data"
    elif prob >= .9: status = "validated"
    elif prob <= .1: status = "invalidated"
    else: status = "inconclusive"
    return dict(actual=actual, n=n, needed=need, probability=prob, status=status, detail=detail, experiments=len(ex),
                expected=h.get("expected"), threshold=thr, direction=direction, unit=unit,
                vs_expected=None if actual is None or not h.get("expected") else actual / h["expected"] - 1)
