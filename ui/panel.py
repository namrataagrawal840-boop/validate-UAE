"""Customer panel: simulated UAE customers react to the idea, answer a survey, debate it in a focus group, and the answers are summarised.
Everything here is simulated and labelled as such; it never counts as evidence."""
import copy
import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import agents as AG
from app import lab as LB
from app import panel as PN
from app import store
from ui.common import ss, esc, pct, aed, kpi, chart, section, soft, PASTEL, PLOT, LINE, refresh, user_id

TONE = {"yes": "mint", "maybe": "butter", "no": "rose"}
LABEL = {"yes": "Would buy", "maybe": "Maybe", "no": "Wouldn't buy"}


def avatar(p):
    bg, bd, fg = PASTEL[TONE[p["intent"]]]
    ini = "".join(w[0] for w in p["name"].split()[:2])
    return f'<span style="display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;border-radius:50%;background:{bg};border:1px solid {bd};color:{fg};font-weight:700;margin-right:8px">{esc(ini)}</span>'


def save_panel(panel, message):
    state = copy.deepcopy(ss.state); state["panel"] = panel
    store.save_project(user_id(), ss.pid, state=state); ss.state = state; ss.flash = message; st.rerun()


def run(r, size, debate_size, use_ai):
    with st.status("Building the panel…", expanded=True) as box:
        st.write(f"Drawing {size} people from the simulated UAE market and working out their reactions…")
        panel = PN.build(r, n=size, seed=int(dt.datetime.now().timestamp()) % 100000)
        if use_ai:
            st.write("Claude is writing each person's own opinion…")
            PN.ai_voices(panel, r)
        st.write("Running the focus-group debate…")
        panel["debate"] = PN.ai_debate(panel, r, size=debate_size) if use_ai else PN.debate(panel, r, size=debate_size)
        box.update(label="Panel ready", state="complete")
    save_panel(panel, f"Panel of {panel['n']} simulated customers is ready.")


def page(r, state):
    st.header("Customer panel")
    st.markdown(soft("<b>Simulated customers, not real ones.</b> Each person is drawn from the synthetic UAE market, with their own age, income, habits, "
                     "problem severity and budget. They give feedback, answer a price survey and debate your idea. Use it to find objections, questions "
                     "and fixes before you spend money. It <b>never</b> counts as evidence and does not change evidence confidence.", "lavender"), unsafe_allow_html=True)
    panel = state.get("panel")
    ai_ok = AG.enabled()
    with st.expander("➕ Run a new panel" if panel else "➕ Run your first panel", expanded=not panel):
        with st.form("panel_run"):
            c = st.columns(3)
            size = c[0].select_slider("Panel size", [20, 40, 80, 150], 40, help="More people give steadier percentages.")
            dsz = c[1].select_slider("Focus group size", [4, 5, 6, 7, 8], 6)
            use_ai = c[2].checkbox("Claude writes their opinions", value=ai_ok, disabled=not ai_ok,
                                   help="Each person's view comes from Claude, given their profile; adds an independent judgement." if ai_ok else
                                   "Add ANTHROPIC_API_KEY in the app's secrets to enable. Without it, reactions follow the buying model and the text uses templates.")
            go_ = st.form_submit_button("Run the panel", type="primary")
        if go_: run(r, size, dsz, use_ai and ai_ok)
        if panel: st.caption("A new run replaces the current panel.")
    if not panel: return
    s = PN.synthesise(panel, r)
    mode = "Opinions written by Claude" if panel["mode"] == "ai" else "Opinions follow the buying model; text from templates"
    st.caption(f"{panel['n']} simulated customers · {mode} · run on {panel['created_at'][:10]}")
    tabs = st.tabs(["Answers", "People", "Feedback and survey", "Focus group", "Ask a person"])
    with tabs[0]: answers(panel, s, r, state)
    with tabs[1]: people(panel)
    with tabs[2]: feedback(panel, s)
    with tabs[3]: focus(panel)
    with tabs[4]: ask(panel, r, ai_ok)


