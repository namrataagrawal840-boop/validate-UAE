"""Market and customers: source-backed insights first, each labelled as evidence, sourced (web) or estimate; then the customer-value analysis."""
import streamlit as st

from app import evidence as EV
from app import store
from ui import report
from ui.common import ss, esc, aed, pct, num, section, user_id


def tag(kind):
    t = {"evidence": ("Your evidence", "good"), "web": ("Sourced (web, unverified)", "info"), "ai": ("AI estimate", "lav"), "model": ("Model estimate", ""),
         "yours": ("Your data", "peach")}[kind]
    return f'<span class="pill p-{t[1]}">{t[0]}</span>'


def link(u):
    return f' <a href="{esc(u)}" target="_blank">source</a>' if str(u or "").startswith("http") else ""


def page(r, state):
    ag = state.get("agents") or {}
    st.header("Market and customers")
    st.markdown('<p class="muted">What is known about the market and the customer, and how well each point is supported. '
                'Green = your own evidence; blue = found on the web by the AI with a link; lavender = AI estimate; grey = model estimate.</p>', unsafe_allow_html=True)
    ledger = store.list_evidence(user_id(), ss.pid)
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            section("Market insights", "sky")
            mk = ag.get("market") or {}
            items = [(tag("evidence"), f"{esc(x['claim'])} ({EV.TYPES[x['ev_type']][0].lower()}, {EV.VERIFICATION.get(x['verification'] or 'unverified')[0].lower()})" + link(x.get("source_url")))
                     for x in ledger if x["area"] in ("market", "competition", "regulation") and EV.is_real(x)]
            items += [(tag("web") if t.get("url") else tag("ai"), esc(t["text"]) + link(t.get("url"))) for t in mk.get("trends", [])]
            if mk.get("tam_aed"): items.append((tag("ai"), f"Category spend about {aed(mk['tam_aed'])} a year; one new business could reach about {aed(mk.get('som_aed') or 0)} within 3 years. {esc(mk.get('tam_reasoning', ''))[:200]}"))
            if mk.get("growth_pct_per_year") is not None: items.append((tag("ai"), f"Growth about {mk['growth_pct_per_year']:.0f}% a year."))
            s = r["market_sizing"]
            items.append((tag("model"), f"Synthetic population: category spend {aed(s['tam_synthetic'])}/year, {aed(s['sam'])} within reach, simulation suggests {aed(s['som_bottom_up'])}/year for you. {esc(s['note'])}"))
            for t_, x in items: st.markdown(f"{t_} {x}", unsafe_allow_html=True)
            if not mk: st.caption("Run with AI agents for web research on the market, or add reports to the evidence ledger.")
    with c2:
        with st.container(border=True):
            section("Customer pain points", "rose")
            cu = ag.get("customer") or {}
            items = [(tag("evidence"), esc(x["claim"]) + link(x.get("source_url"))) for x in ledger if x["area"] == "pain" and EV.is_real(x)]
            items += [(tag("web") if p.get("url") else tag("ai"), f"{esc(p['pain'])} · intensity {round(p['intensity'])}/100" + link(p.get("url"))) for p in cu.get("pains", [])]
            tx = r["stages"]["text"]
            if tx["status"] == "ran":
                items += [(tag("yours"), f"Theme in your reviews or notes: {esc(', '.join(t['terms'][:4]))} ({pct(t['share'])} of texts, {pct(t['negative_share'])} negative)") for t in tx["topics"][:3]]
            items.append((tag("model"), f"In the simulated market, likely buyers have pain {pct(r['value']['pain_adopters'])} on average with today's options."))
            for t_, x in items: st.markdown(f"{t_} {x}", unsafe_allow_html=True)
            quotes = cu.get("evidence", [])[:5]
            if quotes:
                st.markdown("**What people say online** " + tag("web"), unsafe_allow_html=True)
                for q in quotes: st.markdown(f"<span class='muted'>“{esc(q['quote'])}”</span>{link(q.get('url'))}", unsafe_allow_html=True)
            alts = cu.get("alternatives") or []
            if alts:
                st.markdown("**What they use today** " + tag("web"), unsafe_allow_html=True)
                for a in alts: st.markdown(f"- {esc(a['name'])}: {aed(a['monthly_cost_aed'])}/month{link(a.get('url'))}", unsafe_allow_html=True)
    st.divider()
    report.tab_value(r, state)
