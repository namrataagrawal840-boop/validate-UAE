"""Shared look, helpers and project session handling for the Streamlit app."""
import copy
import html
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import priors as P
from app import store
from app.compute import compute, LABEL
from ui_explain import explain, aed, pct, num

ss = st.session_state

# Soft pastels: one colour per meaning, used sparingly (headline numbers, status, steps, section chips)
PASTEL = dict(lavender=("#f4f2ff", "#e3defb", "#5b54a8"), mint=("#eef8f3", "#d3ecdf", "#3f8f72"), peach=("#fff4ec", "#f8dcc8", "#a8643a"),
              sky=("#eef5ff", "#d6e6fa", "#3f6fae"), butter=("#fffae8", "#f2e6b6", "#8c6d1a"), rose=("#fdf0f3", "#f3d6de", "#a5505f"))
STATUS = {"launch": ("mint", "Launch"), "pivot": ("sky", "Pivot"), "test": ("butter", "Test first"), "stop": ("rose", "Stop")}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stButton button, input, textarea, select { font-family: 'Plus Jakarta Sans', system-ui, sans-serif !important; }
.block-container { padding-top: 2rem; max-width: 1180px; }
h1, h2, h3 { color: #2b3047; letter-spacing: -.015em; }
section[data-testid="stSidebar"] { background: #faf9ff; border-right: 1px solid #eeecfb; }
.kpi { border-radius: 14px; padding: 14px 16px; border: 1px solid; height: 100%; }
.kpi .l { font-size: 13px; color: #6b7189; } .kpi .v { font-size: 26px; font-weight: 700; color: #2b3047; line-height: 1.25; } .kpi .s { font-size: 12.5px; color: #6b7189; }
.k0 { background: #f4f2ff; border-color: #e3defb; } .k1 { background: #eef8f3; border-color: #d3ecdf; } .k2 { background: #fff4ec; border-color: #f8dcc8; } .k3 { background: #eef5ff; border-color: #d6e6fa; }
.box { border: 1px solid #eceef4; border-radius: 14px; padding: 16px 18px; background: #fff; margin-bottom: 4px; }
.soft { border-radius: 14px; padding: 14px 16px; border: 1px solid; margin-bottom: 8px; }
.banner { border-radius: 18px; padding: 22px 24px; border: 1px solid; margin-bottom: 8px; }
.banner h2 { margin: 2px 0 8px; font-size: 30px; } .banner .k { color: #6b7189; font-size: 14px; }
.b-launch { background: #eef8f3; border-color: #d3ecdf; } .b-pivot { background: #eef5ff; border-color: #d6e6fa; }
.b-test { background: #fffae8; border-color: #f2e6b6; } .b-stop { background: #fdf0f3; border-color: #f3d6de; }
.pill { display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 9px; border-radius: 999px; background: #f3f4f8; color: #6b7189; margin-right: 4px; }
.p-good { background: #e5f5ec; color: #3f8f72; } .p-warn { background: #fdf3d9; color: #8c6d1a; } .p-bad { background: #fbe8ec; color: #a5505f; } .p-info { background: #ebefff; color: #4f62b8; }
.p-lav { background: #efecff; color: #5b54a8; } .p-peach { background: #ffeee2; color: #a8643a; }
.chip { display: inline-block; font-size: 12px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; padding: 3px 10px; border-radius: 8px; margin-bottom: 6px; }
.muted { color: #6b7189; font-size: 14px; }
.steps { display: flex; gap: 8px; margin: 4px 0 14px; }
.step { flex: 1; border-radius: 12px; padding: 10px 12px; border: 1px solid #eceef4; background: #fff; font-size: 13.5px; color: #8a8fa6; }
.step b { display: block; font-size: 12px; letter-spacing: .04em; text-transform: uppercase; }
.step.done { background: #eef8f3; border-color: #d3ecdf; color: #3f8f72; } .step.now { background: #f4f2ff; border-color: #cfc8f6; color: #5b54a8; }
.pcard { border-radius: 16px; padding: 16px 18px; border: 1px solid; margin-bottom: 4px; }
[data-testid="stMetricValue"] { font-size: 24px !important; font-weight: 600; color: #2b3047; }
[data-testid="stMetricLabel"] p { color: #6b7189 !important; }
div[data-testid="stTabs"] button p { font-size: 15px; }
</style>
"""


def styles():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(x):
    """Escape any user- or web-supplied text before it goes into HTML."""
    return html.escape(str(x if x is not None else ""))


def chip(text, colour="lavender"):
    bg, bd, fg = PASTEL[colour]
    return f'<span class="chip" style="background:{bg};color:{fg};border:1px solid {bd}">{esc(text)}</span>'


def soft(content_html, colour="lavender"):
    bg, bd, _ = PASTEL[colour]
    return f'<div class="soft" style="background:{bg};border-color:{bd}">{content_html}</div>'


def section(title, colour="lavender", sub=None):
    st.markdown(chip(title, colour), unsafe_allow_html=True)
    if sub: st.markdown(f'<p class="muted" style="margin-top:-4px">{sub}</p>', unsafe_allow_html=True)


# What kind of number is this? Facts, estimates and assumptions are always labelled.
KIND = {"measured": ("Measured", "good"), "benchmarked": ("Sourced", "info"), "web": ("Sourced (web, unverified)", "info"),
        "founder": ("Your assumption", "warn"), "ai": ("AI estimate", "lav"), "critic": ("AI estimate", "lav"),
        "derived": ("Model estimate", ""), "prior": ("Typical for the category", "")}


def kind_pill(label):
    t, tone_ = KIND.get(label, (label, ""))
    return f'<span class="pill p-{tone_}">{t}</span>'

PLOT = dict(template="simple_white", height=300, margin=dict(l=10, r=10, t=10, b=10), font=dict(family="Plus Jakarta Sans, sans-serif", size=12, color="#6b7189"))
LINE, BAND, ZERO = "#6470dc", "rgba(118,130,230,.16)", "#d9a35a"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
months = lambda n: [f"{MON[i % 12]} {str(P.START_YEAR + i // 12)[2:]}" for i in range(n)]
EXAMPLES = [
    dict(idea="A cloud kitchen in Business Bay delivering healthy, high-protein lunches to office workers, ordered through our own app and the delivery platforms.", business_type="kitchen", emirate="Dubai", setup="Mainland", target_customer="Office workers aged 25-45 in Business Bay and DIFC", budget_aed=600000),
    dict(idea="An online platform that matches children aged 6 to 14 with qualified Arabic tutors for live lessons, with weekly progress reports for parents.", business_type="education", emirate="All UAE", setup="Free zone", target_customer="Parents who want their children to improve their Arabic", budget_aed=300000),
    dict(idea="A women-only boutique fitness studio in Sharjah with small group classes, childcare during sessions and flexible class packs.", business_type="fitness", emirate="Sharjah", setup="Mainland", target_customer="Women aged 25-50 living in Sharjah", budget_aed=900000),
]
_N = [0]


def chart(fig):
    _N[0] += 1
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=f"chart{_N[0]}")


def kpi(col, i, label, value, sub="", math_key=None):
    with col:
        st.markdown(f'<div class="kpi k{i % 4}"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div><div class="s">{esc(sub)}</div></div>', unsafe_allow_html=True)
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



def pill_status(code):
    c, t = STATUS.get(code, ("lavender", "Not run"))
    bg, bd, fg = PASTEL[c]
    return f'<span class="pill" style="background:{bg};color:{fg};border:1px solid {bd}">{t}</span>'


# ---------------- project session ----------------
def user_id():
    return ss["user"]["id"]


def ledger_for_engine():
    """Evidence records the engine may use (no file bytes)."""
    try:
        return [{k: v for k, v in r.items() if k != "has_file"} for r in store.list_evidence(user_id(), ss.pid)]
    except store.NotFound:
        return []


def run_compute(state):
    s = copy.deepcopy(state); s["ledger"] = ledger_for_engine()
    s["hypotheses"] = store.list_hypotheses(user_id(), ss.pid) if ss.get("pid") else []
    return compute(s)


def open_project(pid):
    p = store.load_project(user_id(), pid)
    ss.pid, ss.state, ss.pname, ss.baseline = pid, p["state"], p["name"], p["baseline"]
    ss.result = p["result"]
    if not ss.result or ss.result.get("_version") != RESULT_VERSION:
        with st.spinner("Updating this project to the latest analysis…"):
            ss.result = run_compute(ss.state); ss.result["_version"] = RESULT_VERSION
        store.save_project(user_id(), pid, result=ss.result)
    ss._explain = explain(ss.result)
    for k in ("lab_out",): ss.pop(k, None)
    ensure_starter()


def ensure_starter():
    """Give every project something to work with from day one, once:
    a simulated customer panel (labelled simulated, zero weight) and three starter hypotheses in the lab.
    Real evidence still decides confidence; nothing here changes the forecast."""
    from app import panel as PN
    from app import lab as LB
    st_ = ss.state; changed = False
    if not st_.get("panel"):
        try:
            pn = PN.build(ss.result, n=40); pn["debate"] = PN.debate(pn, ss.result)
            st_ = copy.deepcopy(st_); st_["panel"] = pn; changed = True
        except Exception:  # a missing panel must never block opening a project
            pass
    if not st_.get("starter_hypotheses"):
        try:
            have = {h["metric"] for h in store.list_hypotheses(user_id(), ss.pid)}
            for h in [x for x in LB.suggestions(ss.result) if x["metric"] not in have][:3]:
                h = dict(h, status="planned", direction=LB.METRICS[h["metric"]][3]); h["plan"] = LB.plan(dict(h, id="new"), ss.result, ss.result["kit"])
                store.add_hypothesis(user_id(), ss.pid, h)
            st_ = copy.deepcopy(st_) if not changed else st_; st_["starter_hypotheses"] = True; changed = True
        except Exception:
            pass
    if changed:
        store.save_project(user_id(), ss.pid, state=st_); ss.state = st_


def refresh(message=None, state=None):
    """Recalculate with the current state and ledger, save, and rerun the page."""
    if state is not None: ss.state = state
    with st.spinner("Recalculating…"):
        r = run_compute(ss.state); r["_version"] = RESULT_VERSION
    store.save_project(user_id(), ss.pid, state=ss.state, result=r)
    ss.result = r; ss._explain = explain(r)
    if message: ss.flash = message
    st.rerun()


def recompute(mutate, message):
    state = copy.deepcopy(ss.state); mutate(state)
    refresh(message, state)


RESULT_VERSION = 5


# ---------------- experiments always come with a ledger record ----------------
def add_experiment(e, message, hypothesis_id=None):
    """Store a lab result in the project and a matching record in the evidence ledger, then recalculate."""
    import uuid
    import datetime as dt
    from app import evidence as EV
    e = dict(e, id=e.get("id") or str(uuid.uuid4()), date=e.get("date") or dt.date.today().isoformat())
    if hypothesis_id: e["hypothesis_id"] = hypothesis_id
    store.add_evidence(user_id(), ss.pid, EV.from_experiment(e, ss.state["intake"]))
    state = copy.deepcopy(ss.state); state.setdefault("experiments", []).append(e)
    refresh(message, state)


def remove_experiment(index, message="Result removed."):
    state = copy.deepcopy(ss.state); e = state["experiments"].pop(index)
    if e.get("id"): store.delete_evidence(user_id(), ss.pid, experiment_id=e["id"])
    refresh(message, state)