def answers(panel, s, r, state):
    colour = {"Strong interest": "mint", "Some interest": "butter", "Little interest": "rose"}[s["verdict"]]
    bg, bd, fg = PASTEL[colour]
    st.markdown(f'<div class="banner" style="background:{bg};border-color:{bd}"><div class="k">What the simulated panel says</div><h2 style="color:{fg}">{s["verdict"]}</h2>'
                f'<div>{esc(s["headline"])}</div></div>', unsafe_allow_html=True)
    k = st.columns(4)
    kpi(k[0], 0, "Say they would buy", f"{s['counts']['yes']} of {panel['n']}", f"{s['counts']['maybe']} more say maybe")
    kpi(k[1], 1, "Likely to actually buy", pct(s["actual_rate"], 1), "After the usual say-do gap")
    kpi(k[2], 2, "Accept your price", pct(s["acceptance"]), f"at {aed(panel['price'])} a month")
    kpi(k[3], 3, "Recommend score (NPS)", f"{s['nps']['nps']:+.0f}", f"Average rating {s['avg_rating']:.1f}/10")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            section("Main objections", "rose")
            for o in s["objections"][:5]:
                st.markdown(f"**{esc(o['title'])}** · {pct(o['share'])} of the panel  \n<span class='muted'>Fix: {esc(o['fix'])}</span>", unsafe_allow_html=True)
    with c2:
        with st.container(border=True):
            section("What they like", "mint")
            for l in s["likes"][:4]: st.markdown(f"- {esc(l['title'])} ({pct(l['share'])})")
            if s["debate"]:
                d = s["debate"]
                st.markdown(f"**Focus group:** average intent went from {pct(d['start'])} to {pct(d['end'])}. Final vote: {d['votes']['yes']} yes, {d['votes']['maybe']} maybe, "
                            f"{d['votes']['no']} no. Main concern: “{esc(d['concern'])}”. Most persuasive voice: {esc(d['influential'].rstrip('.'))}.")
    with st.container(border=True):
        section("Which customers respond best", "sky")
        st.dataframe(pd.DataFrame([dict(Group=x["segment"], People=x["n"], **{"Say they would buy": pct(x["yes_share"]), "Average rating": f"{x['avg_rating']:.1f}"}) for x in s["segments"]]),
                     hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            section("What to change", "peach")
            st.markdown("\n".join(f"{i + 1}. {esc(x)}" for i, x in enumerate(s["changes"])) or "No clear changes.")
    with c2:
        with st.container(border=True):
            section("Ask real customers", "lavender", "Questions that would test what the panel raised")
            st.markdown("\n".join(f"- {esc(q)}" for q in s["questions"]))
    st.caption(s["caveat"])
    c = st.columns([1.6, 1.6, 3])
    hyps = store.list_hypotheses(user_id(), ss.pid)
    have = {h["metric"] for h in hyps}
    new = [x for x in LB.suggestions(r) if x["metric"] in ("pain_share", "price_acceptance", "signup_rate") and x["metric"] not in have]
    if c[0].button("Turn into hypotheses to test", disabled=not new, help="Adds hypotheses to the Validation lab so real customers can confirm or reject what the panel suggested."
                   if new else "The matching hypotheses are already in the Validation lab."):
        for h in new[:3]:
            h = dict(h, status="planned", direction=LB.METRICS[h["metric"]][3]); h["plan"] = LB.plan(dict(h, id="new"), r, r["kit"])
            store.add_hypothesis(user_id(), ss.pid, h)
        ss.flash = f"Added {len(new[:3])} hypotheses to the Validation lab."; ss.section = "Validation lab"; st.rerun()
    if c[1].button("Record in the evidence ledger", help="Saved as a synthetic simulation record with zero weight, so the decision can show it existed without counting it."):
        store.add_evidence(user_id(), ss.pid, dict(claim=f"Simulated panel: {s['counts']['yes']} of {panel['n']} say they would buy; about {s['actual_rate']:.1%} likely to buy",
                                                  area="market", ev_type="synthetic", description=s["headline"], collected_on=dt.date.today().isoformat(), geography="target",
                                                  sample_size=panel["n"], verification="unverified", confidence="low",
                                                  limitations="Simulated people. Not evidence of real customer behaviour."))
        refresh("Panel recorded in the ledger as a synthetic simulation (zero weight).")


def people(panel):
    flt = st.segmented_control("Show", ["Everyone", "Would buy", "Maybe", "Wouldn't buy"], default="Everyone", key="pp_f")
    want = {"Would buy": "yes", "Maybe": "maybe", "Wouldn't buy": "no"}.get(flt)
    ps = [p for p in panel["people"] if not want or p["intent"] == want]
    st.caption(f"{len(ps)} people")
    for i in range(0, len(ps), 3):
        cols = st.columns(3)
        for col, p in zip(cols, ps[i:i + 3]):
            with col.container(border=True):
                bg, bd, fg = PASTEL[TONE[p["intent"]]]
                st.markdown(f"{avatar(p)}<b>{esc(p['name'])}</b>, {p['age']}<br><span class='muted' style='font-size:13px'>{esc(p['job'].capitalize())} · {esc(p['household'])} · "
                            f"{esc(p['emirate'])} · {esc(p['income_band'].lower())} income · buys {esc(p['habits'])}</span><br>"
                            f"<span class='pill' style='background:{bg};color:{fg};border:1px solid {bd}'>{LABEL[p['intent']]}</span><span class='pill'>Rating {p['rating']}/10</span>"
                            f"<span class='pill p-lav'>Simulated</span>", unsafe_allow_html=True)
                st.markdown(f"<i>“{esc(p['quote'])}”</i>", unsafe_allow_html=True)
                st.markdown(f"<span class='muted' style='font-size:13px'>Would change my mind: {esc(p['change_mind'])}<br>Would pay up to about {aed(p['wtp'])}/month · "
                            f"group: {esc(p['segment'])}</span>", unsafe_allow_html=True)


def feedback(panel, s):
    ps = panel["people"]
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**Would they buy? By customer group**")
            segs = sorted({p["segment"] for p in ps})
            fig = go.Figure()
            for k in ("yes", "maybe", "no"):
                fig.add_trace(go.Bar(y=segs, x=[sum(p["segment"] == g and p["intent"] == k for p in ps) for g in segs], orientation="h", name=LABEL[k],
                                     marker_color=PASTEL[TONE[k]][1]))
            fig.update_layout(**{**PLOT, "height": 80 + 50 * len(segs), "margin": dict(l=10, r=10, t=36, b=10)}, barmode="stack", legend=dict(orientation="h", y=1.2, x=0))
            chart(fig)
    with c2:
        with st.container(border=True):
            st.markdown("**How likely to recommend (0-10)**")
            fig = go.Figure(go.Bar(x=list(range(11)), y=[sum(p["rating"] == v for p in ps) for v in range(11)],
                                   marker_color=["#f3d6de"] * 7 + ["#f2e6b6"] * 2 + ["#d3ecdf"] * 2))
            fig.update_layout(**{**PLOT, "height": 260}, xaxis=dict(dtick=1, title="Detractors 0-6 · passives 7-8 · promoters 9-10"), yaxis=dict(visible=False))
            chart(fig)
    vw = s["van_westendorp"]
    if vw:
        with st.container(border=True):
            st.markdown("**Simulated price survey (Van Westendorp)**")
            c = st.columns(4)
            for j, (l, x) in enumerate([("Lowest acceptable", vw["pmc"]), ("Optimal price", vw["opp"]), ("Indifference price", vw["ipp"]), ("Highest acceptable", vw["pme"])]): c[j].metric(l, aed(x))
            fig = go.Figure()
            for key, name, col in [("too_cheap", "Too cheap", "#c9cff7"), ("cheap", "Cheap", LINE), ("expensive", "Expensive", "#f0c27a"), ("too_expensive", "Too expensive", "#e3a3a8")]:
                fig.add_trace(go.Scatter(x=vw["curves"]["price"], y=vw["curves"][key], name=name, line=dict(color=col, width=2)))
            fig.add_vline(x=panel["price"], line=dict(color="#6b7189", dash="dash"), annotation_text="Your price")
            fig.update_layout(**{**PLOT, "height": 280}, yaxis=dict(tickformat=".0%"), legend=dict(orientation="h", y=-.25))
            chart(fig)
    df = pd.DataFrame([dict(Name=p["name"], Age=p["age"], Emirate=p["emirate"], Income=p["income_band"], Group=p["segment"], **{"Would buy": LABEL[p["intent"]]},
                            Rating=p["rating"], **{"Max price (AED)": round(p["wtp"])}, **{"Main objection": p["objection_title"]}, Quote=p["quote"]) for p in ps])
    st.dataframe(df, hide_index=True, width="stretch")
    st.download_button("Download panel answers (CSV)", df.to_csv(index=False), file_name="simulated-panel.csv", mime="text/csv")


def focus(panel):
    d = panel.get("debate")
    if not d: st.info("Not enough people for a focus group. Run a larger panel."); return
    people = {p["id"]: p for p in panel["people"]}
    c1, c2 = st.columns([1.5, 1])
    with c1:
        for l in d["lines"]:
            p = people.get(l.get("pid"))
            if not p:
                st.markdown(f'<div class="soft" style="background:#f4f2ff;border-color:#e3defb"><b>Moderator</b><br>{esc(l["text"])}</div>', unsafe_allow_html=True)
            else:
                tone = "yes" if l.get("intent", .5) >= .6 else "maybe" if l.get("intent", .5) >= .3 else "no"
                bg, bd, _ = PASTEL[TONE[tone]]
                st.markdown(f'<div class="soft" style="background:{bg};border-color:{bd};margin-left:28px">{avatar(p)}<b>{esc(p["name"])}</b>'
                            f'<span class="muted" style="font-size:12.5px"> · {p["age"]}, {esc(p["job"])}</span><br>{esc(l["text"])}</div>', unsafe_allow_html=True)
    with c2:
        with st.container(border=True):
            st.markdown("**How opinions moved**")
            h = d["history"]; fig = go.Figure()
            for j, pid in enumerate(d["members"]):
                fig.add_trace(go.Scatter(x=["Start"] + [f"Round {i}" for i in range(1, len(h))], y=[row[j] for row in h], name=people[pid]["name"], mode="lines+markers"))
            fig.add_hrect(y0=.6, y1=1, fillcolor="#eef8f3", line_width=0, layer="below"); fig.add_hrect(y0=0, y1=.3, fillcolor="#fdf0f3", line_width=0, layer="below")
            fig.update_layout(**{**PLOT, "height": 340}, yaxis=dict(range=[0, 1], tickformat=".0%", title="Intent to buy"), legend=dict(orientation="h", y=-.3))
            chart(fig)
            st.caption("Opinions move by the Friedkin–Johnsen model: each person blends their first view with the views of similar, convinced people, "
                       "weighted by how open they are." if d.get("mode") != "ai" else "Turns written by Claude; the chart shows the model's opinion dynamics for the same group.")
            st.markdown(f"**Final vote:** {d['final_votes']['yes']} yes · {d['final_votes']['maybe']} maybe · {d['final_votes']['no']} no")


def ask(panel, r, ai_ok):
    p = st.selectbox("Choose a person", panel["people"], format_func=lambda p: f"{p['name']}, {p['age']} · {p['job']} · {LABEL[p['intent']]}")
    st.markdown(f"{avatar(p)}<b>{esc(p['name'])}</b> <span class='pill p-lav'>Simulated</span><br><span class='muted'>{esc(PN._persona_card(p))}</span>", unsafe_allow_html=True)
    if not ai_ok:
        st.info("Chatting with a person needs Claude: add ANTHROPIC_API_KEY in the app's secrets. Their recorded answers are shown below.")
        st.markdown(f"**Their view:** {LABEL[p['intent']]} · rating {p['rating']}/10  \n**In their words:** “{esc(p['quote'])}”  \n**What would change their mind:** {esc(p['change_mind'])}")
        return
    key = f"chat_{ss.pid}_{p['id']}"; hist = ss.setdefault(key, [])
    for h in hist:
        with st.chat_message("user" if h["role"] == "user" else "assistant"): st.write(h["text"])
    q = st.chat_input(f"Ask {p['name'].split()[0]} something, e.g. what would you pay for this?")
    if q:
        hist.append(dict(role="user", text=q[:500]))
        try:
            hist.append(dict(role="persona", text=PN.ask(p, q, r, hist[:-1])))
        except Exception as e:  # noqa: BLE001
            hist.append(dict(role="persona", text=f"(Could not reach Claude: {e})"))
        st.rerun()
