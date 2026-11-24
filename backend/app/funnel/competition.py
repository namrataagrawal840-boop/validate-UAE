"""Competitive analysis: who already does this, how close they are, and where the gap is.

Competitors come from three places, in this order of trust:
  1. "yours"  - competitors the founder typed in (known first-hand)
  2. "ai"     - real businesses the competition agent found in web search results (with URLs)
  3. "typical"- generic competitor types for the business category, used only when 1 and 2 are empty

Algorithms
  - Similarity: TF-IDF cosine similarity between the idea and each competitor's description.
  - Threat score: type weight x (0.5 similarity + 0.3 price closeness + 0.2 strength), 0-100.
  - Price benchmark: where your price sits among competitor prices (percentile).
  - Feature matrix: key buying criteria x competitors; white space = criteria few rivals cover.
  - Crowding: named competitors raise rivalry (1-5) and lower differentiation, which feed the
    choice model and how often the simulated competitor reacts.
"""
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

TYPE_W = {"direct": 1.0, "indirect": 0.6, "substitute": 0.35}

# Key buying criteria per category (what customers compare on)
CRITERIA = {
    "cafe": ["Specialty coffee or signature menu", "Healthy or dietary options", "Delivery available", "Work-friendly space", "Loyalty programme", "Late opening hours"],
    "kitchen": ["Healthy or high-protein meals", "Own ordering app", "Meal subscriptions", "Corporate or office delivery", "Calorie and macro info", "Fast delivery under 30 minutes"],
    "retail": ["Exclusive or local brands", "Online ordering", "Same-day delivery", "Personal styling or advice", "Loyalty programme", "Mall location"],
    "ecommerce": ["Same-day delivery in UAE", "Cash on delivery", "Free returns", "Arabic and English site", "Exclusive products", "Subscriptions"],
    "app": ["Arabic language support", "Free plan or trial", "Local payment methods", "Integrations", "Human support", "Mobile app"],
    "services": ["Online booking", "Same-day service", "Fixed transparent prices", "Vetted and insured staff", "Subscription plans", "WhatsApp support"],
    "education": ["Live online lessons", "Qualified certified tutors", "Progress reports for parents", "Arabic curriculum", "Flexible scheduling", "Small groups"],
    "fitness": ["Women-only sessions", "Small group classes", "Childcare", "Flexible class packs", "Personal training", "Online classes"],
}

