"""Business-validation modules around the funnel:
overall validation score, market sizing check, customer value, idea variants with
recombination, and analysis of extra real-world tests (Van Westendorp pricing,
usability test with SUS, NPS, sales forecasting) plus a ready-to-use experiment kit."""
import numpy as np
from .. import priors as P

# ---------- Overall validation score (multi-criteria decision analysis) ----------
WEIGHTS = dict(market=.20, customers=.25, competition=.15, money=.30, usability=.10)


def validation_score(scores, evidence_strength, critic_flags, p_payback, meets_limits=True):
    used = {k: w for k, w in WEIGHTS.items() if scores.get(k) is not None}
    tot = sum(used.values())
    score = sum(w / tot * scores[k] for k, w in used.items())
    uncapped = score
    if not meets_limits: score = min(score, 49.0)
    coin = 1 - abs(p_payback - .5) * 2 if .1 < p_payback < .9 else 0
    width = 6 + 20 * (1 - evidence_strength) + 2 * min(critic_flags, 5) + 10 * coin
    return dict(score=float(score), uncapped=float(uncapped), low=float(max(0, score - width / 2)), high=float(min(100, score + width / 2)), width=float(width),
                weights={k: w / tot for k, w in used.items()},
                verdict="Promising" if score >= 70 else "Possible, but risky" if score >= 50 else "Weak as it stands" if score >= 35 else "Not viable as described")


def score_parts(scores, meets_limits):
    """The single score mixes three different questions, so it is also shown as three named parts.
    The overall score is capped at 49 when the plan misses the founder's own money limits: an attractive
    idea that does not pay back in time is not a viable plan."""
    avg = lambda *k: float(np.mean([scores[x] for x in k if scores.get(x) is not None]))
    parts = dict(market=dict(name="Market attractiveness", score=avg("market", "competition"), basis="Published statistics and the competition scan"),
                 customers=dict(name="Customer appeal", score=avg("customers"), basis="Simulated customers: a model, not real buyers"),
                 money=dict(name="Financial viability", score=avg("money"), basis="Payback and budget risk across simulated futures"))
    return dict(parts=parts, meets_limits=bool(meets_limits), capped=not meets_limits)


# ---------- Market sizing: top-down vs bottom-up ----------
def market_sizing(desc, pot, arpu, customers_end, agent_market):
    sam = desc["tam_aed"] * pot["catchment"]
    som_bottom_up = customers_end * arpu * 12
    tam_ai = (agent_market or {}).get("tam_aed"); som_ai = (agent_market or {}).get("som_aed")
    ratio = (max(som_ai, som_bottom_up) / max(min(som_ai, som_bottom_up), 1)) if som_ai and som_bottom_up else None
    return dict(tam_synthetic=desc["tam_aed"], tam_ai=tam_ai, sam=sam, som_bottom_up=som_bottom_up, som_top_down=som_ai, disagreement=ratio,
                flag=bool(ratio and ratio > 3),
                note=("The top-down and bottom-up estimates disagree by more than 3 times: treat the market size as unproven." if ratio and ratio > 3 else
                      "Top-down and bottom-up estimates are within 3 times of each other." if ratio else "Run with AI agents for a top-down estimate to compare."))


# ---------- Customer value ----------
def customer_value(ag, value_ratio, pain_adopters, price, wtp_sample):
    c = ag.get("customer") or {}
    gap = value_ratio - 1
    return dict(value_ratio=value_ratio, value_gap_score=float(np.clip(50 + 50 * np.tanh(gap), 0, 100)), pain_adopters=pain_adopters,
                jtbd=c.get("jtbd") or [], canvas=c.get("value_canvas") or {}, kano=c.get("kano") or [], pains=c.get("pains") or [],
                alternatives=c.get("alternatives") or [],
                wtp_hist=_hist(wtp_sample, price))


