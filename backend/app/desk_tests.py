"""Desk tests: checks a founder can run alone, without talking to a single customer.

ValidateUAE does not depend on real customer feedback. Most of what decides whether a business pays back can be
checked from the desk: what competitors charge and how busy they are, written quotes for rent, fit-out and
supplies, what an ad click costs, published churn figures, licence fees, how much one person can produce in a day.
Each test turns into an evidence-ledger record with an honest type and weight:

    written quote or price list      0.7   (rent, fit-out, supplier quotes)
    observed market data             0.5   (competitor prices, review counts, ad bids, timed trial runs)
    secondary research               0.4   (published churn or conversion benchmarks)

Simulations and AI still count for nothing. Tests that need customers (landing page, pricing, pilot) stay in the
validation lab as optional extras.
"""
import datetime as dt
import statistics

# Which test checks which forecast input (keys from the leak / tornado analysis)
FOR_INPUT = {"market": ["review_count", "search_check"], "arpu": ["competitor_prices"], "churn": ["churn_benchmark"], "cac": ["ad_cost"],
             "fixed": ["rent_quotes"], "setup": ["setup_quotes"], "var_pct": ["supplier_quotes"], "capacity": ["capacity_time"],
             "p": ["ad_cost"], "q": ["review_count"], "satisfaction": ["social_listening"]}
FOR_AREA = {"market": ["review_count", "search_check"], "price": ["competitor_prices"], "churn": ["churn_benchmark"], "cac": ["ad_cost"],
            "fixed": ["rent_quotes"], "setup": ["setup_quotes"], "var_pct": ["supplier_quotes"], "capacity": ["capacity_time"],
            "pain": ["social_listening"], "competition": ["competitor_prices"], "regulation": ["licence_check"]}

