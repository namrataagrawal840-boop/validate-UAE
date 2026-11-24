"""AI research agents (Claude API with web search).

Every agent returns JSON. Numbers backed by a source URL are labelled
"Benchmarked (web source)"; numbers without one are "AI estimate". If no API key
is set, or an agent fails, the funnel falls back to category priors and says so.
"""
import json
import os
import re
import concurrent.futures as cf

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
SEARCH_TOOL = os.getenv("WEB_SEARCH_TOOL", "web_search_20250305")
RULES = ("Be realistic and conservative; never flatter the idea. Money in UAE dirhams (AED). "
         "Prefer UAE-specific sources (government portals, official statistics, reputable news, company websites). "
         "Never invent a source: only give a URL you actually found in your search results. "
         "End your answer with ONE ```json code block in exactly this shape:")


def enabled():
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def ctx(it):
    from .priors import TYPES
    return (f"Idea (neutral brief): {it.get('_brief') or it['idea']}\nBusiness type: {TYPES[it['business_type']]['label']}. "
            f"Location: {it.get('emirate') or 'All UAE'}. Setup: {it.get('setup')}. Target customer: {it.get('target_customer') or 'not specified'}.")


R3 = '{"min": 0, "likely": 0, "max": 0, "source": "", "url": ""}'
PROMPTS = {
    "orch": lambda it: f"""You are the orchestrator of ValidateUAE, which tests new business ideas for the UAE.
Founder's words: \"\"\"{it['idea']}\"\"\"
Rewrite the idea as a neutral, factual brief of 2-3 sentences with all hype removed. Fill a Lean Canvas in short phrases. List the 5 assumptions it depends on most.
{RULES}
{{"neutral_brief": "", "lean_canvas": {{"problem": "", "customer_segments": "", "unique_value": "", "solution": "", "channels": "", "revenue_streams": "", "cost_structure": "", "key_metrics": "", "unfair_advantage": ""}}, "key_assumptions": ["", "", "", "", ""]}}""",
    "market": lambda it: f"""You are the market research agent of ValidateUAE. Search the web.
{ctx(it)}
Estimate the yearly spend in this category in the location (tam_aed), what one new business could capture in 3 years (som_aed), the number of people or businesses it could realistically reach (reachable_customers) and yearly growth. Give 2-4 trends with their URLs.
{RULES}
{{"tam_aed": 0, "tam_reasoning": "", "som_aed": 0, "reachable_customers": 0, "growth_pct_per_year": 0, "trends": [{{"text": "", "url": ""}}]}}""",
    "customer": lambda it: f"""You are the customer research agent of ValidateUAE. Search the web for real customer complaints, reviews and forum posts about this problem in the UAE (Google reviews pages, Reddit r/dubai or r/UAE, news, app store reviews).
{ctx(it)}
Return the 5 main pains (intensity 0-100, where 50 = annoying but tolerated, 80 = people actively look for a fix) and 6-15 short evidence snippets: each a real complaint paraphrased in under 25 words with the URL where you found it. Also list current alternatives with their monthly cost and what a typical customer would pay per month. Describe the customer's jobs-to-be-done (functional, emotional, social), fill a Value Proposition Canvas (customer jobs, pains, gains; and the idea's pain relievers, gain creators, products and services), and classify 4-6 features with the Kano model.
{RULES}
{{"pains": [{{"pain": "", "intensity": 0, "url": ""}}], "evidence": [{{"quote": "", "url": ""}}], "alternatives": [{{"name": "", "monthly_cost_aed": 0, "url": ""}}], "wtp_aed": {{"min": 0, "likely": 0, "max": 0}}, "jtbd": [{{"type": "functional", "job": ""}}], "value_canvas": {{"jobs": [""], "pains": [""], "gains": [""], "pain_relievers": [""], "gain_creators": [""], "products": [""]}}, "kano": [{{"feature": "", "category": "must-have"}}]}}""",
    "competition": lambda it: f"""You are the competition agent of ValidateUAE. Search the web for real competitors operating in the UAE.
{ctx(it)}
List 5-8 real businesses already doing the same or a very similar thing in the UAE (prefer the same emirate): direct = same offer to the same customers; indirect = different offer, same need; substitute = what people do instead. Only name businesses you found in search results, and give the URL where you found each.
For each: where it operates, typical spend per customer per month in AED as a number (price_aed; null if not found) and the price as written (price_point), public rating out of 5 if you found one (else null), what it offers (note), 2-3 strengths, 2-3 weaknesses (from reviews where possible), and the features it offers as short phrases (e.g. "Online booking", "Women-only sessions").
Score Porter's five forces 1 (weak pressure) to 5 (strong). differentiation 0-100 = how clearly this idea stands apart. gaps = needs competitors leave unmet; moats = what could protect this idea.
{RULES}
{{"competitors": [{{"name": "", "type": "direct", "location": "", "price_aed": null, "price_point": "", "rating": null, "note": "", "strengths": [""], "weaknesses": [""], "features": [""], "url": ""}}], "forces": {{"rivalry": 3, "new_entrants": 3, "substitutes": 3, "buyer_power": 3, "supplier_power": 3}}, "differentiation": 0, "gaps": [""], "moats": [""]}}""",
    "finance": lambda it: f"""You are the finance agent of ValidateUAE. Search the web for current UAE costs: commercial rent for the area, trade licence and visa costs, salaries, supplier or platform commissions, typical ad costs.
{ctx(it)}
Give low/likely/high ranges. price = average revenue per active customer per month. var_pct = % of revenue spent per sale (ingredients, stock, commissions, payment fees). fixed = monthly rent, salaries, visas, licence spread monthly, software. setup = one-off licence, fit-out, equipment, deposits. cac = cost to win one paying customer. churn = % of active customers lost per month. capacity = most active customers per month at launch size. For each field give the source name and URL you used, or leave url empty if it is your estimate.
{RULES}
{{"fields": {{"price": {R3}, "var_pct": {R3}, "fixed": {R3}, "setup": {R3}, "cac": {R3}, "churn": {R3}, "capacity": {R3}}}, "cost_breakdown": [{{"item": "", "monthly_aed": 0, "url": ""}}], "reasoning": ""}}""",
    "regulation": lambda it: f"""You are the regulation agent of ValidateUAE. Search official UAE sources (the emirate's economic department, free-zone authorities, municipality, relevant regulators).
{ctx(it)}
Which licence and approvals does this activity need, from which authority, roughly what cost and timeline? List anything that would block the idea entirely as hard_blockers (leave empty if none).
{RULES}
{{"licence_type": "", "authority": "", "approvals": [{{"name": "", "note": "", "url": ""}}], "cost_aed": {{"min": 0, "max": 0}}, "timeline_weeks": {{"min": 0, "max": 0}}, "hard_blockers": [], "notes": "", "url": ""}}""",
    "usability": lambda it: f"""You are the ease-of-use agent of ValidateUAE.
{ctx(it)}
Describe the customer journey from first hearing about the business to getting real value, as short steps. Check it against Nielsen's 10 usability heuristics (or service-design equivalents for a physical business). 2-5 issues, severity 1 minor, 2 major, 3 critical.
{RULES}
{{"flow_steps": [{{"step": "", "note": ""}}], "steps_to_first_value": 0, "issues": [{{"heuristic": "", "issue": "", "severity": 1}}], "suggestions": [""]}}""",
    "critic": lambda it, summary: f"""You are the red-team critic of ValidateUAE. Your job is to prevent false positives.
{ctx(it)}
Other agents found: {summary}
1) Pre-mortem: it is 2 years later and the business failed. Give the 3-5 most likely reasons. 2) Check the other agents' numbers and sources for optimism or weak evidence. 3) market_haircut (0.4-1): multiply the market estimate by this if it looks inflated. cac_uplift (1-1.8): multiply customer acquisition cost by this if it looks too low. 4) Suggest 2-3 pivots that would fix the biggest weaknesses, each with its expected effect on the model as changes: price, cac, fixed, setup, churn, capacity and market in percent; var_pct and satisfaction in percentage points (each between -50 and 50; leave unchanged ones out). 5) Score the idea with this rubric, 1 (poor) to 5 (excellent), each with a one-line reason: problem severity, solution fit, differentiation, feasibility in the UAE, timing. You must find at least one real weakness.
{RULES}
{{"pre_mortem": ["", "", ""], "weak_claims": [{{"agent": "", "claim": "", "why": ""}}], "market_haircut": 1, "cac_uplift": 1, "pivot_ideas": [{{"name": "", "why": "", "changes": {{"price": 0}}}}], "rubric": [{{"criterion": "Problem severity", "score": 3, "reason": ""}}], "verdict_note": ""}}""",
    "consistency": lambda it: f"""You are an independent cost estimator for ValidateUAE. Do not search; use your own knowledge of UAE costs.
{ctx(it)}
Give low/likely/high ranges for: price (average revenue per active customer per month, AED), var_pct (% of revenue spent per sale), fixed (monthly fixed costs, AED), setup (one-off, AED), cac (cost to win one paying customer, AED), churn (% of customers lost per month), capacity (most active customers per month at launch size).
{RULES}
{{"fields": {{"price": {R3}, "var_pct": {R3}, "fixed": {R3}, "setup": {R3}, "cac": {R3}, "churn": {R3}, "capacity": {R3}}}}}""",
    "kit": lambda it: f"""You write validation experiments for ValidateUAE.
{ctx(it)}
Write: a landing page (headline under 10 words, subheadline, 3 benefit bullets, call to action for a waitlist); two short ads for an A/B test (A problem-led, B benefit-led, under 25 words each, suitable for Instagram in the UAE); 6 open interview questions that avoid leading the customer (ask about past behaviour, not opinions about the idea); 3 extra survey questions. Plain English.
{RULES}
{{"headline": "", "subheadline": "", "bullets": ["", "", ""], "cta": "", "ads": [{{"label": "A: problem-led", "text": ""}}, {{"label": "B: benefit-led", "text": ""}}], "interview": ["", "", "", "", "", ""], "survey": ["", "", ""]}}""",
}
SEARCH = {"market": 4, "customer": 6, "competition": 5, "finance": 6, "regulation": 4}