def _hist(x, price):
    x = np.asarray(x); hi = np.quantile(x, .97); edges = np.linspace(0, hi, 21)
    h, _ = np.histogram(np.clip(x, 0, hi), edges)
    return dict(edges=edges.round(1).tolist(), counts=h.tolist(), price=price, share_above_price=float((x >= price).mean()))


# ---------- Real-world tests ----------
def van_westendorp(rows):
    """rows: list of (too_cheap, cheap, expensive, too_expensive) prices per respondent.
    Returns the acceptable price range and the optimal price point."""
    a = np.array(rows, float)
    grid = np.linspace(a.min() * .8, a.max() * 1.2, 400)
    too_cheap = np.array([(a[:, 0] >= g).mean() for g in grid])      # share who think g is too cheap
    cheap = np.array([(a[:, 1] >= g).mean() for g in grid])
    expensive = np.array([(a[:, 2] <= g).mean() for g in grid])
    too_exp = np.array([(a[:, 3] <= g).mean() for g in grid])
    cross = lambda f, g: float(grid[np.argmin(np.abs(f - g))])
    return dict(n=len(a), opp=cross(too_cheap, too_exp), ipp=cross(cheap, expensive), pmc=cross(too_cheap, 1 - cheap), pme=cross(too_exp, 1 - expensive),
                curves=dict(price=grid[::10].round(1).tolist(), too_cheap=too_cheap[::10].round(3).tolist(), cheap=cheap[::10].round(3).tolist(),
                            expensive=expensive[::10].round(3).tolist(), too_expensive=too_exp[::10].round(3).tolist()))


def accept_at(rows, price):
    a = np.array(rows, float)
    ok = (a[:, 0] < price) & (a[:, 3] > price)
    return int(ok.sum()), len(a)


def sus_score(answers):
    """System Usability Scale: 10 answers from 1 to 5 -> score 0..100."""
    a = np.asarray(answers, float)
    odd, even = a[0::2] - 1, 5 - a[1::2]
    return float((odd.sum() + even.sum()) * 2.5)


def usability_test(users, tasks_done, tasks_total, sus_scores):
    success = tasks_done / max(tasks_total, 1)
    sus = float(np.mean(sus_scores)) if sus_scores else None
    score = 100 * success if sus is None else 0.5 * 100 * success + 0.5 * sus
    grade = None if sus is None else "excellent" if sus >= 80.3 else "good" if sus >= 68 else "below average" if sus >= 51 else "poor"
    return dict(users=users, success=success, sus=sus, sus_grade=grade, score=float(np.clip(score, 0, 100)))


def nps(promoters, passives, detractors):
    n = promoters + passives + detractors
    score = 100 * (promoters - detractors) / max(n, 1)
    return dict(n=n, nps=float(score), satisfaction=float(np.clip((promoters + .5 * passives) / max(n, 1), .02, .98)))


def holt_forecast(sales, horizon=12):
    """Holt's linear exponential smoothing; alpha and beta chosen by one-step-ahead error.
    Prediction interval from the residual spread, widening with the horizon."""
    y = np.asarray(sales, float); best = None
    for a in np.linspace(.1, .9, 9):
        for b in np.linspace(.05, .6, 12):
            l, t = y[0], y[1] - y[0]; err = []
            for v in y[1:]:
                f = l + t; err.append(v - f)
                nl = a * v + (1 - a) * (l + t); t = b * (nl - l) + (1 - b) * t; l = nl
            sse = float(np.sum(np.square(err)))
            if best is None or sse < best[0]: best = (sse, a, b, l, t, np.std(err) if len(err) > 1 else abs(err[0]))
    _, a, b, l, t, sd = best
    h = np.arange(1, horizon + 1); mean = l + h * t
    band = 1.28 * sd * np.sqrt(h)
    return dict(alpha=float(a), beta=float(b), history=y.tolist(), forecast=mean.round(1).tolist(), low=np.maximum(mean - band, 0).round(1).tolist(),
                high=(mean + band).round(1).tolist(), trend_per_month=float(t))