TESTS = {
    "competitor_prices": dict(
        name="Check what 5 competitors charge", area="price", days=1, input="arpu",
        checks="whether your price sits inside what the market already pays",
        steps=["List the 5 closest competitors (the Competition page has a starting list).",
               "Find each one's price for the offer closest to yours: website, delivery app, Instagram, or call as a customer.",
               "Write each as: name, monthly price in AED, link."],
        template="Hi, I'm looking at {offer} for {customer}. What does it cost per month, and is there a joining fee or minimum period?",
        fields=[("prices", "lines", "One competitor per line: name, monthly price in AED, link (optional)")]),
    "review_count": dict(
        name="Count competitors' reviews to estimate how many customers they win", area="market", days=1, input="market",
        checks="whether competitors already win as many customers a month as you need",
        steps=["Open Google Maps (or the delivery app) for the 3 competitors nearest to your location.",
               "Write down each one's number of reviews and roughly how long it has been open (the oldest review's date).",
               "The app converts reviews into customers using a published rule of thumb: only about 1 in 20 to 1 in 50 customers leaves a review."],
        template="", fields=[("rows", "lines", "One competitor per line: name, number of reviews, months open"), ("url", "text", "Link to one of the listings (makes the record checkable)")]),
    "search_check": dict(
        name="Measure Google search demand", area="market", days=1, input="market", page="Search demand",
        checks="how many people already look for this each month",
        steps=["Open Search demand.", "Check the suggested phrases, then fetch volumes (or upload a Keyword Planner export).", "Save: the record is added automatically."],
        template="", fields=[]),
    "ad_cost": dict(
        name="Look up what an ad click costs", area="cac", days=1, input="cac",
        checks="what it really costs to win a customer online",
        steps=["Open Google Ads Keyword Planner (free with a Google account) and search your 3-5 main phrases for the UAE.",
               "Write down the 'Top of page bid' low and high, in AED.",
               "Enter the share of visitors you expect to become customers. If you don't know, keep 2%: typical for small-business websites (published benchmarks put most between 1% and 4%)."],
        template="", fields=[("cpc_low", "money", "Top of page bid, low (AED)"), ("cpc_high", "money", "Top of page bid, high (AED)"),
                             ("conv", "percent", "Visitors who become customers (%)", 2.0), ("url", "text", "Link or screenshot reference (optional)")]),
    "rent_quotes": dict(
        name="Get 3 written rent quotes and price your staff", area="fixed", days=7, input="fixed",
        checks="your real monthly fixed costs",
        steps=["Ask 3 landlords or brokers (Bayut, Property Finder, Dubizzle) for written quotes for a suitable unit.",
               "Price staff: salaries plus visa, insurance and housing allowance, per month.",
               "Add other fixed costs: licence spread per month, software, utilities."],
        template="Hello, I'm looking for a {size} unit in {area} for a {business}. Could you send the annual rent, service charges, deposit and payment terms in writing?",
        fields=[("rents", "lines", "Monthly rent of each quote in AED (one per line)"), ("staff", "money", "Staff cost per month (AED)"),
                ("other", "money", "Other fixed costs per month (AED)"), ("url", "text", "Where the quotes are saved (optional)")]),
    "setup_quotes": dict(
        name="Get fit-out, equipment and licence quotes", area="setup", days=7, input="setup",
        checks="the real cash needed before opening",
        steps=["Ask 2-3 fit-out contractors and equipment suppliers for written quotes.",
               "Check the licence fee for your activity on the economic department or free-zone fee calculator.",
               "Add deposits and launch marketing."],
        template="Hello, we are fitting out a {size} {business} in {area}. Could you quote fit-out (including MEP and approvals) and the timeline?",
        fields=[("fitout", "lines", "Fit-out and equipment quotes in AED (one per line)"), ("licence", "money", "Licence and permits (AED)"),
                ("other", "money", "Deposits, launch marketing and other one-off costs (AED)"), ("url", "text", "Where the quotes are saved (optional)")]),
    "supplier_quotes": dict(
        name="Price your supplies and platform fees", area="var_pct", days=3, input="var_pct",
        checks="how much of each sale you keep",
        steps=["Ask 2 suppliers for a price list for the inputs of one typical sale.",
               "Look up the commission of the delivery apps or payment provider you will use.",
               "Enter the cost of one sale and the commission."],
        template="Hello, we need about {volume} a month of {items}. Could you send your price list and delivery terms?",
        fields=[("cogs", "money", "Cost of goods or delivery for one sale (AED)"), ("sale", "money", "Price of one sale (AED)"),
                ("commission", "percent", "Platform or card commission (%)", 0.0), ("url", "text", "Where the price lists are saved (optional)")]),
    "churn_benchmark": dict(
        name="Find a published churn figure for your category", area="churn", days=1, input="churn",
        checks="how long customers typically stay",
        steps=["Search for a published retention or churn figure for your category (industry report, listed competitor's annual report, trade association).",
               "Prefer UAE or GCC figures; global ones count less.", "Enter the monthly churn and the link."],
        template="", fields=[("churn", "percent", "Monthly churn (% of customers who leave each month)"), ("geo", "choice", "Where the figure is from", ["uae", "gcc", "global"]),
                             ("url", "text", "Link to the source")]),
    "capacity_time": dict(
        name="Time a trial run of your operation", area="capacity", days=2, input="capacity",
        checks="how many customers you can really serve",
        steps=["Run your core task for a few hours as if open: cook the meals, run the class, deliver the lesson.",
               "Count how many units you finish per hour with the staff you plan.", "Enter the numbers; the app works out customers per month."],
        template="", fields=[("per_hour", "number", "Units finished per hour"), ("hours", "number", "Working hours a day"), ("days", "number", "Working days a month", 26),
                             ("per_customer", "number", "Units one customer uses a month")]),
    "licence_check": dict(
        name="Confirm your licence activity and fee", area="regulation", days=2, input=None,
        checks="that you can legally operate as planned, and what it costs",
        steps=["Find your activity on the economic department (DET in Dubai, ADDED in Abu Dhabi, SEDD in Sharjah) or free-zone activity list.",
               "Check whether it needs extra approvals (municipality, KHDA, DHA, civil defence).", "Enter the activity, the authority and the link."],
        template="", fields=[("activity", "text", "Licence activity name"), ("authority", "text", "Authority"), ("fee", "money", "Licence fee (AED)"),
                             ("approvals", "text", "Extra approvals needed (if any)"), ("url", "text", "Link")]),
    "social_listening": dict(
        name="Read what people already complain about", area="pain", days=1, input="satisfaction", page="Social listening",
        checks="whether people already feel the problem, in their own words",
        steps=["Open Social listening.", "Collect or paste 20+ public comments from Google reviews, Instagram, Reddit or YouTube about competitors.",
               "Save: the record is added automatically."], template="", fields=[]),
}


