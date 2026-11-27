"""Simple mode: five pages that answer one question each, in plain words, with a link to the full detail.
Idea -> Market -> Customers -> Money -> Decision."""
import streamlit as st

from app import market_size as MZ
from app import panel as PN
from app import store
from app import lab as LB
from ui import decision
from ui.market import KIND as MKIND
from ui.common import ss, esc, aed, pct, num, kpi, section, soft, PASTEL, kind_pill, user_id, approx, rng, payback_line
from ui.glossary import gloss

PAGES = ["1. Idea", "2. Market", "3. Customers", "4. Money", "5. Decision", "6. Run a test", "7. Share"]


def answer(text, colour="lavender"):
    bg, bd, fg = PASTEL[colour]
    st.markdown(f'<div class="banner" style="background:{bg};border-color:{bd};padding:18px 22px"><div style="font-size:19px;line-height:1.5;color:#2b3047">{gloss(text)}</div></div>',
                unsafe_allow_html=True)


def more(*targets):
    cols = st.columns(len(targets) + 1)
    for c, (label, sec) in zip(cols, targets):
        if c.button(f"{label} →", key=f"more_{sec}", width="stretch"):
            ss.mode = "Full"; ss.section = sec; st.rerun()


def nxt(i):
    if i < len(PAGES) - 1 and st.button(f"Next: {PAGES[i + 1][3:]} →", type="primary" if i != 4 else "secondary", key=f"next{i}"):
        ss.simple_page = PAGES[i + 1]; st.rerun()


def idea(r, state):
    i = r["idea"]; cv = i["canvas"]
    st.header("Your idea")
    answer(f"<b>{esc(i['brief'])}</b>")
    c = st.columns(3)
    for col, (lab, key, colour) in zip(c, [("The problem", "problem", "rose"), ("Who it's for", "customer_segments", "sky"), ("Why it's different", "unique_value", "mint")]):
        bg, bd, _ = PASTEL[colour]
        col.markdown(f'<div class="pcard" style="background:{bg};border-color:{bd};min-height:150px"><div class="muted" style="font-size:13px">{lab}</div>'
                     f'<div style="font-size:15.5px;margin-top:4px">{esc(cv.get(key) or "–")}</div></div>', unsafe_allow_html=True)
    st.write("")
    with st.container(border=True):
        section("What has to be true for this to work", "peach")
        st.markdown("\n".join(f"{n + 1}. {esc(x)}" for n, x in enumerate(i["assumptions"][:5])))
        st.caption("The next pages check each of these against market data, simulated and real customers, and the numbers.")
    more(("Improve my idea", "Improve my idea"), ("Competition", "Competition"))
    nxt(0)


def market(r, state):
    from ui.search import summary_for as search_summary
    st.header("Is there a market?")
    m = MZ.size(r, state.get("market_overrides"), state.get("panel"))
    s = search_summary(state, r)
    comp = r["competition"]
    base = next(x for x in m["steps"] if x["key"] == "category")
    R = m.get("ranges") or dict(tam=(m["tam"]["people"],) * 2, sam=(m["sam"]["people"],) * 2, som=(m["som"]["people"],) * 2)
    tam_aed = lambda x: x * m["tam"]["aed"] / max(m["tam"]["people"], 1)
    lead = (f"Yes: roughly <b>{rng(*R['tam'])} people</b> {esc(base['label'].replace('…who ', '').replace(' (TAM)', ''))} in {esc(m['area'])}, "
            f"spending about <b>{aed(m['tam']['aed'])} a year</b>. One business like yours can reach roughly {rng(*R['sam'])} of them, "
            f"and could realistically win <b>{rng(*R['som'])} customers</b> (typical: {approx(m['som']['people'])}).")
    if s and s.get("total"):
        lead += f" People in the UAE search Google for this about <b>{approx(s['total'])} times a month</b>" + \
                (f", about {approx(s['local_total'])} of them in {esc(s['local_area'])}." if s.get("local_total") else ".")
    answer(lead, "sky")
    k = st.columns(4)
    kpi(k[0], 0, "Total market (TAM)", aed(m["tam"]["aed"]) + "/yr", f"{rng(*R['tam'])} people")
    kpi(k[1], 1, "You can reach (SAM)", aed(m["sam"]["aed"]) + "/yr", f"{rng(*R['sam'])} people")
    kpi(k[2], 2, "You can win (SOM)", aed(m["som"]["aed"]) + "/yr", f"{rng(*R['som'])} customers")
    if s and s.get("total"):
        kpi(k[3], 3, "Google searches a month", approx(s["total"]) if not s.get("ranges") else rng(s['total_low'], s['total_high']),
            (f"≈{approx(s['local_total'])} in {s['local_area']}" if s.get("local_total") else "UAE, for related phrases") + (f" · busiest in {s['peak']}" if s.get("peak") else ""))
    else:
        kpi(k[3], 3, "Google searches a month", "Not checked", "Open Search demand to add it")
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            section("Where these numbers come from", "mint")
            for x in m["steps"][:4]:
                t, tone = MKIND[x["kind"]]
                st.markdown(f"{esc(x['label'].replace('…', ''))}: <b>{num(x['people']) if x['kind'] == 'official' else 'about ' + approx(x['people'])}</b> <span class='pill p-{tone}'>{t}</span>"
                            f"<br><span class='muted' style='font-size:12.5px'>{esc(x['source'])}</span>", unsafe_allow_html=True)
    with c2:
        with st.container(border=True):
            section("Who you're up against", "rose")
            st.markdown(esc(comp["headline"]))
            for x in comp["competitors"][:3]:
                st.markdown(f"- **{esc(x['name'])}** ({esc(x['type'])}) · threat {round(x['threat'])}/100" + (f" · {aed(x['price_aed'])}/month" if x.get("price_aed") else ""))
            if comp.get("white_space"): st.markdown("**Your edge:** " + esc(", ".join(comp["white_space"][:3])))
    more(("Market size details", "Market size"), ("Search demand", "Search demand"), ("Competition", "Competition"))
    nxt(1)