# ---------- Idea variants: generate, re-simulate, rank, recombine ----------
BUILTIN_VARIANTS = [
    dict(id="price-up", name="Raise the price by 15%", what="More per customer; fewer people accept it", changes=dict(price=15), tag="price"),
    dict(id="price-down", name="Cut the price by 15%", what="More people accept; less per customer", changes=dict(price=-15), tag="price"),
    dict(id="lean", name="Lean launch before a full fit-out", what="Shared space, dark kitchen or online first: lower rent and setup, less capacity", changes=dict(fixed=-30, setup=-50, capacity=-40, cac=10)),
    dict(id="niche", name="Focus on one high-value segment", what="Smaller market, cheaper to reach, more loyal", changes=dict(market=-40, cac=-30, churn=-15, price=5)),
    dict(id="onboarding", name="Make the first experience faster", what="Fewer steps to first value lifts satisfaction", changes=dict(satisfaction=10)),
    dict(id="membership", name="Add a membership or bundle", what="Customers stay longer and spend a bit more", changes=dict(churn=-25, price=8, var_pct=2)),
    dict(id="partners", name="Sell through partners", what="Delivery apps, marketplaces or institutions bring customers for a commission", changes=dict(cac=-35, var_pct=8)),
]
PCT_KEYS = ("price", "cac", "fixed", "setup", "churn", "capacity", "market")


def apply_changes_A(A, ch):
    """Apply a variant's changes to the assumption ranges (before the simulation)."""
    for k, v in (ch or {}).items():
        if k in ("price", "cac", "fixed", "setup", "churn", "capacity") and k in A:
            for f in ("min", "likely", "max"): A[k][f] *= 1 + v / 100
            A[k]["source"] += f"; changed {v:+.0f}% by an applied variant"
        if k == "var_pct" and k in A:
            for f in ("min", "likely", "max"): A[k][f] = float(np.clip(A[k][f] + v, 0, 95))


def change_inp(inp, ch):
    out = dict(inp)
    for k, v in (ch or {}).items():
        if k in ("cac", "fixed", "setup", "churn", "capacity", "market"):
            out[k] = tuple(x * (1 + v / 100) for x in inp[k])
        elif k == "price":
            out["arpu"] = tuple(x * (1 + v / 100) for x in inp["arpu"])
        elif k == "var_pct":
            out[k] = tuple(float(np.clip(x + v, 0, 95)) for x in inp[k])
        elif k == "satisfaction":
            out[k] = tuple(float(np.clip(x + v / 100, .02, .98)) for x in inp[k])
    return out


def all_variants(ag):
    out = [dict(v) for v in BUILTIN_VARIANTS]
    for i, p in enumerate((ag.get("critic") or {}).get("pivot_ideas") or []):
        if p.get("changes"):
            out.append(dict(id=f"ai-{i}", name=p["name"], what=p.get("why", ""), changes=p["changes"], ai=True))
    return out


