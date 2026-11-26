"""Simulated customer panel: personas, feedback, a survey, a focus-group debate and the answers they add up to.

Inspired by multi-agent "swarm" simulators such as MiroFish, but written from scratch for ValidateUAE.

Personas are real rows of the blinded synthetic UAE market (age, emirate, income, category spend, pain,
online habits, price sensitivity), with the buying model's probability and willingness to pay for each one.
Without an API key their reactions follow those numbers through transparent rules, and the text comes from
templates. With an API key Claude writes each persona's opinions and debate turns, given the same facts;
that adds a second, independent judgement.

Debate: opinions (stated purchase intent, 0-1) move by the Friedkin-Johnsen model,
    x(t+1) = s * W x(t) + (1 - s) * x(0)
where W weighs other panellists by similarity and conviction, and s is each person's openness.

Everything here is simulated. It is never evidence of what real customers do: ledger records it creates are
of type "synthetic" and carry zero weight.
"""
import datetime as dt
import json
import re

import numpy as np

from . import priors as P
from .synth import market
from .funnel import market_stages as MS
from .funnel import checks as C
from .funnel import validation as V

# Rule of thumb for stated vs actual buying (hypothetical bias): of those who say "yes", fewer actually buy.
STATED_TO_ACTUAL = {"yes": .45, "maybe": .12, "no": .01}

NAMES = {  # illustrative mix of first names common among UAE residents; nationality is not modelled
    "f": ["Aisha", "Fatima", "Mariam", "Noura", "Priya", "Anjali", "Sana", "Ayesha", "Maria", "Joy", "Hala", "Rana", "Layla", "Sarah", "Emma",
          "Deepa", "Hira", "Grace", "Reem", "Lina", "Meera", "Zainab", "Nadia", "Chloe", "Shamma"],
    "m": ["Ahmed", "Mohammed", "Khalid", "Omar", "Rahul", "Arjun", "Imran", "Bilal", "Jose", "Mark", "Karim", "Tarek", "Yousef", "James",
          "Vikram", "Faisal", "Hamza", "Rohan", "Saeed", "Ali", "Daniel", "Hassan", "Rashid", "Kiran", "Sultan"],
}
SURNAME_INITIAL = list("ABCDEFGHIJKLMNOPRSTVYZ")
NOUN = {"cafe": "café", "kitchen": "meal service", "retail": "shop", "ecommerce": "online store", "app": "app", "services": "service",
        "education": "tutoring", "fitness": "studio"}
JOBS = {0: ["retail assistant", "driver", "cashier", "delivery rider", "hospitality worker"], 1: ["teacher", "nurse", "accountant", "sales executive", "IT support engineer"],
        2: ["engineer", "marketing manager", "doctor", "project manager", "architect"], 3: ["business owner", "senior director", "investor", "consultant partner", "surgeon"]}

OBJECTIONS = {
    "price": ("Too expensive for me", "At AED {price:,.0f} a month it's more than I'd pay; I'd think about it at around AED {wtp:,.0f}."),
    "no_pain": ("I don't really have this problem", "Honestly, what I do now works fine for me, so I'm not looking for a new {noun}."),
    "trust": ("Not sure I can trust a new brand", "It's new and I don't know anyone who has used it. I'd want reviews or a free trial first."),
    "switching": ("Happy with what I use today", "I'm used to my current option and switching feels like effort for a small gain."),
    "convenience": ("Doesn't fit how I buy", "I prefer to do this {channel}, so it would have to be really easy for me."),
    "competitor": ("Something similar already exists", "I already know {competitor}; I'd need a clear reason to choose you instead."),
    "time": ("I don't have time for it", "With work and family, I'm not sure when I'd actually use it."),
}
FIXES = {"price": "Test a lower entry price, a smaller pack or a first-month discount, and show the value in AED.",
         "no_pain": "Narrow the launch to the segment with the strongest problem; drop the rest from early marketing.",
         "trust": "Offer a free trial or money-back guarantee and collect testimonials from the first users.",
         "switching": "Make switching effortless: import, onboarding help, or a bonus for the first month.",
         "convenience": "Match how customers like to buy (delivery, WhatsApp ordering, location or hours).",
         "competitor": "Lead with what competitors don't offer; see the white space on the Competition page.",
         "time": "Cut the time it takes: shorter sessions, flexible slots, or a done-for-you option."}