def parse_json(text):
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    cand = blocks[-1] if blocks else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(cand)


def call(prompt, max_searches=0, max_tokens=6000):
    from anthropic import Anthropic
    client = Anthropic()
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": SEARCH_TOOL, "name": "web_search", "max_uses": max_searches}] if max_searches else None
    texts, urls = [], {}
    for _ in range(4):
        kw = dict(model=MODEL, max_tokens=max_tokens, messages=messages)
        if tools: kw["tools"] = tools
        r = client.messages.create(**kw)
        for b in r.content:
            if b.type == "text":
                texts.append(b.text)
                for c in getattr(b, "citations", None) or []:
                    u = getattr(c, "url", None)
                    if u: urls[u] = getattr(c, "title", "") or u
            elif b.type == "web_search_tool_result" and isinstance(getattr(b, "content", None), list):
                for x in b.content:
                    u = getattr(x, "url", None)
                    if u: urls.setdefault(u, getattr(x, "title", "") or u)
        if r.stop_reason == "pause_turn":
            messages = [{"role": "user", "content": prompt}, {"role": "assistant", "content": r.content}]
            continue
        break
    return parse_json("\n".join(texts)), urls


# ---------- cleaning: never trust raw model output ----------
def num(x, lo, hi, d=None):
    try:
        v = float(x)
        return min(max(v, lo), hi) if v == v else d
    except (TypeError, ValueError):
        return d