# Generic competitor types (NOT named businesses): price factor vs category price, which criteria they usually cover
ARCHETYPES = {
    "cafe": [("Large international coffee chains", "direct", 1.0, 4.2, "Many branches, consistent menu, strong brand and app loyalty.", [0, 2, 4, 5]),
             ("Independent specialty cafés", "direct", 1.2, 4.4, "Specialty coffee, design-led spaces, strong on Instagram.", [0, 3]),
             ("Delivery-app restaurants", "indirect", 0.9, 4.0, "Huge choice on Talabat, Deliveroo, Careem and Noon Food.", [1, 2, 5]),
             ("Home coffee and office pantries", "substitute", 0.3, 3.5, "Capsule machines and free office coffee.", [])],
    "kitchen": [("Healthy meal-plan companies", "direct", 1.3, 4.1, "Weekly subscriptions with calorie-counted meals.", [0, 2, 4]),
                ("Virtual brands on delivery apps", "direct", 0.9, 3.9, "Many brands from one kitchen, promoted listings.", [5]),
                ("Restaurants and cafeterias near offices", "indirect", 0.8, 4.0, "Walk-in lunch, low prices, no wait for delivery.", [3, 5]),
                ("Home cooking and packed lunches", "substitute", 0.4, 3.5, "Cheapest option; costs time instead of money.", [0])],
    "retail": [("Mall chain stores", "direct", 1.0, 4.0, "Prime locations, wide ranges, loyalty points.", [1, 4, 5]),
               ("Marketplaces (Amazon.ae, Noon)", "indirect", 0.8, 4.2, "Huge range, fast delivery, low prices.", [1, 2]),
               ("Independent boutiques", "direct", 1.2, 4.3, "Curated local brands and personal service.", [0, 3]),
               ("Buying abroad while travelling", "substitute", 0.8, 3.5, "Common for higher-value purchases.", [0])],
    "ecommerce": [("Marketplaces (Amazon.ae, Noon)", "direct", 0.85, 4.2, "Fast delivery, cash on delivery, easy returns.", [0, 1, 2, 3]),
                  ("Brand-owned online stores", "direct", 1.1, 4.0, "Own sites with exclusive ranges.", [3, 4]),
                  ("Instagram and WhatsApp sellers", "indirect", 0.8, 3.6, "Informal, personal, often cash on delivery.", [1, 4]),
                  ("Physical shops and malls", "substitute", 1.0, 4.0, "Try before you buy, instant.", [])],
    "app": [("Global software leaders", "direct", 1.2, 4.4, "Feature-rich, well funded, mostly English-first.", [1, 3, 5]),
            ("Regional startups", "direct", 0.9, 4.0, "Arabic support and local payments.", [0, 2, 4, 5]),
            ("Spreadsheets and WhatsApp", "substitute", 0.1, 3.4, "Free and familiar; the real competitor for many small firms.", [1]),
            ("Agencies doing it by hand", "indirect", 3.0, 4.0, "Done-for-you service at a higher price.", [4])],
    "services": [("Booking platforms (e.g. Justlife-type apps)", "direct", 1.0, 4.2, "Online booking, vetted staff, many services.", [0, 1, 2, 3]),
                 ("Established local companies", "direct", 1.1, 4.0, "Reputation, contracts with buildings.", [2, 3, 4]),
                 ("Freelancers via WhatsApp groups", "indirect", 0.6, 3.5, "Cheap and flexible, quality varies.", [1, 5]),
                 ("Live-in help or do-it-yourself", "substitute", 0.7, 3.6, "Many households already have help at home.", [])],
    "education": [("Large tutoring centres", "direct", 1.2, 4.1, "Physical centres, structured programmes.", [1, 3, 5]),
                  ("Online tutoring marketplaces", "direct", 0.9, 4.2, "Big tutor choice, flexible times.", [0, 1, 4]),
                  ("Freelance private tutors", "direct", 1.0, 4.4, "Home visits, personal relationships.", [1, 3, 4]),
                  ("School support and free apps", "substitute", 0.1, 3.5, "School classes, YouTube and free apps.", [0, 4])],
    "fitness": [("Big-box gym chains", "indirect", 0.8, 3.9, "Low monthly fees, many locations, equipment-heavy.", [3, 4]),
                ("Boutique studios", "direct", 1.3, 4.5, "Small classes, strong community.", [1, 3, 4]),
                ("Personal trainers", "direct", 2.0, 4.5, "One-to-one, comes to you.", [4]),
                ("Home workouts and fitness apps", "substitute", 0.15, 3.8, "Cheap, flexible, no travel.", [5])],
}

_tok = lambda s: set(w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in {"and", "the", "for", "with", "from", "under", "per", "you", "your"})


def _mentions(text, criterion):
    """A criterion counts as mentioned if at least half its meaningful words appear in the text (prefix match)."""
    t = _tok(text); c = _tok(criterion)
    if not c: return False
    hit = sum(any(w.startswith(x[:5]) or x.startswith(w[:5]) for w in t) for x in c)
    return hit / len(c) >= .5


def gather(state, business_type, category_price):
    """Return (competitors, source) with a common shape."""
    mine = [dict(c, source="yours") for c in state.get("competitors") or []]
    ai = [dict(c, source="ai") for c in ((state.get("agents") or {}).get("competition") or {}).get("competitors") or []]
    if mine or ai:
        return mine + ai, "yours+ai" if mine and ai else "yours" if mine else "ai"
    crit = CRITERIA[business_type]
    arch = [dict(name=n, type=t, price_aed=round(category_price * f), rating=r, note=d, features=[crit[i] for i in fi], url="", source="typical")
            for n, t, f, r, d, fi in ARCHETYPES[business_type]]
    return arch, "typical"