def customers(r, state):
    from ui.social import summary_for as social_summary
    st.header("Do customers want it?")
    pn = state.get("panel"); so = social_summary(state, r)
    ps = PN.synthesise(pn, r) if pn else None
    hyps = store.list_hypotheses(user_id(), ss.pid)
    evs = [LB.evaluate(dict(h, price=r["assumptions"]["price"]["likely"]), state.get("experiments") or []) for h in hyps]
    tested = [e for e in evs if e["actual"] is not None]
    parts = []
    if ps: parts.append(f"In a simulated panel of {pn['n']} UAE customers, <b>{ps['counts']['yes']} would buy and {ps['counts']['maybe']} might</b>; "
                        f"the main worry is “{esc(ps['objections'][0]['title'].lower()) if ps['objections'] else 'none'}”.")
    if so:
        top = max(so["objections"], key=so["objections"].get)
        from ui.social import OBJ_LABEL
        parts.append(f"In {so['n']} real public posts, {pct(so['positive'])} are positive and {pct(so['demand'])} are people asking for something like this; "
                     f"the top complaint is {esc(OBJ_LABEL[top].lower())}.")
    dts = state.get("desk_tests") or {}
    nd = sum(1 for t in dts.values() if t.get("status") == "done")
    parts.append(f"Desk tests done: <b>{nd}</b> (no customers needed). " + (f"Optional customer tests: {sum(e['status'] == 'validated' for e in evs)} confirmed, "
                 f"{sum(e['status'] == 'invalidated' for e in evs)} disproved." if tested else ""))
    answer(" ".join(parts), "mint")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            section("What simulated customers say", "lavender")
            if ps:
                for o in ps["objections"][:3]: st.markdown(f"**{esc(o['title'])}** ({pct(o['share'])})  \n<span class='muted'>Fix: {esc(o['fix'])}</span>", unsafe_allow_html=True)
                for l in ps["likes"][:2]: st.markdown(f"👍 {esc(l['title'])} ({pct(l['share'])})")
            st.caption("Simulated, not real customers.")
    with c2:
        with st.container(border=True):
            section("What real people post", "sky")
            if so:
                for x in (so["examples"]["demand"][:2] + so["examples"]["negative"][:1]):
                    link = f' <a href="{esc(x["url"])}" target="_blank">open</a>' if x["url"] else ""
                    st.markdown(f"<span class='pill'>{esc(x['platform'])}</span> “{esc(x['text'][:160])}”{link}", unsafe_allow_html=True)
            else:
                st.markdown("No posts collected yet. Paste 10-20 comments from Instagram or Google reviews in Social listening; it takes two minutes.")
    with st.container(border=True):
        section("Your tests", "peach")
        for t in dts.values():
            tone = {"better": "good", "worse": "bad"}.get(t.get("direction"), "warn" if t.get("status") == "planned" else "info")
            st.markdown(f"<span class='pill p-{tone}'>{'Running' if t.get('status') == 'planned' else 'Desk test'}</span> {esc(t.get('finding') or t.get('name', ''))}", unsafe_allow_html=True)
        if hyps: st.caption("Optional tests with customers (validation lab):")
        for h, e in zip(hyps, evs):
            tone = {"validated": "good", "invalidated": "bad"}.get(e["status"], "warn")
            st.markdown(f"<span class='pill p-{tone}'>{e['status'].capitalize()}</span> {esc(h['statement'])}", unsafe_allow_html=True)
        if not hyps and not dts: st.markdown("No tests yet: page 6 suggests desk tests you can run alone.")
    more(("Customer panel", "Customer panel"), ("Social listening", "Social listening"), ("Validation lab", "Validation lab"))
    nxt(2)


def budget_text(s):
    if s["budget_lasts"]: return "budget lasts"
    m = s["runway_months"]
    return "setup and pre-opening costs use up the budget" if m == 0 else f"budget runs out after {m} month{'' if m == 1 else 's'}"