def s(x, n=400):
    return x.strip()[:n] if isinstance(x, str) and x.strip() else ""


def url_ok(u, found):
    """Keep a URL only if it is http(s) and actually appeared in the search results."""
    u = s(u, 500)
    return u if u.startswith("http") and (not found or u in found or any(u.split("?")[0].rstrip("/") == f.split("?")[0].rstrip("/") for f in found)) else ""


def clean(name, v, found):
    v = v if isinstance(v, dict) else {}
    L = lambda x, f, n=10: [y for y in (f(i) for i in (x if isinstance(x, list) else [])[:n]) if y]
    if name == "orch":
        return dict(neutral_brief=s(v.get("neutral_brief"), 800), lean_canvas={k: s(x, 200) for k, x in (v.get("lean_canvas") or {}).items()},
                    key_assumptions=L(v.get("key_assumptions"), lambda x: s(x, 200), 6))
    if name == "market":
        return dict(tam_aed=num(v.get("tam_aed"), 0, 1e12), tam_reasoning=s(v.get("tam_reasoning"), 600), som_aed=num(v.get("som_aed"), 0, 1e11),
                    reachable_customers=num(v.get("reachable_customers"), 0, 2e7), growth_pct_per_year=num(v.get("growth_pct_per_year"), -50, 100),
                    trends=L(v.get("trends"), lambda t: s(t.get("text"), 300) and dict(text=s(t.get("text"), 300), url=url_ok(t.get("url"), found)) if isinstance(t, dict) else None, 5))
    if name == "customer":
        w = v.get("wtp_aed") or {}
        return dict(pains=L(v.get("pains"), lambda p: isinstance(p, dict) and s(p.get("pain")) and dict(pain=s(p.get("pain"), 200), intensity=num(p.get("intensity"), 0, 100, 50), url=url_ok(p.get("url"), found)), 6),
                    evidence=L(v.get("evidence"), lambda e: isinstance(e, dict) and s(e.get("quote")) and dict(quote=s(e.get("quote"), 240), url=url_ok(e.get("url"), found)), 20),
                    alternatives=L(v.get("alternatives"), lambda a: isinstance(a, dict) and s(a.get("name")) and dict(name=s(a.get("name"), 120), monthly_cost_aed=num(a.get("monthly_cost_aed"), 0, 1e6, 0), url=url_ok(a.get("url"), found)), 6),
                    wtp_aed=dict(min=num(w.get("min"), 0, 1e6), likely=num(w.get("likely"), 0, 1e6), max=num(w.get("max"), 0, 1e6)),
                    jtbd=L(v.get("jtbd"), lambda j: isinstance(j, dict) and s(j.get("job")) and dict(type=s(j.get("type"), 20) or "functional", job=s(j.get("job"), 240)), 6),
                    value_canvas={k: L((v.get("value_canvas") or {}).get(k), lambda x: s(x, 200), 6) for k in ("jobs", "pains", "gains", "pain_relievers", "gain_creators", "products")},
                    kano=L(v.get("kano"), lambda k: isinstance(k, dict) and s(k.get("feature")) and dict(feature=s(k.get("feature"), 160), category=k.get("category") if k.get("category") in ("must-have", "performance", "delighter", "indifferent") else "performance"), 8))
    if name == "competition":
        f = v.get("forces") or {}
        return dict(competitors=L(v.get("competitors"), lambda c: isinstance(c, dict) and s(c.get("name")) and dict(name=s(c.get("name"), 120), type=c.get("type") if c.get("type") in ("direct", "indirect", "substitute") else "direct", location=s(c.get("location"), 80),
                                price_aed=num(c.get("price_aed"), 1, 1e6), price_point=s(c.get("price_point"), 80), rating=num(c.get("rating"), 0, 5), note=s(c.get("note"), 240),
                                strengths=L(c.get("strengths"), lambda x: s(x, 120), 3), weaknesses=L(c.get("weaknesses"), lambda x: s(x, 120), 3),
                                features=L(c.get("features"), lambda x: s(x, 60), 8), url=url_ok(c.get("url"), found)), 8),
                    forces={k: num(f.get(k), 1, 5, 3) for k in ["rivalry", "new_entrants", "substitutes", "buyer_power", "supplier_power"]},
                    differentiation=num(v.get("differentiation"), 0, 100, 40), gaps=L(v.get("gaps"), lambda x: s(x, 240), 5), moats=L(v.get("moats"), lambda x: s(x, 240), 5))
    if name == "finance":
        bounds = dict(price=(1, 1e6), var_pct=(0, 95), fixed=(0, 1e8), setup=(0, 1e9), cac=(1, 1e6), churn=(.2, 60), capacity=(1, 1e7))
        fields = {}
        for k, (lo, hi) in bounds.items():
            x = (v.get("fields") or {}).get(k) or {}
            vals = [num(x.get(f), lo, hi) for f in ("min", "likely", "max")]
            if None in vals or vals[1] <= 0 and k != "var_pct": continue
            vals.sort(); fields[k] = dict(min=vals[0], likely=vals[1], max=vals[2], source=s(x.get("source"), 160) or "Finance agent", url=url_ok(x.get("url"), found))
        return dict(fields=fields, cost_breakdown=L(v.get("cost_breakdown"), lambda c: isinstance(c, dict) and s(c.get("item")) and dict(item=s(c.get("item"), 120), monthly_aed=num(c.get("monthly_aed"), 0, 1e8, 0), url=url_ok(c.get("url"), found)), 12),
                    reasoning=s(v.get("reasoning"), 800))
    if name == "regulation":
        c, t = v.get("cost_aed") or {}, v.get("timeline_weeks") or {}
        return dict(licence_type=s(v.get("licence_type"), 160), authority=s(v.get("authority"), 160),
                    approvals=L(v.get("approvals"), lambda a: isinstance(a, dict) and s(a.get("name")) and dict(name=s(a.get("name"), 160), note=s(a.get("note"), 240), url=url_ok(a.get("url"), found)), 10),
                    cost_aed=dict(min=num(c.get("min"), 0, 1e8), max=num(c.get("max"), 0, 1e8)), timeline_weeks=dict(min=num(t.get("min"), 0, 200), max=num(t.get("max"), 0, 200)),
                    hard_blockers=L(v.get("hard_blockers"), lambda x: s(x, 240), 5), notes=s(v.get("notes"), 600), url=url_ok(v.get("url"), found))
    if name == "usability":
        return dict(flow_steps=L(v.get("flow_steps"), lambda x: isinstance(x, dict) and s(x.get("step")) and dict(step=s(x.get("step"), 160), note=s(x.get("note"), 240)), 12),
                    steps_to_first_value=num(v.get("steps_to_first_value"), 1, 15, 4),
                    issues=L(v.get("issues"), lambda x: isinstance(x, dict) and s(x.get("issue")) and dict(heuristic=s(x.get("heuristic"), 120), issue=s(x.get("issue"), 240), severity=int(num(x.get("severity"), 1, 3, 1))), 6),
                    suggestions=L(v.get("suggestions"), lambda x: s(x, 240), 5))
    if name == "critic":
        return dict(pre_mortem=L(v.get("pre_mortem"), lambda x: s(x, 300), 5), weak_claims=L(v.get("weak_claims"), lambda w: isinstance(w, dict) and s(w.get("claim")) and dict(agent=s(w.get("agent"), 60), claim=s(w.get("claim"), 240), why=s(w.get("why"), 300)), 6),
                    market_haircut=num(v.get("market_haircut"), .4, 1, 1), cac_uplift=num(v.get("cac_uplift"), 1, 1.8, 1),
                    pivot_ideas=L(v.get("pivot_ideas"), lambda p: isinstance(p, dict) and s(p.get("name")) and dict(name=s(p.get("name"), 160), why=s(p.get("why"), 300),
                        changes={k: num(x, -50, 50, 0) for k, x in (p.get("changes") or {}).items() if k in ("price", "cac", "fixed", "setup", "churn", "capacity", "market", "var_pct", "satisfaction") and num(x, -50, 50, 0)}), 4),
                    rubric=L(v.get("rubric"), lambda r: isinstance(r, dict) and s(r.get("criterion")) and dict(criterion=s(r.get("criterion"), 60), score=int(num(r.get("score"), 1, 5, 3)), reason=s(r.get("reason"), 240)), 6),
                    verdict_note=s(v.get("verdict_note"), 400))
    if name == "consistency":
        return clean("finance", v, found)
    if name == "kit":
        return dict(headline=s(v.get("headline"), 120), subheadline=s(v.get("subheadline"), 200), bullets=L(v.get("bullets"), lambda x: s(x, 160), 4), cta=s(v.get("cta"), 80),
                    ads=L(v.get("ads"), lambda a: isinstance(a, dict) and s(a.get("text")) and dict(label=s(a.get("label"), 40) or "Ad", text=s(a.get("text"), 300)), 2),
                    interview=L(v.get("interview"), lambda x: s(x, 200), 8), survey=L(v.get("survey"), lambda x: s(x, 200), 5))
    return {}