BENEFITS = {"pain": "It solves something that genuinely bothers me", "value": "It looks like good value for the price", "fit": "It fits the way I like to buy",
            "new": "It sounds different from what's out there"}
SAY_OBJ = {  # first-person variants, picked at random so panellists don't sound identical
    "price": ["At AED {price:,.0f} a month it's more than I'd pay; around AED {wtp:,.0f} would feel right.", "The price puts me off. I spend about AED {spend:,.0f} a month on this now.",
              "For me it would need to be closer to AED {wtp:,.0f} a month."],
    "no_pain": ["Honestly, what I do now works fine, so I'm not looking for a new {noun}.", "I don't really feel this problem day to day.",
                "It's a nice idea, but it isn't something I'd go looking for."],
    "trust": ["It's new and I don't know anyone who has used it. I'd want reviews or a free trial first.", "I'd wait until a friend tried it.",
              "New places sometimes don't last. I'd need to see it's reliable."],
    "switching": ["I'm used to my current option and switching feels like effort.", "What I have now is good enough; changing is a hassle.",
                  "I'd only move if it were clearly better than what I use."],
    "convenience": ["I prefer to do this {channel}, so it would have to be really easy for me.", "Location and timing matter most to me; it has to fit my routine.",
                    "If it's not convenient, I won't keep using it."],
    "competitor": ["I already know {competitor}; I'd need a clear reason to choose you instead.", "There are already places like this. What makes it different?",
                   "{competitor} does something similar, so I'd compare carefully."],
    "time": ["With work and family, I'm not sure when I'd actually use it.", "My weeks are packed; I'd sign up and then not go.", "Time is my real problem, not money."],
}
SAY_LIKE = {"pain": ["This is something that genuinely bothers me.", "I've wanted something like this for a while.", "It solves a real headache for me."],
            "value": ["It looks like good value.", "For what you get, the price seems fair.", "It's worth the money if it works as described."],
            "fit": ["It fits the way I like to do things.", "It would be easy to make it part of my week.", "The format suits me."],
            "new": ["It sounds different from what's out there.", "I like that it's a fresh take.", "Nobody near me offers quite this."]}
SAY_FIX = {"price": ["A cheaper starter option or a first-month discount would get me to try it.", "Show me a smaller package and I'd consider it."],
           "no_pain": ["Show me how it saves time or money compared with what I do now.", "Maybe if I saw friends really benefiting from it."],
           "trust": ["A free trial or a money-back guarantee would do it for me.", "Real reviews from people like me would help a lot."],
           "switching": ["Make switching effortless and give me a reason to move.", "If the first month were free, I'd give it a go."],
           "convenience": ["Make it easy to fit around my day, with flexible times or delivery.", "If it were closer or bookable on WhatsApp, I'd try it."],
           "competitor": ["Tell me clearly what you do that others don't.", "If it had something the others lack, I'd switch."],
           "time": ["Shorter, flexible sessions would make it work for me.", "If it saved me time instead of taking it, I'm in."]}
SAY_AGREE = {"price": "the price is a real issue", "no_pain": "I'm not sure the need is big enough", "trust": "I'd want proof it's reliable first",
             "switching": "switching is a hassle", "convenience": "it has to be convenient", "competitor": "there are alternatives already", "time": "time is a real constraint"}


def audience(it):
    """Who the idea is for, read from the idea and target customer: used to pick panellists' gender."""
    t = f"{it.get('idea', '')} {it.get('target_customer', '')}".lower()
    if re.search(r"\b(women|woman|female|ladies|mothers|mums|moms|girls)\b", t) and not re.search(r"\b(men|male|fathers|boys)\b", t.replace("women", "")):
        return "f"
    if re.search(r"\b(men|male|gentlemen|fathers|dads|boys)\b", t.replace("women", "")):
        return "m"
    return None


def _people(m, it, n, seed):
    f = MS.focus_mask(m, it.get("emirate")) & m["participates"]
    idx = np.where(f)[0]
    rng = np.random.default_rng([seed, 99])
    return rng.choice(idx, min(n, len(idx)), replace=False), rng