def money(r, state):
    st.header("Does the money work?")
    F = r["finance"]; f = r["stages"]["forecast"]; L = r["limits"]; sc = F["scenarios"]; be = F["break_even"]; t = F["tornado"]["rows"][0]
    pv = F.get("payback") or {}
    h = f["horizon"]; std = round(L["min_payback"] * 10)
    if pv.get("typical"):
        when = f"In a typical future you get your money back in <b>month {pv['typical']}</b>"
        safe = (f"; to be fairly safe ({std} in 10 futures) plan for <b>month {pv['safe']}</b>" if pv.get("safe") else
                f"; but fewer than {std} in 10 futures pay back within the plan")
    else:
        when = f"In a typical future you <b>do not get your money back within {h} months</b>"; safe = ""
    verdict = (f"Your limit is {h} months, so this <b>passes</b>." if pv.get("passes") else
               f"Your limit is {h} months, so this <b>misses by {pv['months_over']} months</b>." if pv.get("months_over") else
               f"Your limit is {h} months, so this <b>does not pass</b>.")
    best = (r.get("decision") or {}).get("best")
    fix = (f" “{esc(best['name'])}” would bring the typical payback to month {round(best['payback_median'])}." if best and best.get("payback_median") and not pv.get("passes") else "")
    lead = (f"You need about <b>{approx(be['customers'])} customers</b> to cover your monthly costs. {when}{safe}. {verdict}{fix} "
            f"Have about <b>{aed(F['runway']['cash_need_p90'])}</b> ready. What matters most: {esc(t['name'].lower())}.")
    answer(lead, "butter")
    cols = st.columns(3)
    for col, (key, name, colour) in zip(cols, [("bad", "Bad case", "rose"), ("typical", "Typical case", "sky"), ("good", "Good case", "mint")]):
        s_ = sc[key]; bg, bd, fg = PASTEL[colour]
        col.markdown(f'<div class="pcard" style="background:{bg};border-color:{bd}"><div style="font-weight:700;color:{fg}">{name}</div>'
                     f'<div style="font-size:24px;font-weight:700;margin:4px 0">{aed(s_["npv"])}</div><div class="muted" style="font-size:13.5px">'
                     f'{"Money back in month " + str(s_["payback_month"]) if s_["payback_month"] else "Money not back within " + str(h) + " months"} · '
                     f'{budget_text(s_)}</div></div>', unsafe_allow_html=True)
    from ui import case_detail
    case_detail.buttons(cols, r)
    st.caption("Each case is one complete simulated future, picked by its total value (NPV, what the business is worth to you after paying back what you put in) "
               "at the 10th, 50th and 90th percentile. They are ranked by value, not by speed, so a bigger-growing future can pay back later: open the details to see why. "
               "“Money back” = the first month cumulative cash, after setup and pre-opening costs, is back to zero.")
    k = st.columns(3)
    head, sub, ok = payback_line(r)
    kpi(k[0], 0, "Typical payback", head, sub)
    kpi(k[1], 2, "Chance of needing more than your budget", pct(f["p_ruin"]), f"Your limit {pct(L['max_ruin'])}")
    kpi(k[2], 1, "Each customer brings", aed(be["contribution"]) + "/month", "after variable costs")
    sensitivity_table(r)
    more(("Financials", "Financials"), ("What-if lab", "What-if lab"))
    nxt(3)


def sensitivity_table(r):
    """What would change the answer: the two inputs that most often decide it. Uses replays already run."""
    import pandas as pd
    S = r.get("sensitivity")
    if not S: return
    with st.expander("What would change the answer? (sensitivity)", expanded=False):
        st.caption(gloss("How the chance of paying back within your time limit moves if the buyers within reach, or your price, differ from the estimate. "
                         "The sensitivity of the plan shows which number to check first."))
        c1, c2 = st.columns(2)
        std = r["limits"]["min_payback"]
        c1.markdown("**If buyers within reach are…**")
        c1.dataframe(pd.DataFrame([{"Of the estimate": f"{x['mult']:.0%}", "Buyers": approx(x["buyers"]), "Paid back in time": pct(x["p_payback"]),
                                    "Passes": "✓" if x["p_payback"] >= std else "✗"} for x in S["market"]]), hide_index=True, width="stretch")
        c2.markdown("**If your price is…**")
        c2.dataframe(pd.DataFrame([{"Price": aed(x["price"]) + "/month", "Typical payback": f"month {round(x['payback_median'])}" if x["payback_median"] else "beyond plan",
                                    "Paid back in time": pct(x["p_payback"]), "Passes": "✓" if x["p_payback"] >= std and x["p_ruin"] <= r["limits"]["max_ruin"] else "✗"} for x in S["price"]]),
                     hide_index=True, width="stretch")


def decision_page(r, state):
    decision.page(r, state)
    nxt(4)


def test_page(r, state):
    from ui import loop
    loop.page(r, state)
    nxt(5)


def share_page(r, state):
    from ui import share
    share.page(r, state)


def render(name):
    from ui import loop, share
    r, state = ss.result, ss.state
    loop.progress(r, state)
    {"1. Idea": idea, "2. Market": market, "3. Customers": customers, "4. Money": money, "5. Decision": decision_page,
     "6. Run a test": test_page, "7. Share": share_page}.get(name, decision_page)(r, state)
    share.comments_box(name[3:])