def summarise(ag):
    keep = {k: ag.get(k) for k in ("market", "customer", "competition", "finance", "regulation")}
    if keep.get("customer"): keep["customer"] = {**keep["customer"], "evidence": keep["customer"].get("evidence", [])[:4]}
    return json.dumps(keep, default=str)[:12000]


def run_agents(intake, progress):
    """Returns (agents, sources, errors). progress(stage, status, text)."""
    agents, sources, errors = {}, {}, {}

    def one(name, prompt, searches):
        progress(name, "working", "")
        try:
            raw, found = call(prompt, searches)
            out = clean(name, raw, set(found))
            agents[name] = out; sources[name] = [dict(url=u, title=t) for u, t in found.items()]
            progress(name, "done", line(name, out, len(found)))
        except Exception as e:  # noqa: BLE001 - any failure falls back to priors
            errors[name] = str(e)[:300]
            progress(name, "fallback", "Could not complete; the funnel uses category priors for this part.")

    one("orch", PROMPTS["orch"](intake), 0)
    it = {**intake, "_brief": (agents.get("orch") or {}).get("neutral_brief")}
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(one, n, PROMPTS[n](it), SEARCH.get(n, 0)) for n in ("market", "customer", "competition", "finance", "regulation", "usability", "consistency", "kit")]
        for f in futs: f.result()
    one("critic", PROMPTS["critic"](it, summarise(agents)), 0)
    return agents, sources, errors