def build(result, n=40, seed=2027, social=None):
    """Create n personas from the synthetic market with their reactions to the idea.
    With a social-listening summary, objections follow what real people post, mood follows real sentiment,
    and each persona links to a real example post (grounding)."""
    it = result["intake"]; bt = it["business_type"]
    m = market(int(result["settings"].get("seed", 2027)), bt)
    price = float(result["assumptions"]["price"]["likely"])
    p_all = MS.adoption(m, it, price, result["comp_position"], result["choice_model"])
    w_all = MS.wtp(m)
    pick, rng = _people(m, it, n, seed)
    seg = MS.segment(m, it, int(result["settings"].get("seed", 2027)))
    seg_names = {s["id"]: s["name"] for s in result["stages"]["segment"]["segments"]}
    labels = np.asarray(seg["labels"]); fidx = np.where(MS.focus_mask(m, it.get("emirate")) & m["participates"])[0]
    comp = (result.get("competition") or {}).get("competitors") or []
    top_comp = next((c["name"] for c in comp if c.get("source") != "typical"), comp[0]["name"] if comp else "the usual options")
    online = P.TYPES[bt]["digital"] > .55 or it.get("setup") == "Online only"
    people = []
    used = set()
    only = audience(it)
    real_obj = (social or {}).get("objections") or {}
    mood = float((social or {}).get("sentiment") or 0)
    lift = float(np.clip(.8 + .4 * ((social or {}).get("positive", 0) - (social or {}).get("negative", 0)) + (social or {}).get("demand", 0), .6, 1.4)) if social else 1.0
    for j, i in enumerate(pick):
        g = only or ("f" if rng.random() < .5 else "m")
        name = rng.choice(NAMES[g])
        tries = 0
        while name in used and tries < 30: name = rng.choice(NAMES[g]); tries += 1
        used.add(name)
        age = int(m["age"][i]); inc_b = int(m["income_band"][i])
        house = "single" if age < 27 and rng.random() < .7 else ("married with children" if age >= 32 and rng.random() < .65 else "married, no children" if rng.random() < .5 else "single")
        p = float(p_all[i]); wtp = float(w_all[i]); pain = float(m["pain"][i]); dig = float(m["digital"][i])
        # stated intent overstates real buying; drawn so that the discounted rate matches the model
        # chosen so that yes x 0.45 + maybe x 0.12 = the model's probability on average
        y = float(np.clip(1.5 * p * lift, 0, .9)); mb = float(np.clip(2.7 * p * lift, 0, 1 - y))
        r = rng.random(); intent = "yes" if r < y else "maybe" if r < y + mb else "no"
        ratio = wtp / price
        reasons = {"price": max(0, 1.3 - ratio) * 2, "no_pain": max(0, .45 - pain) * 3, "trust": .35 + .2 * rng.random(),
                   "switching": .25 + .3 * (1 - pain) * rng.random(), "convenience": abs(dig - (.9 if online else .4)) * 1.2,
                   "competitor": .3 * float((result.get("competition") or {}).get("rivalry", 3) / 3) * rng.random(), "time": (.25 if "children" in house else .1) * rng.random()}
        if real_obj: reasons = {k: v * (1 + 4 * real_obj.get(k, 0)) for k, v in reasons.items()}  # what real people actually complain about
        obj = max(reasons, key=reasons.get)
        likes = {"pain": pain, "value": min(1, ratio / 1.5), "fit": 1 - reasons["convenience"], "new": .4 + .2 * rng.random()}
        like = max(likes, key=likes.get)
        rating = int(np.clip(round(4 + 6 * (pain - .4) + 3 * np.log(max(ratio, .05)) + (2 if intent == "yes" else 0) + 3 * mood + rng.normal(0, 1.2)), 0, 10))
        ex = ((social or {}).get("examples") or {}).get(f"obj_{obj}") or []
        echo = dict(ex[int(rng.integers(len(ex)))], share=real_obj.get(obj, 0)) if ex else None
        noise = np.exp(rng.normal(0, .12, 4))
        vw = sorted([wtp * .45 * noise[0], wtp * .7 * noise[1], wtp * 1.05 * noise[2], wtp * 1.45 * noise[3]])
        o_title = OBJECTIONS[obj][0]
        text = str(rng.choice(SAY_OBJ[obj])).format(price=price, wtp=wtp, spend=float(m["cat_spend"][i]), noun=NOUN[bt], channel="online" if dig > .6 else "in person", competitor=top_comp)
        liked = str(rng.choice(SAY_LIKE[like]))
        people.append(dict(
            id=f"p{j}", name=f"{name} {SURNAME_INITIAL[rng.integers(len(SURNAME_INITIAL))]}.", gender=g, age=age,
            emirate=P.EMIRATES[int(m["emirate"][i])][0], income_band=P.INCOME_BANDS[inc_b][0], income=float(m["income"][i]),
            job=str(rng.choice(JOBS[inc_b])), household=house, habits="mostly online" if dig > .6 else "mostly in person" if dig < .4 else "online and in person",
            segment=seg_names.get(int(labels[i]), "Other buyers"), pain=pain, wtp=wtp, p_buy=p, spend_today=float(m["cat_spend"][i]),
            openness=float(np.clip(rng.beta(3, 3), .1, .9)), intent=intent, rating=rating, objection=obj, objection_title=o_title, like=like,
            quote=(liked + " " + text) if intent != "no" else text,
            change_mind=str(rng.choice(SAY_FIX[obj])), echo=echo, van_westendorp=[round(x) for x in vw], price_view="Good value" if ratio > 1.2 else "About right" if ratio > .9 else "Too expensive",
            source="model"))
    return dict(created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), n=len(people), price=price, people=people, mode="model",
                grounded=dict(posts=social["n"], platforms=social["platforms"], sentiment=mood) if social else None,
                model_rate=float(p_all[fidx].mean()) if len(fidx) else 0.0, debate=None)