def _lines(txt):
    return [l.strip() for l in (txt or "").splitlines() if l.strip()]


def _num(x):
    try: return float(str(x).replace(",", "").replace("AED", "").replace("%", "").strip())
    except (TypeError, ValueError): return None


def recommend(result, state, done=None, top=3):
    """The desk tests worth doing next: the inputs that move the answer most, minus what is already done."""
    done = set(done or [])
    order = []
    for row in (result.get("leak") or {}).get("rows", []):
        for k in FOR_INPUT.get(row["key"], []):
            if k not in order: order.append(k)
    for g in (result.get("evidence") or {}).get("gaps", []):
        for k in FOR_AREA.get(g["area"], []):
            if k not in order: order.append(k)
    for k in TESTS:
        if k not in order: order.append(k)
    share = {k: 0.0 for k in TESTS}
    for row in (result.get("leak") or {}).get("rows", []):
        for k in FOR_INPUT.get(row["key"], []): share[k] = max(share[k], row["variance_share"])
    return [dict(key=k, **TESTS[k], uncertainty_share=share[k]) for k in order if k not in done][:top]


def fill(template, result):
    it = result["intake"]
    return template.format(offer=(result.get("idea") or {}).get("brief", it.get("idea", ""))[:80], customer=it.get("target_customer") or "customers",
                           size="suitable", area=it.get("emirate") or "the UAE", business=it.get("business_type"), volume="our expected volume", items="your inputs")