def rank_variants(variants, inp, run, price_mult_market):
    """Each variant is re-simulated with the same random seed as the current plan (a fair
    comparison). The best three are crossed in pairs, like one generation of a genetic
    algorithm; a child is kept only if it beats both parents."""
    def go(ch):
        i2 = change_inp(inp, ch)
        if "price" in ch:  # price changes who buys: use the choice model's response
            i2["market"] = tuple(x * price_mult_market(1 + ch["price"] / 100) for x in i2["market"])
        s = run(i2, runs=P.RUNS_OPTION, keep_paths=False, journeys=False)
        return s["p_payback"], float(np.mean(s["npv"])), s["p_ruin"]
    bp, bn, br = go({})
    rows = []
    for v in variants:
        p, n, r = go(v["changes"])
        rows.append({**v, "p_payback": p, "npv_mean": n, "p_ruin": r, "d_payback": p - bp, "d_npv": n - bn})
    good = sorted([r for r in rows if r["d_npv"] > 0], key=lambda r: (-r["d_payback"], -r["d_npv"]))[:3]
    for i in range(len(good)):
        for j in range(i + 1, len(good)):
            a, b = good[i], good[j]
            if a.get("tag") and a.get("tag") == b.get("tag"): continue
            ch = dict(a["changes"])
            for k, v in b["changes"].items(): ch[k] = ch.get(k, 0) + v
            p, n, r = go(ch)
            if n > max(a["npv_mean"], b["npv_mean"]) and p >= max(a["p_payback"], b["p_payback"]) - .02:
                rows.append(dict(id=f"combo-{a['id']}-{b['id']}", name=f"{a['name']} + {b['name'][0].lower() + b['name'][1:]}", what="Recombined from two of the best changes",
                                 changes=ch, combo=True, p_payback=p, npv_mean=n, p_ruin=r, d_payback=p - bp, d_npv=n - bn))
    rows.sort(key=lambda r: (-r["d_payback"], -r["d_npv"]))
    return dict(base=dict(p_payback=bp, npv_mean=bn, p_ruin=br), variants=rows)


# ---------- Experiment kit ----------
def experiment_kit(it, ag, price, sample_landing, predicted_rate):
    kit = (ag.get("kit") or {})
    brief = (ag.get("orch") or {}).get("neutral_brief") or it["idea"]
    who = it.get("target_customer") or "your target customers"
    pain = ((ag.get("customer") or {}).get("pains") or [{}])[0].get("pain") or "the main problem"
    t = P.TYPES[it["business_type"]]["label"].lower()
    default = dict(
        landing=dict(headline=kit.get("headline") or f"{brief[:90]}", subheadline=kit.get("subheadline") or f"For {who} in {it.get('emirate')}.",
                     bullets=kit.get("bullets") or [f"Solves: {pain}", "Simple to start, no long contract", "Launching soon: be first in line"],
                     cta=kit.get("cta") or f"Join the waitlist (from AED {price:,.0f} a month)"),
        ads=kit.get("ads") or [dict(label="A: problem-led", text=f"Tired of {pain.lower()}? A new {t} for {who}. Join the waitlist."),
                               dict(label="B: benefit-led", text=f"The easier way for {who}. From AED {price:,.0f} a month. Join the waitlist.")],
        interview=kit.get("interview") or ["Tell me about the last time you dealt with this problem.", "How often does it happen?", "What do you use today, and what does it cost you?",
                                           "What is the most frustrating part?", "Have you looked for a better option? What happened?", "If this existed, what would make you switch?"],
        survey=["At what monthly price would this be so cheap you'd doubt the quality? (too cheap)", "At what price would it be a bargain? (cheap)",
                "At what price would it start to feel expensive? (expensive)", "At what price would it be too expensive to consider? (too expensive)"]
               + (kit.get("survey") or ["How often do you face this problem?", "What do you use today?", "Would you join a waitlist? (yes/no)"]),
        plan=[f"Run the landing page with ads A and B until each has about {sample_landing:,} visitors (predicted sign-up rate {predicted_rate:.1%}).",
              "Interview 10 target customers with the script; count how many describe strong, frequent pain.",
              "Send the 4 pricing questions to at least 30 target customers (Van Westendorp).",
              "Before launch, test the sign-up or ordering journey with 5 users and the 10 SUS questions."],
        source="ai" if kit else "template")
    return default


SUS_QUESTIONS = ["I think that I would like to use this system frequently.", "I found the system unnecessarily complex.", "I thought the system was easy to use.",
                 "I think that I would need the support of a technical person to be able to use this system.", "I found the various functions in this system were well integrated.",
                 "I thought there was too much inconsistency in this system.", "I would imagine that most people would learn to use this system very quickly.",
                 "I found the system very cumbersome to use.", "I felt very confident using the system.", "I needed to learn a lot of things before I could get going with this system."]