# ---------------- focus group debate ----------------
INTENT_X = {"yes": .8, "maybe": .45, "no": .1}


def _phrase_open(p, noun):
    if p["intent"] == "yes": return f"I'd try it. {p['quote']}"
    if p["intent"] == "maybe": return f"I'm on the fence. {p['quote']}"
    return f"Probably not for me. {p['quote']}"


def debate(panel, result, size=6, rounds=3, seed=2027):
    """Pick a mixed group and let opinions move by the Friedkin-Johnsen model. Returns the transcript and the shift."""
    people = panel["people"]; rng = np.random.default_rng([seed, 7])
    groups = {k: [p for p in people if p["intent"] == k] for k in ("yes", "maybe", "no")}
    chosen = []
    for k, want in (("yes", 2), ("maybe", 2), ("no", 2)):
        chosen += groups[k][:want]
    for p in people:
        if len(chosen) >= size: break
        if p not in chosen: chosen.append(p)
    chosen = chosen[:size]
    n = len(chosen)
    if n < 2: return None
    noun = NOUN[result["intake"]["business_type"]]; price = panel["price"]
    x0 = np.array([INTENT_X[p["intent"]] * (.8 + .4 * p["pain"]) for p in chosen]).clip(0, 1); x = x0.copy()
    s = np.array([p["openness"] for p in chosen])
    feat = np.array([[p["age"] / 60, np.log(max(p["income"], 1000)) / 12, p["pain"], np.log(max(p["wtp"], 1) / price)] for p in chosen])
    d = np.linalg.norm(feat[:, None, :] - feat[None, :, :], axis=2)
    conv = np.abs(x0 - .5) * 2 + .2  # conviction: strong views carry more weight
    W = np.exp(-d * 2) * conv[None, :]; np.fill_diagonal(W, 0); W = W / W.sum(1, keepdims=True)
    lines = [dict(who="Moderator", text=f"Thanks for joining. Here's the idea: {result['idea']['brief'][:220]} It would cost about AED {price:,.0f} a month. First reactions?")]
    for i, p in enumerate(chosen): lines.append(dict(who=p["name"], pid=p["id"], text=_phrase_open(p, noun), intent=float(x[i])))
    hist = [x.copy()]
    obj_counts = {}
    for p in chosen: obj_counts[p["objection"]] = obj_counts.get(p["objection"], 0) + 1
    top_obj = max(obj_counts, key=obj_counts.get)
    for r in range(rounds):
        x_new = s * (W @ x) + (1 - s) * x0
        if r == 0:
            lines.append(dict(who="Moderator", text="Some of you are keen and some aren't. What would you say to each other?"))
            for i, p in enumerate(chosen):
                j = int(np.argmax(W[i] * np.abs(x - x[i])))  # the most influential person who disagrees
                q = chosen[j]; moved = x_new[i] - x[i]
                first = q["name"].split()[0]
                if abs(moved) < .03:
                    t = (f"I hear {first}, but for me {SAY_AGREE[p['objection']]}." if x[i] < .5 else f"I hear {first}, but I still like it. {str(rng.choice(SAY_LIKE[p['like']]))}")
                elif moved > 0:
                    t = str(rng.choice([f"{first} makes a fair point. If it really works like that, I could see myself trying it.", f"Hearing {first}, I'm warming to it.",
                                        f"I hadn't thought of it the way {first} puts it. Maybe I'd try it.", f"{first} is convincing. {str(rng.choice(SAY_LIKE[q['like']]))}"]))
                else:
                    t = str(rng.choice([f"{first} has a point: {SAY_AGREE[q['objection']]}. I'm less sure now.", f"That's true, {first}: {SAY_AGREE[q['objection']]}.",
                                        f"{first} is right that {SAY_AGREE[q['objection']]}; that makes me hesitate."]))
                lines.append(dict(who=p["name"], pid=p["id"], text=t, intent=float(x_new[i])))
        elif r == 1:
            lines.append(dict(who="Moderator", text=f"The concern I'm hearing most is: “{OBJECTIONS[top_obj][0]}”. What would change your mind?"))
            for i, p in enumerate(chosen):
                if x_new[i] > .6: t = "I'm already in. " + ("A trial would get my friends to try it too." if p["objection"] == "trust" else "Get the basics right and I'd tell people about it.")
                else: t = p["change_mind"]
                lines.append(dict(who=p["name"], pid=p["id"], text=t, intent=float(x_new[i])))
        x = x_new; hist.append(x.copy())
    lines.append(dict(who="Moderator", text="Final question: if this launched next month, would you buy it?"))
    final = []
    for i, p in enumerate(chosen):
        v = "yes" if x[i] >= .6 else "maybe" if x[i] >= .3 else "no"
        final.append(v)
        say = {"yes": ["Yes, I'd sign up.", "Yes, I'd give it a go.", "Count me in."], "maybe": ["Maybe, if the concerns are fixed.", "Possibly, after a trial.", "Maybe; it depends on the details."],
               "no": ["No, not as it is.", "Not for me, sorry.", "No, I'd stick with what I have."]}[v]
        lines.append(dict(who=p["name"], pid=p["id"], text=str(rng.choice(say)), intent=float(x[i])))
    infl = (W * np.abs(x0[None, :] - x0[:, None])).sum(0)
    lead = chosen[int(np.argmax(infl))]
    return dict(members=[p["id"] for p in chosen], lines=lines, history=[h.round(3).tolist() for h in hist], start=float(x0.mean()), end=float(x.mean()),
                final_votes={k: final.count(k) for k in ("yes", "maybe", "no")}, top_concern=top_obj, top_concern_title=OBJECTIONS[top_obj][0],
                most_influential=lead["name"], influential_view=lead["intent"], mode="model")