def evaluate(key, v, result):
    """Turn the founder's entries into (ledger record, plain-language finding, direction vs the plan).
    direction: 'better', 'worse' or 'in line' with what the forecast assumed. Raises ValueError on bad input."""
    A = result["assumptions"]; it = result["intake"]
    today = dt.date.today().isoformat(); url = (v.get("url") or "").strip()
    base = dict(collected_on=today, geography="target", confidence="medium", verification="partly" if url else "unverified", source_url=url,
                description=f"Desk test: {TESTS[key]['name']}.")
    plan = lambda k: A[k]["likely"]

    def rel(actual, planned, higher_is_good):
        if planned == 0: return "in line"
        d = (actual - planned) / planned
        if abs(d) < .1: return "in line"
        return "better" if (d > 0) == higher_is_good else "worse"

    if key == "competitor_prices":
        rows = []
        for l in _lines(v.get("prices")):
            parts = [x.strip() for x in l.split(",")]
            p = next((_num(x) for x in parts[1:] if _num(x)), None)
            if p: rows.append((parts[0], p, next((x for x in parts if x.startswith("http")), "")))
        if len(rows) < 2: raise ValueError("Enter at least 2 competitors with a price.")
        ps = sorted(r[1] for r in rows); mine = plan("price")
        rank = sum(p < mine for p in ps) / len(ps)
        med = statistics.median(ps)
        finding = (f"Your price AED {mine:,.0f} sits above {rank:.0%} of {len(ps)} competitors (they charge AED {ps[0]:,.0f}–{ps[-1]:,.0f}, median AED {med:,.0f}).")
        direction = "worse" if mine > ps[-1] * 1.05 else "better" if mine < med * .9 else "in line"
        if direction == "worse": finding += " You are dearer than everyone checked: you need a clear reason to pay more."
        rec = dict(base, claim=f"{len(ps)} competitor prices: AED {ps[0]:,.0f}–{ps[-1]:,.0f} (median {med:,.0f}); yours AED {mine:,.0f}", area="price", ev_type="observation",
                   verification="partly" if any(r[2] for r in rows) or url else "unverified",
                   source_url=url or next((r[2] for r in rows if r[2]), ""), description=base["description"] + " " + "; ".join(f"{n}: AED {p:,.0f}" for n, p, _ in rows),
                   limitations="Listed prices; discounts and bundles may differ. Shows the market's range, not what customers will pay you.")
        return rec, finding, direction
    if key == "review_count":
        rows = []
        for l in _lines(v.get("rows")):
            parts = [x.strip() for x in l.split(",")]
            nums = [_num(x) for x in parts[1:] if _num(x) is not None]
            if len(nums) >= 2 and nums[1] > 0: rows.append((parts[0], nums[0], nums[1]))
        if not rows: raise ValueError("Enter at least one competitor as: name, reviews, months open.")
        per_month = [r / m for _, r, m in rows]
        lo, hi = statistics.mean(per_month) * 20, statistics.mean(per_month) * 50
        need = result["unit"]["bep_customers"]; churn = plan("churn") / 100
        need_new = need * max(churn, .02)
        finding = (f"The competitors checked win roughly {lo:,.0f}–{hi:,.0f} new customers a month each (from {sum(r for _, r, _ in rows):,.0f} reviews). "
                   f"To hold the {need:,.0f} customers you need, you must win about {need_new:,.0f} a month.")
        direction = "better" if lo >= need_new else "worse" if hi < need_new else "in line"
        finding += {"better": " Competitors already do this: demand at this scale exists.", "worse": " Even busy competitors win fewer than you need: the plan may be too ambitious.",
                    "in line": " You would need to do about as well as an established competitor."}[direction]
        rec = dict(base, claim=f"{len(rows)} competitors: about {lo:,.0f}–{hi:,.0f} new customers a month each (review count method)", area="market", ev_type="observation",
                   limitations="Assumes 1 in 20 to 1 in 50 customers leaves a review (a rule of thumb); review habits differ by category.")
        return rec, finding, direction
    if key == "ad_cost":
        lo, hi = _num(v.get("cpc_low")), _num(v.get("cpc_high")); conv = (_num(v.get("conv")) or 2) / 100
        if not lo or not hi or conv <= 0: raise ValueError("Enter both bids and a conversion share above 0.")
        lo, hi = sorted([lo, hi]); mid = (lo + hi) / 2
        cac = (mid / conv, lo / (conv * 1.5), hi / (conv * .6))
        finding = f"Online, a customer would cost about AED {cac[0]:,.0f} (AED {cac[1]:,.0f}–{cac[2]:,.0f}); the plan assumed AED {plan('cac'):,.0f}."
        direction = rel(cac[0], plan("cac"), False)
        rec = dict(base, claim=f"Google Ads bids AED {lo:,.2f}–{hi:,.2f} a click; at {conv:.1%} conversion, about AED {cac[0]:,.0f} per customer", area="cac", ev_type="observation",
                   value_min=cac[1], value_likely=cac[0], value_max=cac[2],
                   limitations="Bids are Google's estimates; the conversion share is an assumption until you run ads. Other channels (referrals, walk-ins) can be cheaper.")
        return rec, finding, direction
    if key == "rent_quotes":
        rents = [x for x in (_num(l) for l in _lines(v.get("rents"))) if x]
        if not rents: raise ValueError("Enter at least one rent quote.")
        staff, other = _num(v.get("staff")) or 0, _num(v.get("other")) or 0
        tot = [r + staff + other for r in rents]
        mid = statistics.median(tot)
        finding = f"Real fixed costs come to about AED {mid:,.0f} a month (AED {min(tot):,.0f}–{max(tot):,.0f}); the plan assumed AED {plan('fixed'):,.0f}."
        direction = rel(mid, plan("fixed"), False)
        rec = dict(base, claim=f"{len(rents)} rent quote(s) plus staff and other costs: AED {mid:,.0f} a month", area="fixed", ev_type="quote", sample_size=len(rents),
                   value_min=min(tot) * .97, value_likely=mid, value_max=max(tot) * 1.08, confidence="high" if len(rents) >= 3 else "medium",
                   limitations="Quotes can change before signing; staff costs are the founder's estimate.")
        return rec, finding, direction
    if key == "setup_quotes":
        fit = [x for x in (_num(l) for l in _lines(v.get("fitout"))) if x]
        if not fit: raise ValueError("Enter at least one fit-out or equipment quote.")
        extra = (_num(v.get("licence")) or 0) + (_num(v.get("other")) or 0)
        tot = [f + extra for f in fit]; mid = statistics.median(tot)
        finding = f"Setup comes to about AED {mid:,.0f} (AED {min(tot):,.0f}–{max(tot):,.0f}); the plan assumed AED {plan('setup'):,.0f}."
        direction = rel(mid, plan("setup"), False)
        rec = dict(base, claim=f"{len(fit)} setup quote(s) plus licence and other one-off costs: AED {mid:,.0f}", area="setup", ev_type="quote", sample_size=len(fit),
                   value_min=min(tot) * .97, value_likely=mid, value_max=max(tot) * 1.15, confidence="high" if len(fit) >= 2 else "medium",
                   limitations="Fit-outs usually overrun; the upper value adds 15%.")
        return rec, finding, direction
    if key == "supplier_quotes":
        cogs, sale, com = _num(v.get("cogs")), _num(v.get("sale")), _num(v.get("commission")) or 0
        if not cogs or not sale: raise ValueError("Enter the cost and the price of one sale.")
        pct = cogs / sale * 100 + com
        finding = f"You keep about {100 - pct:.0f}% of each sale: variable costs are {pct:.0f}% against {plan('var_pct'):.0f}% in the plan."
        direction = rel(pct, plan("var_pct"), False)
        rec = dict(base, claim=f"Supplier and platform prices: variable cost {pct:.1f}% of each sale", area="var_pct", ev_type="quote",
                   value_min=pct * .92, value_likely=pct, value_max=pct * 1.1, limitations="Prices for one typical sale; the mix of products will vary.")
        return rec, finding, direction
    if key == "churn_benchmark":
        c = _num(v.get("churn")); geo = v.get("geo") or "global"
        if c is None or not 0 < c < 100: raise ValueError("Enter monthly churn as a percentage between 0 and 100.")
        if not url: raise ValueError("Add the link to the source: a benchmark without a source can't be checked.")
        finding = f"A published figure puts monthly churn at {c:.1f}%; the plan assumed {plan('churn'):.1f}%."
        direction = rel(c, plan("churn"), False)
        rec = dict(base, claim=f"Published benchmark: {c:.1f}% monthly churn", area="churn", ev_type="secondary", geography=geo, verification="partly",
                   value_min=c * .75, value_likely=c, value_max=c * 1.3, limitations="A benchmark for the category, not your own customers.")
        return rec, finding, direction
    if key == "capacity_time":
        ph, hrs, days, per = (_num(v.get(k)) for k in ("per_hour", "hours", "days", "per_customer"))
        if not all([ph, hrs, days, per]): raise ValueError("Fill in all four numbers.")
        capc = ph * hrs * days / per
        finding = f"Your operation can serve about {capc:,.0f} customers a month; the plan assumed {plan('capacity'):,.0f}."
        direction = rel(capc, plan("capacity"), True)
        rec = dict(base, claim=f"Timed trial run: {ph:g} units an hour → about {capc:,.0f} customers a month", area="capacity", ev_type="observation", verification="partly",
                   value_min=capc * .8, value_likely=capc, value_max=capc * 1.1, limitations="A trial run without real orders; busy periods and breakdowns lower capacity.")
        return rec, finding, direction
    if key == "licence_check":
        if not (v.get("activity") and url): raise ValueError("Enter the activity name and the link.")
        finding = f"Licence activity “{v['activity']}” confirmed with {v.get('authority') or 'the authority'}" + (f", fee about AED {_num(v.get('fee')):,.0f}" if _num(v.get("fee")) else "") + \
                  (f"; extra approvals: {v['approvals']}." if v.get("approvals") else ".")
        rec = dict(base, claim=f"Licence activity confirmed: {v['activity']}", area="regulation", ev_type="secondary", verification="partly",
                   limitations="Rules change; confirm again before applying.")
        return rec, finding, "in line"
    raise ValueError("This test is done on its own page.")
