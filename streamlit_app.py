"""ValidateUAE - Streamlit version.

Run locally:   streamlit run streamlit_app.py
Deploy:        share.streamlit.io -> New app -> this repository -> streamlit_app.py
Secrets:       ANTHROPIC_API_KEY (optional; without it the app uses category priors)
"""
import copy
import json
import os
import sys
import threading
import time

import streamlit as st

st.set_page_config(page_title="ValidateUAE", page_icon="🌿", layout="wide")

# Secrets -> environment, before the backend is imported
for _k in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "WEB_SEARCH_TOOL", "SIM_MODE"):
    try:
        if _k in st.secrets and not os.getenv(_k):
            os.environ[_k] = str(st.secrets[_k])
    except Exception:
        pass
os.environ.setdefault("SIM_MODE", "fast")  # Streamlit Cloud has modest CPU; set SIM_MODE="full" in secrets for more replays
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
from app import priors as P  # noqa: E402
from app import agents as AG  # noqa: E402
from app.compute import compute, what_if, LABEL  # noqa: E402
from app.funnel.validation import SUS_QUESTIONS  # noqa: E402
from ui_explain import explain, aed, pct, num  # noqa: E402

# ---------------- look: white, calm, pastel only on headline numbers ----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stButton button, input, textarea, select { font-family: 'Plus Jakarta Sans', system-ui, sans-serif !important; }
.block-container { padding-top: 2rem; max-width: 1180px; }
h1, h2, h3 { color: #2b3047; letter-spacing: -.015em; }
.kpi { border-radius: 14px; padding: 14px 16px; border: 1px solid; height: 100%; }
.kpi .l { font-size: 13px; color: #6b7189; } .kpi .v { font-size: 26px; font-weight: 700; color: #2b3047; line-height: 1.25; } .kpi .s { font-size: 12.5px; color: #6b7189; }
.k0 { background: #f4f2ff; border-color: #e6e1fc; } .k1 { background: #eef8f3; border-color: #d8efe3; } .k2 { background: #fff5ee; border-color: #fbe0ce; } .k3 { background: #eff6ff; border-color: #d9e8fb; }
.box { border: 1px solid #eceef4; border-radius: 14px; padding: 16px 18px; background: #fff; margin-bottom: 4px; }
.banner { border-radius: 18px; padding: 22px 24px; border: 1px solid; margin-bottom: 8px; }
.banner h2 { margin: 2px 0 8px; font-size: 30px; } .banner .k { color: #6b7189; font-size: 14px; }
.b-launch { background: #eef8f3; border-color: #d8efe3; } .b-pivot { background: #eff6ff; border-color: #d9e8fb; }
.b-test { background: #fffaea; border-color: #f4e8bb; } .b-stop { background: #fdf1f4; border-color: #f5d9e2; }
.pill { display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 9px; border-radius: 999px; background: #f3f4f8; color: #6b7189; margin-right: 4px; }
.p-good { background: #e9f6ef; color: #3f8f72; } .p-warn { background: #fdf5df; color: #9a6e1f; } .p-bad { background: #fcedef; color: #b0555b; } .p-info { background: #edf0ff; color: #5468c8; }
.muted { color: #6b7189; font-size: 14px; }
[data-testid="stMetricValue"] { font-size: 24px !important; font-weight: 600; color: #2b3047; }
[data-testid="stMetricLabel"] p { color: #6b7189 !important; }
div[data-testid="stTabs"] button p { font-size: 15px; }
</style>
""", unsafe_allow_html=True)

PLOT = dict(template="simple_white", height=300, margin=dict(l=10, r=10, t=10, b=10), font=dict(family="Plus Jakarta Sans, sans-serif", size=12, color="#6b7189"))
LINE, BAND, ZERO = "#6470dc", "rgba(118,130,230,.16)", "#d9a35a"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
months = lambda n: [f"{MON[i % 12]} {str(P.START_YEAR + i // 12)[2:]}" for i in range(n)]
EXAMPLES = [
    dict(idea="A cloud kitchen in Business Bay delivering healthy, high-protein lunches to office workers, ordered through our own app and the delivery platforms.", business_type="kitchen", emirate="Dubai", setup="Mainland", target_customer="Office workers aged 25-45 in Business Bay and DIFC", budget_aed=600000),
    dict(idea="An online platform that matches children aged 6 to 14 with qualified Arabic tutors for live lessons, with weekly progress reports for parents.", business_type="education", emirate="All UAE", setup="Free zone", target_customer="Parents who want their children to improve their Arabic", budget_aed=300000),
    dict(idea="A women-only boutique fitness studio in Sharjah with small group classes, childcare during sessions and flexible class packs.", business_type="fitness", emirate="Sharjah", setup="Mainland", target_customer="Women aged 25-50 living in Sharjah", budget_aed=900000),
]
ss = st.session_state
_N = [0]


def chart(fig):
    _N[0] += 1
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=f"chart{_N[0]}")


def kpi(col, i, label, value, sub="", math_key=None):
    with col:
        st.markdown(f'<div class="kpi k{i % 4}"><div class="l">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)
        if math_key: math(math_key)


def pill(text, tone=""):
    return f'<span class="pill p-{tone}">{text}</span>'


def tone(score):
    return "" if score is None else "good" if score >= 65 else "warn" if score >= 45 else "bad"


def math(key, label="Show the math"):
    d = ss.get("_explain", {}).get(key)
    if not d: return
    title, plain, formula, inputs = d
    with st.popover(label):
        st.markdown(f"**{title}**")
        st.write(plain)
        st.code(formula, language=None)
        if inputs:
            st.dataframe(pd.DataFrame(inputs, columns=["Input", "Value", "Source"]), hide_index=True, width="stretch")


def fan(band, money=False, height=300):
    n = len(band["p50"]); x = months(n)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x + x[::-1], y=band["p90"] + band["p10"][::-1], fill="toself", fillcolor=BAND, line=dict(width=0), name="Bad to good case", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=band["p50"], line=dict(color=LINE, width=2.5), name="Typical"))
    if money: fig.add_hline(y=0, line=dict(color=ZERO, dash="dash", width=1.5))
    fig.update_layout(**{**PLOT, "height": height}, showlegend=False, yaxis=dict(gridcolor="#f1f2f7", showgrid=True), xaxis=dict(nticks=7))
    chart(fig)


def hbars(rows, height=None, fmt=lambda v: f"{v:.0%}", color="#aab3f2", log=False, xmax=None):
    names = [r[0] for r in rows][::-1]; vals = [max(r[1], 1e-9) for r in rows][::-1]
    fig = go.Figure(go.Bar(x=vals, y=names, orientation="h", marker=dict(color=color), text=[fmt(v) for v in vals], textposition="outside", cliponaxis=False))
    xa = dict(visible=False, type="log", range=[np.log10(min(vals)) - 1, np.log10(max(vals)) + .45]) if log else dict(visible=False, range=[0, (xmax or max(vals)) * 1.3])
    fig.update_layout(**{**PLOT, "height": height or 40 + 34 * len(rows)}, xaxis=xa, yaxis=dict(tickfont=dict(color="#2b3047")))
    chart(fig)


# ---------------- running an analysis ----------------
NAMES = dict(orch="Orchestrator", market="Market agent", customer="Customer agent", competition="Competition agent", finance="Finance agent", regulation="Regulation agent",
             usability="Ease-of-use agent", consistency="Consistency checker", kit="Experiment writer", critic="Critic")


def run_analysis(intake, use_ai, competitors=None):
    state = dict(intake=intake, agents={}, overrides={}, experiments=[], settings={}, applied=[], competitors=competitors or [])
    log = []
    if use_ai and AG.enabled():
        prog, out = {}, {}
        th = threading.Thread(target=lambda: out.update(res=AG.run_agents(intake, lambda s, status, text: prog.__setitem__(s, (status, text)))), daemon=True)
        with st.status("AI agents are researching your idea on the web…", expanded=True) as box:
            ph = st.empty(); th.start()
            while th.is_alive():
                ph.markdown("\n".join(f"- {'✅' if v[0] == 'done' else '⚠️' if v[0] == 'fallback' else '⏳'} **{NAMES.get(k, k)}** {v[1]}" for k, v in prog.items()) or "Starting…")
                time.sleep(1)
            agents, sources, errors = out.get("res", ({}, {}, {"all": "failed"}))
            state.update(agents=agents, sources=sources, agent_errors=errors)
            log = [(NAMES.get(k, k), v[0], v[1]) for k, v in prog.items()]
            box.update(label="Research done", state="complete")
    else:
        log = [("Offline mode", "done", "AI agents off: using category priors for the UAE.")]
    with st.spinner("Running the 10-stage funnel and the agent-based market simulation…"):
        result = compute(state)
    ss.state, ss.result, ss.log = state, result, log
    ss._explain = explain(result)


def recompute(mutate, message):
    state = copy.deepcopy(ss.state); mutate(state)
    with st.spinner("Recalculating…"):
        ss.result = compute(state)
    ss.state = state; ss._explain = explain(ss.result); ss.flash = message
    st.rerun()


# ---------------- page: start ----------------
def page_start():
    ss.setdefault("f_budget_aed", 500000)
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.title("Test a business idea against the UAE market before you spend on it")
        st.markdown('<p class="muted" style="font-size:17px">AI agents research your idea on the web with sources. Ten algorithm stages turn the research into one decision. An agent-based simulation replays the market customer by customer, with word of mouth, a reacting competitor and random shocks, and checks the result against your cash and your appetite for risk.</p>', unsafe_allow_html=True)
        st.markdown('<div class="box"><b>How it decides</b><ol class="muted" style="margin:6px 0 0 0">'
                    '<li>Describe the market and group buyers (statistics, Gaussian mixture)</li><li>Flag unrealistic assumptions (Isolation Forest)</li>'
                    '<li>Predict who buys and how much they spend (choice model, regression)</li><li>Model how long customers stay (survival analysis)</li>'
                    '<li>Simulate thousands of UAE customers with friend networks, a reacting competitor, shocks and seasons (agent-based model)</li>'
                    '<li>Read customer complaints (TF-IDF)</li><li>Plan the tests that settle it (Bayesian A/B)</li><li>Allocate the budget and pick the best plan (linear programming)</li></ol></div>', unsafe_allow_html=True)
        st.markdown("**Try an example**")
        for i, x in enumerate(EXAMPLES):
            if st.button(x["idea"], key=f"ex{i}", width="stretch"):
                for k, v in x.items(): ss[f"f_{k}"] = v
                st.rerun()
        up = st.file_uploader("Or open a saved report (.json)", type="json")
        if up:
            try:
                state = json.load(up)
                with st.spinner("Opening…"): ss.result = compute(state)
                ss.state, ss.log, ss._explain = state, [("Restored", "done", "Opened from a saved file.")], explain(ss.result); st.rerun()
            except Exception as e:
                st.error(f"That file could not be opened: {e}")
    with right:
        with st.form("intake"):
            st.subheader("1. The idea")
            idea = st.text_area("Describe it in plain words", key="f_idea", placeholder="A home-cleaning subscription for villas in Arabian Ranches, booked through WhatsApp", height=110)
            c1, c2 = st.columns(2)
            types = list(P.TYPES)
            bt = c1.selectbox("Business type", types, format_func=lambda k: P.TYPES[k]["label"], key="f_business_type")
            ems = ["All UAE"] + [e[0] for e in P.EMIRATES]
            em = c2.selectbox("Where", ems, key="f_emirate")
            setup = c1.selectbox("Setup", ["Mainland", "Free zone", "Online only", "Home-based"], key="f_setup")
            cust = c2.text_input("Target customer", key="f_target_customer", placeholder="Families in Dubai Marina")
            st.subheader("2. Your decision limits")
            c1, c2 = st.columns(2)
            budget = c1.number_input("Cash you can put in (AED)", min_value=1000, step=10000, key="f_budget_aed")
            horizon = c2.selectbox("Time to pay back", [24, 36, 48, 60], index=1, format_func=lambda m: f"{m} months")
            minp = c1.select_slider("Minimum chance of paying back", [.5, .6, .7, .8], value=.6, format_func=lambda v: f"{v:.0%}")
            maxr = c2.select_slider("Most risk of running out you accept", [.05, .1, .2, .3], value=.2, format_func=lambda v: f"{v:.0%}")
            with st.expander("3. Numbers and evidence you already have (optional)"):
                c1, c2, c3 = st.columns(3)
                price = c1.number_input("Spend per customer / month (AED)", min_value=0, value=0)
                fixed = c2.number_input("Fixed costs / month (AED)", min_value=0, value=0)
                setupc = c3.number_input("Setup cost (AED)", min_value=0, value=0)
                ev = st.text_area("Customer reviews, complaints or interview notes (one per line)")
                kc = st.text_area("Competitors you already know, one per line: name, price per month in AED, what they offer", placeholder="ArabicKids Online, 400, live Arabic lessons for children\nKumon, 550, maths and English worksheets")
            ai_ok = AG.enabled()
            use_ai = st.checkbox("Use AI agents with web research", value=ai_ok, disabled=not ai_ok, help=None if ai_ok else "Add ANTHROPIC_API_KEY to the app's secrets to enable.")
            go_ = st.form_submit_button("Run the validation", type="primary", width="stretch")
        if go_:
            if len((idea or "").strip()) < 20:
                st.error("Describe the idea in at least one full sentence (20 characters or more).")
            else:
                intake = dict(idea=idea.strip()[:2000], business_type=bt, emirate=em, setup=setup, target_customer=(cust or "")[:300], budget_aed=float(budget),
                              min_payback_probability=minp, max_ruin_probability=maxr, horizon_months=horizon, price=price or None, fixed=fixed or None,
                              setup_budget=setupc or None, evidence_text=ev[:20000], use_ai=use_ai)
                try:
                    comps = []
                    for line in (kc or "").splitlines()[:15]:
                        parts = [x.strip() for x in line.split(",")]
                        if parts and len(parts[0]) >= 2:
                            pr = next((float(x) for x in parts[1:2] if x.replace(".", "", 1).isdigit()), None)
                            comps.append(dict(name=parts[0][:120], type="direct", price_aed=pr, rating=None, note=", ".join(parts[2 if pr else 1:])[:240], features=[], url="", strengths=[], weaknesses=[]))
                    run_analysis(intake, use_ai, comps); st.rerun()
                except Exception as e:
                    st.error(f"Something went wrong: {e}")


# ---------------- page: report ----------------
def tab_decision(r, state):
    f, dec, L, ag, v = r["stages"]["forecast"], r["decision"], r["limits"], state.get("agents", {}), r["validation"]
    st.markdown(f'<div class="banner b-{dec["code"]}"><div class="k">{r["intake"]["emirate"]} · {r["intake"]["setup"]} · {r["idea"]["brief"]}</div><h2>{dec["label"]}</h2>'
                + "".join(f"<div>• {x}</div>" for x in dec["reasons"]) + "</div>", unsafe_allow_html=True)
    c = st.columns([1, 1, 1, 3]);
    with c[0]: math("decision", "How this is decided")
    summary = summary_text(r)
    c[1].download_button("Download summary", summary, file_name="validateuae-summary.txt", width="stretch")
    c[2].download_button("Save report", json.dumps(ss.state, default=str), file_name="validateuae-report.json", width="stretch", help="Open it later from the start page")
    cols = st.columns(4)
    kpi(cols[0], 0, f"Chance of paying back in {f['horizon']} months", pct(f["p_payback"]), f"You need at least {pct(L['min_payback'])}", "p_payback")
    kpi(cols[1], 1, "Chance of needing more than your budget", pct(f["p_ruin"]), f"Limit {pct(L['max_ruin'])} · budget {aed(L['budget'])}", "p_ruin")
    kpi(cols[2], 2, "Expected value (NPV)", aed(f["npv_mean"]), f"Bad {aed(f['npv_p10'])} · good {aed(f['npv_p90'])}", "npv")
    kpi(cols[3], 3, "Evidence strength", pct(r["evidence"]["strength"]), "Inputs backed by sources or measurements", "evidence")
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("Validation score")
            st.markdown(f'<span style="font-size:52px;font-weight:700;color:#2b3047">{round(v["score"])}</span> &nbsp; {pill(v["verdict"], "good" if v["score"] >= 70 else "warn" if v["score"] >= 50 else "bad")}'
                        f'<div class="muted">Likely range {round(v["low"])} to {round(v["high"])} out of 100</div>', unsafe_allow_html=True)
            st.progress(min(1.0, v["score"] / 100))
            math("validation")
    with c2:
        with st.container(border=True):
            st.subheader("Market size check"); sizing(r)
    with st.container(border=True):
        st.subheader("The idea at a glance")
        i = r["idea"]; cv = i["canvas"]
        st.markdown(f"**Neutral brief:** {i['brief']}")
        st.markdown("**Lean Canvas**" + (" " + pill("template: run with AI to fill", "warn") if i["canvas_source"] == "template" else ""), unsafe_allow_html=True)
        cells = [("Problem", "problem"), ("Customer segments", "customer_segments"), ("Unique value", "unique_value"), ("Solution", "solution"), ("Channels", "channels"),
                 ("Revenue", "revenue_streams"), ("Costs", "cost_structure"), ("Key metrics", "key_metrics"), ("Unfair advantage", "unfair_advantage")]
        for row in (cells[:5], cells[5:]):
            cs = st.columns(5)
            for col, (lab, k) in zip(cs, row):
                col.markdown(f'<div class="box" style="min-height:120px"><div class="muted" style="font-size:12px">{lab}</div>{cv.get(k) or "–"}</div>', unsafe_allow_html=True)
        a1, a2 = st.columns(2)
        a1.markdown("**Key assumptions to test**\n" + "\n".join(f"{n + 1}. {x}" for n, x in enumerate(i["assumptions"])))
        with a2:
            st.markdown("**AI judge rubric**")
            if i["rubric"]:
                for x in i["rubric"]: st.markdown(f"{x['criterion']}: **{x['score']}/5** <span class='muted'>· {x['reason']}</span>", unsafe_allow_html=True)
            else: st.caption("Run with AI agents to score problem severity, solution fit, differentiation, UAE feasibility and timing.")
    if dec.get("best") and dec["code"] in ("pivot", "test"):
        b = dec["best"]
        st.info(f"**Launch plan that works best: {b['name']}.** Payback chance {pct(f['p_payback'])} → {pct(b['p_payback'])}; chance of exceeding budget {pct(f['p_ruin'])} → {pct(b['p_ruin'])}; expected value {aed(f['npv_mean'])} → {aed(b['npv_mean'])}. {dec['feasible']} of 12 plans meet your limits.")
    c1, c2 = st.columns(2)
    seg = r["stages"]["segment"]["segments"][0]; mix = r["stages"]["optimise"]["channel_mix"]
    with c1:
        with st.container(border=True):
            st.subheader("Launch plan")
            st.markdown(f"- **Start with:** {seg['name']} ({pct(seg['value_share'])} of expected revenue)\n- **Spend per customer:** {aed(r['unit']['arpu'])} a month\n"
                        f"- **Customers to cover fixed costs:** {num(r['unit']['bep_customers'])}\n- **Typical payback:** {'month ' + str(round(f['payback_median'])) if f['payback_median'] else 'not within the horizon'}\n"
                        f"- **Cash to have ready (90% of replays):** {aed(f['cash_need_p90'])}\n- **Best channels:** {', '.join([a['channel'] for a in mix['allocation'] if a['customers'] > .5][:3])}")
    with c2:
        with st.container(border=True):
            st.subheader("Stop rules")
            st.markdown("\n".join(f"- {x}" for x in r["kill_criteria"])); math("kill")
    with st.container(border=True):
        st.subheader("Do these next")
        cs = st.columns(3)
        for col, s in zip(cs, r["next_steps"]):
            col.markdown(f'<div class="box"><div class="muted" style="font-size:12px">{s["stage"]}</div><b>{s["experiment"]}</b><div class="muted">{s["why"]}</div></div>', unsafe_allow_html=True)
    st.subheader("Six checks in plain words")
    checks = [("market", "Market"), ("customers", "Customers"), ("competition", "Competition"), ("money", "Money"), ("usability", "Ease of use"), ("evidence", "Evidence")]
    cs = st.columns(3)
    for n, (k, name) in enumerate(checks):
        s = r["scores"][k]
        with cs[n % 3]:
            with st.container(border=True):
                st.markdown(f"**{name}** {pill('Not assessed' if s is None else 'Strong' if s >= 65 else 'Uncertain' if s >= 45 else 'Weak', tone(s))}", unsafe_allow_html=True)
                st.markdown(f'<span style="font-size:28px;font-weight:700">{"–" if s is None else round(s)}</span><span class="muted"> / 100</span>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("How simulated customers reacted")
            ab = f["abm"]
            st.markdown(f'<p class="muted">{num(ab["agents"])} simulated UAE buyers, each with friends, replayed {num(f["runs"])} times. {pct(ab["wom_share"])} of customers came through friends; a competitor hit back in {pct(ab["runs_with_competitor_reaction"])} of replays.</p>', unsafe_allow_html=True)
            for j in ab["journeys"][:4]:
                st.markdown(f"{pill(j['kind'], 'good' if j['kind'] == 'stayed' else '' if j['kind'] == 'said no' else 'bad')} **{j['who']}**: {j['story']}", unsafe_allow_html=True)
    with c2:
        with st.container(border=True):
            st.subheader("Biggest risks")
            risks = list((ag.get("critic") or {}).get("pre_mortem") or []) + [f"{x['name']} looks optimistic compared with similar plans." for x in r["stages"]["anomaly"]["flags"] if x["optimistic"]]
            st.markdown("\n".join(f"{n + 1}. {x}" for n, x in enumerate(risks[:6])) if risks else "Run with AI agents for the critic's pre-mortem.")
            st.markdown("**What happened where**")
            st.markdown("\n".join(f"- {'✅' if s == 'done' else '⚠️'} **{n}**: {t}" for n, s, t in ss.get("log", [])))
    for w in r.get("warnings", []): st.warning(w)


def sizing(r, show_math=True):
    s = r["market_sizing"]
    rows = [("TAM: category spend", s["tam_synthetic"])] + ([("TAM: AI research", s["tam_ai"])] if s.get("tam_ai") else []) + [("SAM: within your reach", s["sam"])] + \
           ([("SOM: AI research", s["som_top_down"])] if s.get("som_top_down") else []) + [("SOM: simulation", s["som_bottom_up"])]
    hbars(rows, fmt=lambda v: aed(v) + "/yr", log=True)
    st.caption(s["note"] + " (log scale)")
    if show_math: math("sizing")


def tab_funnel(r, state):
    S, f = r["stages"], r["stages"]["forecast"]
    st.header("The decision funnel")
    st.markdown('<p class="muted">Each stage answers one question with the simplest algorithm that fits, checks whether the data supports it, and passes probabilities and amounts to the next stage.</p>', unsafe_allow_html=True)
    def stage(n, q, family, method, check, key):
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"#### {n}. {q}")
            with c2: math(key)
            st.markdown(f"{pill(family, 'info')} {pill(method)} {pill(check[1], check[0])} <span class='muted'>{check[2]}</span>", unsafe_allow_html=True)
            return st.container()
    with stage(1, "What does the market look like?", "Descriptive statistics", "Blinded synthetic UAE population", ("info", "Synthetic", "Never sees your idea."), "describe"):
        c = st.columns(4); d = S["describe"]
        for i, (l, v) in enumerate([("Category buyers in focus", num(d["category_buyers"])), ("Median spend today", aed(d["spend_median"])), ("High pain with today's options", pct(d["pain_high_share"])), ("Category spend per year", aed(d["tam_aed"]))]):
            c[i].metric(l, v)
        sizing(r, show_math=False)
    with stage(2, "Who is similar?", "Clustering", f"Gaussian mixture, {S['segment']['k']} groups by BIC", ("good", "Pass", "No labels needed."), "segment"):
        st.dataframe(pd.DataFrame([dict(Segment=s["name"], Share=pct(s["share"]), **{"P(buy)": pct(s["adoption"], 1)}, Spend=aed(s["arpu"]), Customers=num(s["expected_customers"]), **{"Share of value": pct(s["value_share"])}) for s in S["segment"]["segments"]]), hide_index=True, width="stretch")
    with stage(3, "Is anything unusual in the plan?", "Anomaly detection", "Isolation Forest vs 3,000 comparable plans", ("good", "Pass", ""), "anomaly"):
        st.dataframe(pd.DataFrame([dict(Assumption=a["name"], Yours=round(a["value"], 2), Typical=round(a["typical"], 2), Percentile=pct(a["percentile"]), Flag="Optimistic" if a["optimistic"] else "Unusual" if a["unusual"] else "") for a in S["anomaly"]["per_assumption"]]), hide_index=True, width="stretch")
    cal = S["classify"]["calibrated"]
    with stage(4, "Will they buy?", "Classification", "Logistic choice model", ("good", "Calibrated", "Fitted to your results.") if cal else ("warn", "Rule", "Starting coefficients until a landing-page test."), "classify"):
        c = st.columns(4)
        for i, (l, v) in enumerate([("Average P(buy) once aware", pct(S["classify"]["mean_adoption"], 1)), ("Buyers if everyone knew", num(S["classify"]["potential"]["adopters_if_aware"])), ("Reach of one business", pct(S["classify"]["potential"]["catchment"])), ("Market potential used", num(S["classify"]["potential_used"]))]):
            c[i].metric(l, v)
    with stage(5, "How much will they spend?", "Regression (hurdle)", "Weighted linear regression", ("warn", "Rule", "Pricing tests calibrate it."), "regress"):
        st.metric("Expected spend per customer per month", aed(S["regress"]["expected_arpu"]), help=f"Planned price {aed(S['regress']['planned_price'])}")
    with stage(6, "How long do customers stay, and when do you pay back?", "Survival analysis", "Exponential lifetimes; Kaplan-Meier", ("warn", "Rule", "A pilot measures churn."), "survival"):
        c1, c2 = st.columns(2)
        with c1:
            fig = go.Figure(go.Scatter(x=list(range(1, len(S["survival"]["payback_curve"]) + 1)), y=S["survival"]["payback_curve"], line=dict(color=LINE, width=2.5)))
            fig.add_hline(y=r["limits"]["min_payback"], line=dict(color=ZERO, dash="dash")); fig.update_layout(**{**PLOT, "height": 240}, yaxis=dict(tickformat=".0%", gridcolor="#f1f2f7"), xaxis_title="Month")
            st.caption("Chance of having paid back, by month"); chart(fig)
        c2.dataframe(pd.DataFrame([dict(Segment=x["segment"], **{"Median months": round(x["median_months"], 1), "Monthly churn": pct(x["monthly_hazard"], 1)}) for x in S["survival"]["customers"]]), hide_index=True, width="stretch")
    with stage(7, "How many customers in future?", "Simulation", f"Agent-based model: {num(f['abm']['agents'])} customers, {num(f['runs'])} replays", ("good", "Pass", ""), "forecast"):
        ab = f["abm"]; c = st.columns(4)
        for i, (l, v) in enumerate([("Customers won through friends", pct(ab["wom_share"])), ("Replays with a competitor reaction", pct(ab["runs_with_competitor_reaction"])), ("Leavers who left unhappy", pct(ab["unhappy_left_share"])), ("Buyers turned away (full)", num(ab["turned_away"]))]):
            c[i].metric(l, v)
        c1, c2 = st.columns(2)
        with c1:
            b = f["bands"]; last = lambda k: b[k]["p50"][-1]
            still, left, no, un = last("customers"), last("left"), last("said_no"), last("unaware")
            st.caption(f"Customer funnel after {f['horizon']} months")
            hbars([("Within reach", un + no + still + left), ("Heard about you", no + still + left), ("Bought at least once", still + left), ("Still customers", still)], fmt=lambda v: num(v))
        with c2: st.caption("Cash over time (AED)"); fan(f["bands"]["cash"], money=True, height=260)
        st.markdown("**Customer stories from one replay**")
        for j in ab["journeys"]: st.markdown(f"{pill(j['kind'], 'good' if j['kind'] == 'stayed' else '' if j['kind'] == 'said no' else 'bad')} **{j['who']}**: {j['story']}", unsafe_allow_html=True)
    with stage(8, "What are customers talking about?", "Text analysis", "TF-IDF + k-means", ("good", "Pass", f"{S['text']['n_docs']} texts") if S["text"]["status"] == "ran" else ("", "Skipped", S["text"].get("reason", "")), "text"):
        if S["text"]["status"] == "ran":
            st.dataframe(pd.DataFrame([dict(Topic=", ".join(t["terms"][:4]), Share=pct(t["share"]), Negative=pct(t["negative_share"]), Match=round(t["idea_match"], 2), Example=t["example"]) for t in S["text"]["topics"]]), hide_index=True, width="stretch")
    with stage(9, "Does our action change it?", "A/B test, uplift", "Bayesian Beta-binomial, power analysis", ("good", "Pass", f"{len(state.get('experiments', []))} experiments") if state.get("experiments") else ("", "Waiting", "No experiments yet."), "experiments"):
        c = st.columns(2); c[0].metric("Predicted sign-up rate", pct(S["experiments"]["predicted_conversion"], 1)); c[1].metric("Visitors needed per version", num(S["experiments"]["sample_size_landing"]))
    with stage(10, "What is the best allocation?", "Optimisation", "Linear programme + 12 launch plans", ("good", "Pass", ""), "optimise"):
        mix = S["optimise"]["channel_mix"]
        st.dataframe(pd.DataFrame([dict(Channel=a["channel"], Spend=aed(a["spend"]), Customers=num(a["customers"]), **{"Cost each": aed(a["cac"]) if a["cac"] else "–"}) for a in mix["allocation"]]), hide_index=True, width="stretch")
        lim = r["limits"]
        st.dataframe(pd.DataFrame([dict(Plan=o["name"], **{"Payback chance": pct(o["p_payback"]), "Exceeds budget": pct(o["p_ruin"]), "Expected NPV": aed(o["npv_mean"]), "Meets limits": "Yes" if o["p_payback"] >= lim["min_payback"] and o["p_ruin"] <= lim["max_ruin"] and o["npv_mean"] > 0 else "No"}) for o in S["optimise"]["options"]]), hide_index=True, width="stretch")
    with st.container(border=True):
        c1, c2 = st.columns([5, 1]); c1.markdown("#### Where the funnel leaks")
        with c2: math("leak")
        hbars([(x["name"], x["variance_share"]) for x in r["leak"]["rows"][:8]])


def tab_value(r, state):
    v = r["value"]; u = v["usability"]; h = v["wtp_hist"]
    st.header("Customer value"); st.markdown('<p class="muted">Is it worth paying for, and is it easy to get value?</p>', unsafe_allow_html=True)
    c = st.columns(4)
    kpi(c[0], 0, "Value gap score", f"{round(v['value_gap_score'])}/100", f"Likely buyers would pay {v['value_ratio']:.2f}× your price", "value")
    kpi(c[1], 1, "Pain among likely buyers", pct(v["pain_adopters"]), "Unhappiness with today's options")
    kpi(c[2], 2, "Simulated buyers who accept your price", pct(h["share_above_price"]), f"at {aed(h['price'])} a month")
    kpi(c[3], 3, "Ease-of-use score", "–" if u["score"] is None else f"{round(u['score'])}/100", "Measured" if u.get("measured") else "AI review" if u["score"] is not None else "Not assessed yet")
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("Willingness to pay vs your price")
            mids = [(h["edges"][i] + h["edges"][i + 1]) / 2 for i in range(len(h["counts"]))]
            fig = go.Figure(go.Bar(x=mids, y=h["counts"], marker=dict(color=["#aab3f2" if m >= h["price"] else "#e4e7fb" for m in mids])))
            fig.add_vline(x=h["price"], line=dict(color=ZERO, dash="dash")); fig.update_layout(**{**PLOT, "height": 260}, yaxis=dict(visible=False), xaxis_title="AED per month")
            chart(fig)
    with c2:
        with st.container(border=True):
            st.subheader("Jobs to be done")
            st.markdown("\n".join(f"- *{j['type']}*: {j['job']}" for j in v["jtbd"]) if v["jtbd"] else "Run with AI agents to describe functional, emotional and social jobs.")
            st.markdown("**Pains found**")
            st.markdown("\n".join(f"- {p['pain']} ({round(p['intensity'])}/100)" for p in v["pains"]) if v["pains"] else "Not researched yet.")
    with st.container(border=True):
        st.subheader("Value Proposition Canvas")
        cv = v["canvas"]
        if any(cv.get(k) for k in cv):
            c1, c2 = st.columns(2)
            c1.markdown("**Customer profile**\n\n" + "\n\n".join(f"*{n}*\n" + "\n".join(f"- {x}" for x in cv.get(k, [])) for n, k in [("Jobs", "jobs"), ("Pains", "pains"), ("Gains", "gains")]))
            c2.markdown("**Value map (your offer)**\n\n" + "\n\n".join(f"*{n}*\n" + "\n".join(f"- {x}" for x in cv.get(k, [])) for n, k in [("Products and services", "products"), ("Pain relievers", "pain_relievers"), ("Gain creators", "gain_creators")]))
        else: st.caption("Run with AI agents to fill the canvas from real customer research.")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("Kano features")
            if v["kano"]: st.dataframe(pd.DataFrame(v["kano"]).rename(columns={"feature": "Feature", "category": "Type"}), hide_index=True, width="stretch")
            else: st.caption("Run with AI agents to classify features.")
    with c2:
        with st.container(border=True):
            st.subheader("Ease of use")
            if u.get("measured"): st.markdown(f"Measured: {u['measured']['users']} users, {pct(u['measured']['success'])} task success" + (f", SUS {u['measured']['sus']:.1f} ({u['measured']['sus_grade']})" if u['measured']['sus'] is not None else ""))
            if u.get("journey"): st.markdown("\n".join(f"{n + 1}. **{s['step']}** {s.get('note') or ''}" for n, s in enumerate(u["journey"])))
            for x in u.get("issues") or []: st.markdown(f"{pill(['', 'Minor', 'Major', 'Critical'][x['severity']], 'bad' if x['severity'] >= 3 else 'warn' if x['severity'] == 2 else '')} {x['issue']} ({x['heuristic']})", unsafe_allow_html=True)
            if not u.get("journey") and not u.get("measured"): st.caption("Run with AI agents, or enter a usability test on the Experiments tab.")


def tab_competition(r, state):
    c, f = r["competition"], r["stages"]["forecast"]
    st.header("Competition: who already does this?")
    src = {"typical": pill("Typical competitor types", "warn"), "yours": pill("Competitors you added", "good"), "ai": pill("Found by AI web research", "info"),
           "yours+ai": pill("Yours + found by AI", "info")}[c["source"]]
    st.markdown(f'{src} <span class="muted">{c["headline"]}</span>', unsafe_allow_html=True)
    named = [x for x in c["competitors"] if x["source"] != "typical"]
    top = c["competitors"][0] if c["competitors"] else None
    k = st.columns(4)
    kpi(k[0], 0, "Named competitors", str(len(named)), f"{sum(x['type'] == 'direct' for x in named)} direct" if named else "Add the ones you know below")
    kpi(k[1], 1, "Closest rival", f"{round(top['similarity'] * 100)}% similar" if top else "–", top["name"] if top else "")
    pb = c["price"]
    kpi(k[2], 2, "Your price position", pb["position"].capitalize() if pb else "–", (f"You {aed(pb['yours'])} · rivals {aed(pb['low'])} to {aed(pb['high'])}" if pb['n'] > 1 else f"You {aed(pb['yours'])} · rival {aed(pb['low'])}") if pb else "Add rival prices to compare")
    kpi(k[3], 3, "Competition score", f"{round(r['scores']['competition'])}/100", f"Rivalry {c['rivalry']:.1f}/5 · differentiation {round(c['differentiation'])}", "competition")
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("Positioning map")
            fig = go.Figure()
            pts = [x for x in c["competitors"] if x["price_aed"]]
            cols = {"direct": "#e3a3a8", "indirect": "#f0c27a", "substitute": "#c9cff7"}
            for t in ("direct", "indirect", "substitute"):
                g = [x for x in pts if x["type"] == t]
                if g:
                    fig.add_trace(go.Scatter(x=[x["price_aed"] for x in g], y=[x["similarity"] * 100 for x in g], mode="markers+text", name=t.capitalize(),
                                             text=[x["name"][:22] for x in g], textposition="top center", textfont=dict(size=11),
                                             marker=dict(size=[12 + x["threat"] / 4 for x in g], color=cols[t], line=dict(color="#fff", width=1))))
            fig.add_trace(go.Scatter(x=[r["assumptions"]["price"]["likely"]], y=[100], mode="markers+text", name="You", text=["You"], textposition="bottom center",
                                     marker=dict(size=20, color=LINE, symbol="star")))
            xs = [x["price_aed"] for x in pts] + [r["assumptions"]["price"]["likely"]]
            fig.update_layout(**{**PLOT, "height": 330}, xaxis=dict(title="Price per customer per month (AED)", range=[min(xs) * .6, max(xs) * 1.35]), yaxis=dict(title="Similarity to your idea (%)", range=[-5, 115], gridcolor="#f1f2f7"),
                              legend=dict(orientation="h", y=-0.25))
            chart(fig)
            st.caption("Bigger bubble = bigger threat. Rivals near the star sell something similar at a similar price.")
    with c2:
        with st.container(border=True):
            st.subheader("Threat ranking")
            hbars([(x["name"][:30], x["threat"]) for x in c["competitors"][:8]], fmt=lambda v: f"{v:.0f}/100", color="#e8c3c7", xmax=100)
            math("competition")
    with st.container(border=True):
        st.subheader("Feature comparison")
        mine = st.multiselect("What your idea offers (edit if wrong)", c["criteria"], default=c["yours"], key="your_feats")
        if sorted(mine) != sorted(c["yours"]) and st.button("Update my features"):
            recompute(lambda s: s.__setitem__("your_features", mine), "Your features were updated.")
        rows = [{"Feature": k, "You": "✓" if k in c["yours"] else "", **{x["name"][:24]: "✓" if k in x["features"] else "" for x in c["competitors"][:7]}} for k in c["criteria"]]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        a1, a2 = st.columns(2)
        a1.markdown("**Your edge (few rivals offer it)**\n" + ("\n".join(f"- {x}" for x in c["white_space"]) or "- None found yet: what would make you different?"))
        a2.markdown("**Table stakes you are missing (most rivals offer it)**\n" + ("\n".join(f"- {x}" for x in c["table_stakes"]) or "- None: you cover what most rivals offer."))
    st.subheader("Competitor profiles")
    for x in c["competitors"]:
        with st.container(border=True):
            h1, h2 = st.columns([5, 1])
            tag = {"yours": pill("Added by you", "good"), "ai": pill("Web source", "info"), "typical": pill("Typical type", "warn")}[x["source"]]
            link = f' · <a href="{x["url"]}" target="_blank">website</a>' if x["url"].startswith("http") else ""
            h1.markdown(f"**{x['name']}** {pill(x['type'])} {tag}<span class='muted'>{(' · ' + x['location']) if x['location'] else ''}{link}</span>", unsafe_allow_html=True)
            h2.markdown(f"<div style='text-align:right'>{pill('Threat ' + str(round(x['threat'])), 'bad' if x['threat'] >= 55 else 'warn' if x['threat'] >= 30 else '')}</div>", unsafe_allow_html=True)
            st.markdown(f"<span class='muted'>{x['note']}</span>", unsafe_allow_html=True)
            m = st.columns(4)
            m[0].markdown(f"<span class='muted'>Price</span><br>{aed(x['price_aed']) + '/month' if x['price_aed'] else (x['price_text'] or '–')}", unsafe_allow_html=True)
            m[1].markdown(f"<span class='muted'>Rating</span><br>{x['rating']:.1f} / 5" if x["rating"] else "<span class='muted'>Rating</span><br>–", unsafe_allow_html=True)
            m[2].markdown(f"<span class='muted'>Similar to you</span><br>{round(x['similarity'] * 100)}%", unsafe_allow_html=True)
            m[3].markdown(f"<span class='muted'>Price closeness</span><br>{round(x['price_closeness'] * 100)}%", unsafe_allow_html=True)
            if x["strengths"] or x["weaknesses"]:
                s1, s2 = st.columns(2)
                s1.markdown("**Strengths**\n" + "\n".join(f"- {y}" for y in x["strengths"]))
                s2.markdown("**Weaknesses (your opening)**\n" + "\n".join(f"- {y}" for y in x["weaknesses"]))
            if x["source"] == "yours":
                idx = next((i for i, y in enumerate(state.get("competitors") or []) if y["name"] == x["name"]), None)
                if idx is not None and st.button("Remove", key=f"rmc{idx}"):
                    recompute(lambda s, i=idx: s["competitors"].pop(i), f"Removed {x['name']}.")
    with st.container(border=True):
        st.subheader("Add a competitor you know")
        with st.form("addcomp", clear_on_submit=True):
            a = st.columns([2, 1, 1, 1])
            nm = a[0].text_input("Name"); ty = a[1].selectbox("Type", ["direct", "indirect", "substitute"], help="Direct: same offer, same customers. Indirect: different offer, same need. Substitute: what people do instead.")
            pr = a[2].number_input("Price / customer / month (AED)", 0.0); rt = a[3].number_input("Rating (0-5, optional)", 0.0, 5.0, 0.0, .1)
            ds = st.text_input("What they offer, in a sentence")
            b = st.columns(2)
            fe = b[0].multiselect("Features they offer", c["criteria"]); ur = b[1].text_input("Website (optional)")
            b = st.columns(2)
            sg = b[0].text_input("Strengths (comma-separated)"); wk = b[1].text_input("Weaknesses (comma-separated)")
            if st.form_submit_button("Add competitor", type="primary"):
                if len(nm.strip()) < 2: st.error("Enter the competitor's name.")
                else:
                    e = dict(name=nm.strip()[:120], type=ty, price_aed=pr or None, rating=rt or None, note=ds[:240], features=fe, url=ur.strip()[:300] if ur.strip().startswith("http") else "",
                             strengths=[y.strip() for y in sg.split(",") if y.strip()][:3], weaknesses=[y.strip() for y in wk.split(",") if y.strip()][:3])
                    recompute(lambda s: s.setdefault("competitors", []).append(e), f"Added {e['name']}. Everything was recalculated.")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("Five forces")
            fo = c["forces"]
            if fo:
                names = dict(rivalry="Rivalry", new_entrants="New entrants", substitutes="Substitutes", buyer_power="Buyer power", supplier_power="Supplier power")
                hbars([(names[k], v) for k, v in fo.items() if k in names], fmt=lambda v: f"{v:.1f}/5", color="#c9cff7", xmax=5)
                st.caption("1 = weak pressure, 5 = strong. Rivalry blends the AI's score with the competitors you named." if c["derived_rivalry"] and len(fo) > 1 else "Rivalry comes from the competitors named here; the AI scores all five forces.")
            else: st.caption("Name competitors or run with AI agents to score the forces.")
    with c2:
        with st.container(border=True):
            st.subheader("In the simulation")
            ab = f["abm"]
            cp = pct(.15 * min(1.7, max(.4, c['rivalry'] / 3)))
            if ab["runs_with_competitor_reaction"] > 0:
                st.markdown(f"A local competitor hit back (price cuts and promotions) in **{pct(ab['runs_with_competitor_reaction'])}** of the {num(f['runs'])} market replays, "
                            f"about {ab['competitor_reactions']:.1f} times per replay. Each reaction cuts your new customers by 20% and raises your cost per customer by 25% for 4 months.")
            else:
                st.markdown(f"No competitor hit back in the {num(f['runs'])} market replays: rivals react once you take about 3% of the buyers within reach, and this plan stays below that. "
                            f"If you grow past it, a rival reacts with a {cp} chance each month.")
            st.caption(f"Rivalry {c['rivalry']:.1f}/5 sets that monthly chance ({cp}).")
            if c["gaps"]: st.markdown("**Gaps rivals leave open**\n" + "\n".join(f"- {g}" for g in c["gaps"]))
            if c["moats"]: st.markdown("**What could protect you**\n" + "\n".join(f"- {g}" for g in c["moats"]))


def tab_improve(r, state):
    im = r["improve"]
    st.header("Improve my idea")
    st.markdown('<p class="muted">Each change is replayed in the agent-based market with the same random events as your plan. The best are combined in pairs (one generation of a genetic algorithm).</p>', unsafe_allow_html=True)
    math("improve")
    if state.get("applied"):
        st.markdown("**Applied to your plan**")
        for a in state["applied"]:
            if st.button(f"Remove: {a['name']}", key=f"rm-{a['id']}"):
                recompute(lambda s, i=a["id"]: s.__setitem__("applied", [x for x in s.get("applied", []) if x["id"] != i]), f"Removed “{a['name']}”.")
    st.caption(f"Current plan: {pct(im['base']['p_payback'])} payback chance, expected value {aed(im['base']['npv_mean'])}")
    for v in im["variants"]:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([4, 1.3, 1.3, 1])
            tag = (pill("AI pivot", "info") if v.get("ai") else "") + (pill("Recombined", "good") if v.get("combo") else "")
            ch = ", ".join(f"{k} {x:+.0f}{' pts' if k in ('var_pct', 'satisfaction') else '%'}" for k, x in v["changes"].items())
            c1.markdown(f"**{v['name']}** {tag}<div class='muted'>{v['what']} · {ch}</div>", unsafe_allow_html=True)
            d = v["d_payback"] * 100
            c2.markdown(f'<div class="muted" style="font-size:12.5px">Payback chance</div><div style="font-size:22px;font-weight:700">{pct(v["p_payback"])}</div>{pill(f"{d:+.0f} pts", "good" if d > .5 else "bad" if d < -.5 else "")}', unsafe_allow_html=True)
            c3.markdown(f'<div class="muted" style="font-size:12.5px">Expected value</div><div style="font-size:22px;font-weight:700">{aed(v["npv_mean"])}</div>', unsafe_allow_html=True)
            if c4.button("Apply", key=f"ap-{v['id']}"):
                recompute(lambda s, v=v: s.setdefault("applied", []).append(dict(id=v["id"], name=v["name"], changes=v["changes"])), f"Applied “{v['name']}”.")


def tab_lab(r, state):
    A = r["assumptions"]
    st.header("What-if lab")
    st.markdown('<p class="muted">Change the inputs and replay the whole market. The band runs from a bad case to a good case.</p>', unsafe_allow_html=True)
    with st.form("lab_form"):
        c1, c2 = st.columns(2)
        vals = {}
        for i, (k, lab) in enumerate([("price", "Spend per customer per month (AED)"), ("cac", "Cost to win one customer (AED)"), ("fixed", "Fixed costs per month (AED)"), ("setup", "Setup cost (AED)"), ("churn", "Monthly churn (%)")]):
            lo, hi = A[k]["likely"] * .3, A[k]["likely"] * 2.5
            vals[k] = (c1 if i % 2 == 0 else c2).slider(lab, float(round(lo, 2)), float(round(hi, 2)), float(round(A[k]["likely"], 2)))
        sat = c2.slider("Customer satisfaction", .05, .97, float(round(r["unit"]["satisfaction"], 2)))
        shocks = c1.select_slider("Random shocks", [0, 1, 2, 3], value=r["settings"]["shocks"], format_func=lambda x: ["None", "Low", "Medium", "High"][x])
        cyc = c1.checkbox("Economic cycles", value=r["settings"]["cycles"]); sea = c2.checkbox("UAE seasons (summer, Ramadan)", value=r["settings"]["seasonality"])
        ran = st.form_submit_button("Run the simulation", type="primary")
    ov = {k: dict(min=A[k]["min"] * vals[k] / A[k]["likely"], likely=vals[k], max=A[k]["max"] * vals[k] / A[k]["likely"], label="founder", source="Set in the What-if lab") for k in vals if abs(vals[k] - A[k]["likely"]) > 1e-6}
    sett = dict(shocks=shocks, cycles=cyc, seasonality=sea, satisfaction=sat if abs(sat - r["unit"]["satisfaction"]) > 1e-6 else None)
    if ran:
        with st.spinner("Replaying the market…"): ss.lab_out = what_if(state, ov, sett)
    out = ss.get("lab_out")
    f = out["forecast"] if out else r["stages"]["forecast"]
    c = st.columns(4)
    kpi(c[0], 0, "Payback chance", pct(f["p_payback"]), f"Need {pct(r['limits']['min_payback'])}")
    kpi(c[1], 1, "Exceeds budget", pct(f["p_ruin"]), f"Limit {pct(r['limits']['max_ruin'])}")
    kpi(c[2], 2, "Expected NPV", aed(f["npv_mean"]))
    kpi(c[3], 3, "Typical payback", f"Month {round(f['payback_median'])}" if f["payback_median"] else "Beyond horizon")
    c1, c2 = st.columns(2)
    with c1: st.caption("Cash over time (AED)"); fan(f["bands"]["cash"], money=True)
    with c2: st.caption("Active customers"); fan(f["bands"]["customers"])
    if out and st.button("Use these settings in the report"):
        recompute(lambda s: (s.__setitem__("overrides", {**s.get("overrides", {}), **ov}), s.__setitem__("settings", {**s.get("settings", {}), **sett})), "The report now uses the what-if settings.")


def tab_experiments(r, state):
    ev = r["stages"]["experiments"]["evidence"]; k = r["kit"]
    st.header("Experiments: replace guesses with evidence")
    st.markdown('<p class="muted">Run a cheap real test, enter what happened, and the whole funnel recalibrates with Bayesian updating.</p>', unsafe_allow_html=True)
    with st.expander("Experiment kit: landing page, ads, interview script, survey", expanded=False):
        st.markdown("\n".join(f"{n + 1}. {p}" for n, p in enumerate(k["plan"])))
        c1, c2 = st.columns(2)
        c1.markdown(f"**Landing page**\n\n### {k['landing']['headline']}\n{k['landing']['subheadline']}\n\n" + "\n".join(f"- {b}" for b in k["landing"]["bullets"]) + f"\n\n**[{k['landing']['cta']}]**")
        c2.markdown("**Ads for an A/B test**\n\n" + "\n\n".join(f"*{a['label']}*: {a['text']}" for a in k["ads"]))
        c1.markdown("**Interview script**\n" + "\n".join(f"{n + 1}. {q}" for n, q in enumerate(k["interview"])))
        c2.markdown("**Survey (first 4 = Van Westendorp)**\n" + "\n".join(f"{n + 1}. {q}" for n, q in enumerate(k["survey"])))
    def add(e, label):
        recompute(lambda s: s.setdefault("experiments", []).append(e), f"Added: {label}.")
    t = st.tabs(["Landing page", "Pricing", "Van Westendorp", "Interviews", "Pilot + NPS", "Usability (SUS)", "A/B test", "Real sales"])
    with t[0], st.form("landing"):
        c = st.columns(4); vi = c[0].number_input("Visitors", 0); si = c[1].number_input("Sign-ups", 0); sp = c[2].number_input("Ad spend (AED)", 0.0); pr = c[3].number_input("Sign-ups expected to pay (%)", 1, 100, 30)
        if st.form_submit_button("Add result"):
            if vi <= 0 or sp <= 0 or si > vi: st.error("Visitors and spend must be above zero, and sign-ups cannot exceed visitors.")
            else: add(dict(kind="landing", visitors=int(vi), signups=int(si), spend=float(sp), pay_rate=float(pr)), "landing-page test")
    with t[1], st.form("pricing"):
        c = st.columns(3); p1 = c[0].number_input("Price A (AED)", 0.0, value=float(round(r["assumptions"]["price"]["likely"]))); n1 = c[1].number_input("Asked at A", 0); k1 = c[2].number_input("Accepted A", 0)
        p2 = c[0].number_input("Price B (AED, optional)", 0.0); n2 = c[1].number_input("Asked at B", 0); k2 = c[2].number_input("Accepted B", 0)
        if st.form_submit_button("Add result"):
            pts = [dict(price=p, n=int(n), k=int(kk)) for p, n, kk in ((p1, n1, k1), (p2, n2, k2)) if p > 0 and n > 0]
            if not pts or any(x["k"] > x["n"] for x in pts): st.error("Enter at least one price with people asked; accepted cannot exceed asked.")
            else: add(dict(kind="pricing", points=pts), "pricing test")
    with t[2], st.form("vw"):
        txt = st.text_area("One respondent per line: too cheap, cheap, expensive, too expensive (AED a month). At least 5 lines.", placeholder="60, 100, 160, 220\n80, 120, 180, 250")
        if st.form_submit_button("Add result"):
            try:
                rows = [[float(x) for x in line.replace(";", ",").split(",")] for line in txt.strip().splitlines() if line.strip()]
                assert len(rows) >= 5 and all(len(x) == 4 and 0 < x[0] <= x[1] <= x[2] <= x[3] for x in rows)
                add(dict(kind="vanwestendorp", rows=rows), "Van Westendorp survey")
            except Exception:
                st.error("Each line needs four prices in order (too cheap ≤ cheap ≤ expensive ≤ too expensive), at least 5 lines.")
    with t[3], st.form("int"):
        c = st.columns(2); n = c[0].number_input("People interviewed", 0); kk = c[1].number_input("Described strong pain", 0)
        if st.form_submit_button("Add result"):
            if n <= 0 or kk > n: st.error("Interview at least one person; strong-pain answers cannot exceed the number interviewed.")
            else: add(dict(kind="interviews", n=int(n), k=int(kk)), "interviews")
    with t[4], st.form("pilot"):
        c = st.columns(3); cu = c[0].number_input("Paying customers", 0); mo = c[1].number_input("Months", 0.0); lo = c[2].number_input("Customers who left", 0)
        pm = c[0].number_input("Promoters (9-10)", 0); pa = c[1].number_input("Passives (7-8)", 0); de = c[2].number_input("Detractors (0-6)", 0)
        if st.form_submit_button("Add result"):
            if cu <= 0 or mo <= 0 or lo > cu * mo: st.error("Enter customers and months above zero.")
            else:
                e = dict(kind="pilot", customers=int(cu), months=float(mo), lost=int(lo))
                if pm + pa + de > 0: e.update(promoters=int(pm), passives=int(pa), detractors=int(de))
                add(e, "pilot")
    with t[5]:
        with st.form("usab"):
            c = st.columns(3); us = c[0].number_input("Users tested", 1, value=5); td = c[1].number_input("Tasks completed", 0); tt = c[2].number_input("Tasks attempted", 0)
            sus = st.text_input("SUS scores, 0-100, comma-separated", placeholder="72.5, 80, 65")
            if st.form_submit_button("Add result"):
                try:
                    sv = [float(x) for x in sus.replace(";", ",").split(",") if x.strip()]
                    assert tt > 0 and td <= tt and all(0 <= x <= 100 for x in sv)
                    add(dict(kind="usability", users=int(us), tasks_done=int(td), tasks_total=int(tt), sus=sv), "usability test")
                except Exception:
                    st.error("Tasks attempted must be above zero and at least the tasks completed; SUS scores are 0 to 100.")
        with st.expander("SUS calculator: score one tester's 10 answers"):
            ans = [st.select_slider(f"{i + 1}. {q}", [1, 2, 3, 4, 5], 3, key=f"sus{i}") for i, q in enumerate(SUS_QUESTIONS)]
            st.markdown(f"**SUS score: {sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(ans)) * 2.5:.1f}**")
    with t[6], st.form("ab"):
        c = st.columns(4); na = c[0].number_input("A: visitors", 0); ka = c[1].number_input("A: conversions", 0); nb = c[2].number_input("B: visitors", 0); kb = c[3].number_input("B: conversions", 0)
        if st.form_submit_button("Add result"):
            if na <= 0 or nb <= 0 or ka > na or kb > nb: st.error("Visitors must be above zero and conversions cannot exceed visitors.")
            else: add(dict(kind="ab", name="A/B test", nA=int(na), kA=int(ka), nB=int(nb), kB=int(kb)), "A/B test")
    with t[7], st.form("sales"):
        txt = st.text_input("Monthly revenue in AED, oldest first (at least 4 months)", placeholder="12000, 15000, 17500, 21000")
        if st.form_submit_button("Add result"):
            try:
                sv = [float(x) for x in txt.replace(";", ",").split(",") if x.strip()]; assert len(sv) >= 4 and min(sv) >= 0
                add(dict(kind="sales", sales=sv), "sales data")
            except Exception:
                st.error("Enter at least 4 months of sales, none negative.")
    st.subheader("Results so far")
    if not state.get("experiments"): st.caption("No results yet: every number is still an estimate.")
    for i, e in enumerate(state.get("experiments", [])):
        c1, c2 = st.columns([6, 1])
        c1.markdown(f"{pill('Measured', 'good')} {e['kind']}: " + ", ".join(f"{a}={b}" for a, b in e.items() if a not in ('kind', 'rows', 'points', 'sales', 'sus'))[:160], unsafe_allow_html=True)
        if c2.button("Remove", key=f"rmx{i}"):
            recompute(lambda s, i=i: s["experiments"].pop(i), "Result removed.")
    if ev.get("vw"):
        with st.container(border=True):
            st.subheader("Van Westendorp price range"); vw = ev["vw"]; c = st.columns(4)
            for j, (l, x) in enumerate([("Lowest acceptable", vw["pmc"]), ("Optimal price", vw["opp"]), ("Indifference price", vw["ipp"]), ("Highest acceptable", vw["pme"])]): c[j].metric(l, aed(x))
            fig = go.Figure()
            for key, name, col in [("too_cheap", "Too cheap", "#c9cff7"), ("cheap", "Cheap", LINE), ("expensive", "Expensive", "#f0c27a"), ("too_expensive", "Too expensive", "#e3a3a8")]:
                fig.add_trace(go.Scatter(x=vw["curves"]["price"], y=vw["curves"][key], name=name, line=dict(color=col, width=2)))
            fig.update_layout(**{**PLOT, "height": 260}, yaxis=dict(tickformat=".0%")); chart(fig)
    if ev.get("sales"):
        with st.container(border=True):
            s = ev["sales"]; h = len(s["history"]); x1 = [f"M{i + 1}" for i in range(h)]; x2 = [f"M{h + i + 1}" for i in range(len(s["forecast"]))]
            fig = go.Figure([go.Scatter(x=x2 + x2[::-1], y=s["high"] + s["low"][::-1], fill="toself", fillcolor=BAND, line=dict(width=0), showlegend=False),
                             go.Scatter(x=x1, y=s["history"], name="Actual", line=dict(color="#2b3047", width=2.5)), go.Scatter(x=x2, y=s["forecast"], name="Forecast", line=dict(color=LINE, width=2.5, dash="dash"))])
            fig.update_layout(**{**PLOT, "height": 260}); st.subheader("Sales forecast (Holt)"); chart(fig)
    if ev.get("nps"): st.info(f"NPS {round(ev['nps']['nps'])} from {ev['nps']['n']} pilot customers; satisfaction in the simulation is now {pct(ev['nps']['satisfaction'])}.")
    for a in ev.get("ab", []): st.info(f"A/B test: {pct(a['p_b_better'])} chance B beats A; lift {pct(a['lift_mean'])}.")


def tab_audit(r, state):
    a, f = r["audit"], r["stages"]["forecast"]
    st.header("Audit: can you trust this?")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("The simulated market never saw your idea")
            st.write(a["synthetic"]["note"]); st.markdown(f"Fingerprint `{a['synthetic']['fingerprint']}` · population check {'passed' if a['synthetic']['check']['passed'] else 'failed'} (largest gap {pct(a['synthetic']['check']['max_gap'], 1)})")
        with st.container(border=True):
            st.subheader("How much rests on claims?")
            cd = a.get("claims_dependence")
            st.write(f"Without any AI or founder numbers the payback chance would be {pct(cd['p_payback_without_claims'])} (claims add {cd['change'] * 100:+.0f} points)." if cd else "No claims were added: nothing to remove.")
    with c2:
        with st.container(border=True):
            st.subheader("Compared with an average business")
            br = a.get("base_rate")
            st.write(f"An average plan of this type here: {pct(br['p_payback'])} payback chance. Yours: {pct(f['p_payback'])}." if br else "Your analysis already uses category priors only.")
        with st.container(border=True):
            st.subheader("Under heavy shocks")
            st.write(f"With shocks on High: {pct(a['stress']['p_payback'])} payback chance and {pct(a['stress']['p_ruin'])} chance of exceeding the budget.")
    with st.container(border=True):
        st.subheader("Concentration and optimism")
        st.write(f"{pct(a['concentration']['top_share'])} of expected revenue comes from one segment ({a['concentration']['top_segment']}). {a['optimism_flags']} assumption(s) flagged as optimistic.")


def tab_sources(r, state):
    A, ag = r["assumptions"], state.get("agents", {})
    st.header("Assumptions and sources")
    keys = ["price", "var_pct", "fixed", "setup", "cac", "churn", "capacity", "p", "q"]
    df = pd.DataFrame([dict(key=k, Assumption=A[k]["name"], Now=LABEL[A[k]["label"]], Low=A[k]["min"], Likely=A[k]["likely"], High=A[k]["max"],
                            Label=A[k]["label"] if A[k]["label"] in ("founder", "benchmarked", "measured") else "founder", Source=A[k]["source"]) for k in keys])
    ed = st.data_editor(df, hide_index=True, width="stretch", disabled=["key", "Assumption", "Now"], column_config={"key": None, "Label": st.column_config.SelectboxColumn(options=["founder", "benchmarked", "measured"])})
    c1, c2 = st.columns([1, 5])
    if c1.button("Recalculate", type="primary"):
        ov = {}
        for _, row in ed.iterrows():
            o = df[df.key == row.key].iloc[0]
            if any(abs(row[c] - o[c]) > 1e-9 for c in ("Low", "Likely", "High")) or row.Label != o.Label or row.Source != o.Source:
                if not (0 <= row.Low <= row.Likely <= row.High): st.error(f"{row.Assumption}: low ≤ likely ≤ high."); return
                ov[row.key] = dict(min=float(row.Low), likely=float(row.Likely), max=float(row.High), label=row.Label, source=str(row.Source)[:200])
        if ov: recompute(lambda s: s.__setitem__("overrides", {**s.get("overrides", {}), **ov}), "Recalculated with your edits.")
        else: st.info("Change a value first.")
    if c2.button("Undo all edits"):
        recompute(lambda s: (s.__setitem__("overrides", {}), s.__setitem__("settings", {})), "All edits undone.")
    if r.get("consistency"):
        st.subheader("Self-consistency check")
        st.dataframe(pd.DataFrame([dict(Input=c["name"], **{"Estimate 1": round(c["first"], 1), "Estimate 2": round(c["second"], 1), "Gap": f"{c['ratio']:.2f}×", "Result": "Range widened" if c["widened"] else "Consistent"}) for c in r["consistency"]]), hide_index=True, width="stretch")
    if not ag: st.info("This analysis ran without AI agents, so the inputs are category priors. Add ANTHROPIC_API_KEY to the app's secrets for web research with sources.")
    if ag.get("regulation"):
        g = ag["regulation"]; st.subheader("Licence and approvals")
        st.write(f"**{g.get('licence_type') or 'Not identified'}** from {g.get('authority') or '–'}. {g.get('notes', '')}")
        for x in g.get("approvals", []): st.markdown(f"- {x['name']}: {x.get('note', '')} " + (f"[source]({x['url']})" if x.get("url") else ""))
    if ag.get("competition"):
        st.subheader("Competitors found")
        for c in ag["competition"]["competitors"]: st.markdown(f"- **{c['name']}** ({c['type']}) {c.get('note', '')} " + (f"[source]({c['url']})" if c.get("url") else ""))
    if ag.get("customer"):
        st.subheader("What customers say")
        for e in ag["customer"].get("evidence", [])[:10]: st.markdown(f"- “{e['quote']}” " + (f"[source]({e['url']})" if e.get("url") else ""))
    srcs = state.get("sources") or {}
    if any(srcs.values()):
        with st.expander(f"All {sum(len(v) for v in srcs.values())} web sources"):
            for k, v in srcs.items():
                for s in v:
                    if str(s.get("url", "")).startswith("http"): st.markdown(f"- {NAMES.get(k, k)}: [{s.get('title') or s['url']}]({s['url']})")


def summary_text(r):
    f = r["stages"]["forecast"]
    return "\n".join([f"ValidateUAE report", r["idea"]["brief"], "", f"Decision: {r['decision']['label']}", *[f"- {x}" for x in r["decision"]["reasons"]], "",
                      f"Validation score {round(r['validation']['score'])}/100 ({r['validation']['verdict']})", f"Payback chance {pct(f['p_payback'])}; exceeds budget {pct(f['p_ruin'])}; expected NPV {aed(f['npv_mean'])}",
                      f"Evidence strength {pct(r['evidence']['strength'])}", "", f"Competition: {r['competition']['headline']}", "", "Stop rules:", *[f"- {x}" for x in r["kill_criteria"]], "", "Next tests:", *[f"- {s['experiment']} ({s['why']})" for s in r["next_steps"]],
                      "", "Decision support only, not financial advice."])


def page_report():
    r, state = ss.result, ss.state
    c1, c2 = st.columns([5, 1])
    c1.markdown("### 🌿 ValidateUAE")
    if c2.button("New idea", width="stretch"):
        for k in ("result", "state", "lab_out", "log"): ss.pop(k, None)
        st.rerun()
    if ss.get("flash"): st.success(ss.pop("flash"))
    tabs = st.tabs(["Decision", "Funnel", "Customer value", "Competition", "Improve my idea", "What-if lab", "Experiments", "Audit", "Assumptions & sources"])
    fns = [tab_decision, tab_funnel, tab_value, tab_competition, tab_improve, tab_lab, tab_experiments, tab_audit, tab_sources]
    for t, fn in zip(tabs, fns):
        with t: fn(r, state)


if ss.get("result"):
    page_report()
else:
    page_start()
st.markdown('<p class="muted" style="margin-top:40px;font-size:12.5px">ValidateUAE is decision support, not financial advice. Category priors and the simulated population are illustrative; replace them with official statistics and real quotes before relying on results.</p>', unsafe_allow_html=True)