def analyse(state, business_type, idea_text, your_price, category_price, ai_forces=None, ai_diff=None, your_features=None):
    comps, source = gather(state, business_type, category_price)
    crit = list(CRITERIA[business_type])
    for c in comps:  # AI may add criteria it found
        for f in c.get("features") or []:
            if f and not any(_mentions(f, k) and _mentions(k, f) for k in crit) and len(crit) < 9: crit.append(f)
    docs = [f"{c.get('name', '')}. {c.get('note', '')} {' '.join(c.get('features') or [])} {c.get('offering', '')}" for c in comps]

    # 1. Similarity (TF-IDF cosine)
    sims = np.zeros(len(comps))
    if comps:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        X = vec.fit_transform([idea_text] + docs)
        Xn = X.multiply(1 / np.sqrt(X.multiply(X).sum(1) + 1e-12)).tocsr()
        sims = np.asarray((Xn[1:] @ Xn[0].T).todense()).ravel()
    sim_n = np.clip(sims / .35, 0, 1)  # short texts rarely exceed .35 cosine; rescale to 0-1

    # 2. Feature matrix
    yours = set(your_features or [k for k in crit if _mentions(idea_text, k)])
    matrix = []
    for c in comps:
        have = set()
        for k in crit:
            if any(_mentions(f, k) or _mentions(k, f) for f in c.get("features") or []) or _mentions(c.get("note", ""), k): have.add(k)
        matrix.append(have)

    rows = []
    for i, c in enumerate(comps):
        p = c.get("price_aed")
        price_close = float(np.exp(-abs(np.log(p / your_price)) / .5)) if p and your_price else .5
        strength = float(np.clip((c.get("rating") or 3.8) / 5, 0, 1))
        overlap = len(matrix[i] & yours) / max(len(yours), 1) if yours else .5
        sim = float(.7 * sim_n[i] + .3 * overlap)
        threat = 100 * TYPE_W.get(c.get("type"), .6) * (.5 * sim + .3 * price_close + .2 * strength)
        rows.append(dict(name=c.get("name"), type=c.get("type", "direct"), source=c.get("source"), price_aed=p, price_text=c.get("price_point") or "",
                         rating=c.get("rating"), note=c.get("note", ""), strengths=c.get("strengths") or [], weaknesses=c.get("weaknesses") or [],
                         url=c.get("url") or "", location=c.get("location") or "", similarity=sim, price_closeness=price_close, threat=float(threat),
                         features=sorted(matrix[i])))
    rows.sort(key=lambda r: -r["threat"])

    # 3. Price benchmark
    prices = [r["price_aed"] for r in rows if r["price_aed"] and r["type"] != "substitute"]
    bench = None
    if prices:
        bench = dict(n=len(prices), low=float(min(prices)), median=float(np.median(prices)), high=float(max(prices)),
                     percentile=float(np.mean([p < your_price for p in prices]) + .5 * np.mean([p == your_price for p in prices])), yours=your_price)
        bench["position"] = "premium" if bench["percentile"] >= .75 else "budget" if bench["percentile"] <= .25 else "mid-market"

    # 4. White space and table stakes
    cov = {k: sum(k in m for m in matrix) for k in crit}
    n = max(len(comps), 1)
    white = [k for k in crit if k in yours and cov[k] / n <= .34]
    stakes = [k for k in crit if k not in yours and cov[k] / n >= .5]

    # 5. Crowding -> rivalry and differentiation (only from named competitors, not generic types)
    named = [r for r in rows if r["source"] in ("yours", "ai")]
    der_rivalry = der_diff = None
    if named:
        load = sum(r["threat"] / 100 for r in named)
        der_rivalry = float(1 + 4 * (1 - np.exp(-load / 1.2)))
        direct = [r["similarity"] for r in named if r["type"] == "direct"] or [max(r["similarity"] for r in named) * .6]
        der_diff = float(np.clip(100 * (1 - max(direct)) + 10 * len(white), 10, 90))
    forces = dict(ai_forces or {})
    if der_rivalry is not None:
        forces["rivalry"] = round((forces["rivalry"] + der_rivalry) / 2, 2) if "rivalry" in forces else round(der_rivalry, 2)
    diff = ai_diff if ai_diff is not None else der_diff
    if ai_diff is not None and der_diff is not None: diff = (ai_diff + der_diff) / 2

    top = rows[0] if rows else None
    if not rows: headline = "No competitors listed yet."
    elif source == "typical": headline = f"No named competitors yet. Typical rivals for this kind of business are shown; add the ones you know or run with AI to find real ones."
    else:
        hi = [r for r in named if r["threat"] >= 55]
        headline = (f"{len(named)} named competitor{'s' if len(named) != 1 else ''}; {len(hi)} look{'s' if len(hi) == 1 else ''} like a strong threat. "
                    f"Closest: {top['name']} ({round(top['similarity'] * 100)}% similar).")
    return dict(source=source, competitors=rows, criteria=crit, yours=sorted(yours), coverage=cov, white_space=white, table_stakes=stakes,
                price=bench, forces=forces, differentiation=diff, derived_rivalry=der_rivalry, derived_differentiation=der_diff, headline=headline,
                gaps=((state.get("agents") or {}).get("competition") or {}).get("gaps") or [], moats=((state.get("agents") or {}).get("competition") or {}).get("moats") or [])