# ---------------- the answers ----------------
def synthesise(panel, result):
    people = panel["people"]; n = len(people) or 1; price = panel["price"]
    counts = {k: sum(p["intent"] == k for p in people) for k in ("yes", "maybe", "no")}
    adj = sum(STATED_TO_ACTUAL[p["intent"]] for p in people) / n
    seg = {}
    for p in people:
        s = seg.setdefault(p["segment"], dict(n=0, yes=0, rating=0.0)); s["n"] += 1; s["yes"] += p["intent"] == "yes"; s["rating"] += p["rating"]
    seg_rows = sorted([dict(segment=k, n=v["n"], yes_share=v["yes"] / v["n"], avg_rating=v["rating"] / v["n"]) for k, v in seg.items()], key=lambda r: -r["yes_share"])
    objs = {}
    for p in people:
        if p["intent"] != "yes": objs[p["objection"]] = objs.get(p["objection"], 0) + 1
    obj_rows = sorted([dict(key=k, title=OBJECTIONS[k][0], share=v / n, fix=FIXES[k]) for k, v in objs.items()], key=lambda r: -r["share"])
    likes = {}
    for p in people:
        if p["intent"] != "no": likes[p["like"]] = likes.get(p["like"], 0) + 1
    like_rows = sorted([dict(title=BENEFITS[k], share=v / n) for k, v in likes.items()], key=lambda r: -r["share"])
    pro = sum(p["rating"] >= 9 for p in people); pas = sum(7 <= p["rating"] <= 8 for p in people); det = n - pro - pas
    nps = V.nps(pro, pas, det)
    vw = V.van_westendorp([p["van_westendorp"] for p in people]) if len(people) >= 5 else None
    acc = sum(p["wtp"] >= price for p in people) / n
    deb = panel.get("debate")
    verdict = ("Strong interest" if adj >= .15 else "Some interest" if adj >= .06 else "Little interest")
    headline = (f"{counts['yes']} of {n} simulated customers say they would buy and {counts['maybe']} might. Allowing for the usual gap between saying and doing, "
                f"about {adj:.1%} would actually buy once they know about it (the buying model expects {panel['model_rate']:.1%}).")
    questions = []
    for o in obj_rows[:3]:
        questions.append({"price": f"What do you pay today for this, and what would make AED {price:,.0f} a month feel worth it?",
                          "no_pain": "When did this problem last cost you time or money? What did you do about it?",
                          "trust": "What would you need to see before trying a new provider for this?",
                          "switching": "What would make you switch from what you use today?",
                          "convenience": "Walk me through how you'd prefer to buy and use this.",
                          "competitor": "What do you like and dislike about the option you use now?",
                          "time": "When in your week would you realistically use this?"}[o["key"]])
    return dict(verdict=verdict, headline=headline, counts=counts, actual_rate=adj, model_rate=panel["model_rate"], segments=seg_rows, objections=obj_rows,
                likes=like_rows, nps=nps, van_westendorp=vw, acceptance=acc, avg_rating=sum(p["rating"] for p in people) / n,
                debate=None if not deb else dict(start=deb["start"], end=deb["end"], votes=deb["final_votes"], concern=deb["top_concern_title"], influential=deb["most_influential"]),
                changes=[o["fix"] for o in obj_rows[:3]], questions=questions,
                caveat="Simulated customers. Use this to find questions and risks, not as proof. It carries zero weight in evidence confidence.")