def line(name, a, nsrc):
    src = f" ({nsrc} web sources)" if nsrc else ""
    if name == "orch": return f"Rewrote the idea neutrally and listed {len(a.get('key_assumptions', []))} key assumptions."
    if name == "market": return f"Category spend about AED {a.get('tam_aed') or 0:,.0f} a year; growth {a.get('growth_pct_per_year') or 0:.0f}% a year{src}."
    if name == "customer": return f"Found {len(a.get('pains', []))} pains and {len(a.get('evidence', []))} customer quotes{src}."
    if name == "competition": return f"Found {len(a.get('competitors', []))} competitors{src}."
    if name == "finance": return f"Estimated {len(a.get('fields', {}))} cost and revenue ranges{src}."
    if name == "regulation": return f"Licence: {a.get('licence_type') or 'not identified'}; {len(a.get('hard_blockers', []))} hard blockers{src}."
    if name == "usability": return f"{a.get('steps_to_first_value')} steps to first value; {len(a.get('issues', []))} issues."
    if name == "consistency": return f"Second, independent estimate of {len(a.get('fields', {}))} cost ranges for the self-consistency check."
    if name == "kit": return "Wrote a landing page, two ads, an interview script and survey questions."
    if name == "critic": return f"Pre-mortem: “{(a.get('pre_mortem') or ['–'])[0]}”"
    return ""