# ---------------- optional: Claude writes the voices ----------------
AI_RULES = ("You are role-playing realistic UAE residents for a business-idea test. Stay in character, be honest and specific, include doubts, "
            "and do not be more positive than a real person would be. Reply with JSON only.")


def _ai(prompt, max_tokens=4000):
    from anthropic import Anthropic
    from .agents import MODEL, parse_json
    r = Anthropic().messages.create(model=MODEL, max_tokens=max_tokens, system=AI_RULES, messages=[{"role": "user", "content": prompt}])
    return parse_json("".join(b.text for b in r.content if b.type == "text"))


def _persona_card(p):
    return (f"{p['name']}, {p['age']}, {p['job']}, {p['household']}, lives in {p['emirate']}, {p['income_band'].lower()} income "
            f"(about AED {p['income']:,.0f}/month), buys {p['habits']}, spends about AED {p['spend_today']:,.0f}/month on this kind of thing today, "
            f"problem severity {p['pain']:.0%}, would pay up to about AED {p['wtp']:,.0f}/month")


def ai_voices(panel, result, batch=8, limit=24):
    """Ask Claude for each persona's own judgement. Numbers it returns replace the rule-based ones for that persona."""
    it = result["intake"]; price = panel["price"]
    idea = result["idea"]["brief"]
    for k in range(0, min(len(panel["people"]), limit), batch):
        grp = panel["people"][k:k + batch]
        prompt = (f"Business idea in the UAE: {idea}\nPrice: AED {price:,.0f} a month. Setup: {it.get('setup')}. Area: {it.get('emirate')}.\n\n"
                  "For each person below, give their honest reaction.\n" + "\n".join(f"{p['id']}: {_persona_card(p)}" for p in grp) +
                  '\n\nJSON: {"people": [{"id": "", "intent": "yes|maybe|no", "rating": 0, "max_price_aed": 0, "objection": "price|no_pain|trust|switching|convenience|competitor|time", '
                  '"quote": "1-2 sentences in their voice", "change_mind": "what would change their mind"}]}')
        try:
            out = {x.get("id"): x for x in (_ai(prompt).get("people") or [])}
        except Exception:
            continue
        for p in grp:
            x = out.get(p["id"])
            if not x: continue
            if x.get("intent") in ("yes", "maybe", "no"): p["intent"] = x["intent"]
            try: p["rating"] = int(np.clip(int(x.get("rating", p["rating"])), 0, 10))
            except (TypeError, ValueError): pass
            if x.get("objection") in OBJECTIONS: p["objection"] = x["objection"]; p["objection_title"] = OBJECTIONS[x["objection"]][0]
            if isinstance(x.get("quote"), str) and x["quote"].strip(): p["quote"] = x["quote"].strip()[:400]
            if isinstance(x.get("change_mind"), str) and x["change_mind"].strip(): p["change_mind"] = x["change_mind"].strip()[:300]
            try:
                mp = float(x.get("max_price_aed") or 0)
                if 0 < mp < 1e6: p["wtp"] = mp; p["price_view"] = "Good value" if mp > 1.2 * price else "About right" if mp > .9 * price else "Too expensive"
            except (TypeError, ValueError): pass
            p["source"] = "ai"
    panel["mode"] = "ai" if any(p["source"] == "ai" for p in panel["people"]) else panel["mode"]
    return panel


def ai_debate(panel, result, size=6):
    base = debate(panel, result, size=size)
    if not base: return None
    members = [p for p in panel["people"] if p["id"] in base["members"]]
    prompt = (f"Run a short focus group about this UAE business idea: {result['idea']['brief']} Price AED {panel['price']:,.0f}/month.\n"
              "Participants:\n" + "\n".join(f"{p['id']}: {_persona_card(p)}; starting view: {p['intent']}" for p in members) +
              "\nWrite 3 rounds: first reactions, replies to each other (agree or push back by name), what would change their mind; then each gives a final yes/maybe/no. "
              'JSON: {"lines": [{"who": "Moderator or a person id", "text": ""}], "final": {"<id>": "yes|maybe|no"}}')
    try:
        out = _ai(prompt, max_tokens=5000)
    except Exception:
        return base
    names = {p["id"]: p["name"] for p in members}
    lines = [dict(who=names.get(l.get("who"), "Moderator"), pid=l.get("who") if l.get("who") in names else None, text=str(l.get("text", ""))[:500])
             for l in out.get("lines") or [] if l.get("text")]
    final = {k: v for k, v in (out.get("final") or {}).items() if k in names and v in ("yes", "maybe", "no")}
    if len(lines) < 4 or not final: return base
    base.update(lines=lines, final_votes={k: list(final.values()).count(k) for k in ("yes", "maybe", "no")},
                end=float(np.mean([INTENT_X[v] for v in final.values()])), mode="ai")
    return base


def ask(persona, question, result, history=None):
    """Chat with one persona (needs an API key)."""
    convo = "\n".join(f"{'Founder' if h['role'] == 'user' else persona['name']}: {h['text']}" for h in (history or [])[-8:])
    prompt = (f"You are {_persona_card(persona)}. Your view of this idea: {persona['intent']}; main concern: {persona['objection_title']}.\n"
              f"Idea: {result['idea']['brief']} Price AED {result['assumptions']['price']['likely']:,.0f}/month.\n{convo}\nFounder: {question}\n"
              'Answer in character in 1-4 sentences. JSON: {"answer": ""}')
    return str(_ai(prompt, max_tokens=600).get("answer", "")).strip()[:1200]


# ---------------- simulated signals for the ledger and the lab (never evidence) ----------------
def signals(panel, result):
    """What the simulated panel suggests for each evidence area. Shown next to real evidence, never mixed into it."""
    ps = panel["people"]; n = len(ps) or 1; price = panel["price"]
    s = synthesise(panel, result)
    return {
        "market": dict(label="Would actually buy", value=s["actual_rate"], text=f"{s['actual_rate']:.1%} of simulated customers would likely buy"),
        "pain": dict(label="Serious problem", value=sum(p["pain"] >= .6 for p in ps) / n, text=f"{sum(p['pain'] >= .6 for p in ps) / n:.0%} say the problem is serious"),
        "price": dict(label="Accept the price", value=s["acceptance"], text=f"{s['acceptance']:.0%} would pay AED {price:,.0f} a month"),
        "competition": dict(label="Loyal to alternatives", value=sum(p["objection"] in ("competitor", "switching") for p in ps) / n,
                            text=f"{sum(p['objection'] in ('competitor', 'switching') for p in ps) / n:.0%} prefer what they use today"),
        "trust": dict(label="Want proof first", value=sum(p["objection"] == "trust" for p in ps) / n, text=f"{sum(p['objection'] == 'trust' for p in ps) / n:.0%} want reviews or a trial first"),
    }


def metric_value(metric, panel, result):
    """The simulated panel's answer to a lab hypothesis metric, or None where a panel can't say."""
    sig = signals(panel, result)
    return {"signup_rate": sig["market"]["value"], "price_acceptance": sig["price"]["value"], "pain_share": sig["pain"]["value"]}.get(metric)
