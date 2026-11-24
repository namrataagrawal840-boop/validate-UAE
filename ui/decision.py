"""Decision dashboard: Launch, Test first, Pivot or Stop, with the reasons and what to do next."""
import json

import streamlit as st

from ui import report
from ui.common import ss, esc, pct, aed, kpi, math, section, soft, PASTEL, STATUS

BANNER = {"launch": "mint", "pivot": "sky", "test": "butter", "stop": "rose"}


def score_bar(score, lo, hi):
    return (f'<div style="position:relative;height:16px;border-radius:999px;background:linear-gradient(90deg,#fbe8ec,#fdf3d9 45%,#e5f5ec 70%);margin:10px 0 4px">'
            f'<div style="position:absolute;left:{lo}%;width:{max(hi - lo, 1)}%;top:0;bottom:0;border-radius:999px;background:rgba(100,112,220,.22);border:1px solid rgba(100,112,220,.45)"></div>'
            f'<div style="position:absolute;left:calc({score}% - 2px);top:-4px;width:4px;height:24px;border-radius:2px;background:#5b54a8"></div></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:12px" class="muted"><span>0 · not viable</span><span>50</span><span>100 · strong</span></div>')


def go_to(section_name, key):
    if st.button(f"Go to {section_name}", key=key):
        ss.section = section_name; st.rerun()


def page(r, state):
    b = r["brief"]; f = r["stages"]["forecast"]; L = r["limits"]
    bg, bd, fg = PASTEL[BANNER[b["code"]]]
    st.markdown(f'<div class="banner" style="background:{bg};border-color:{bd}"><div class="k">Recommendation for {esc(ss.get("pname", ""))}</div>'
                f'<h2 style="color:{fg}">{esc(b["label"])}</h2><div style="font-size:16px;margin-bottom:8px">{esc(b["plain"])}</div>'
                + "".join(f"<div>• {esc(x)}</div>" for x in b["reasons"]) + "</div>", unsafe_allow_html=True)
    opts = ["launch", "test", "pivot", "stop"]
    st.markdown("".join(f'<span class="pill" style="{"background:" + PASTEL[BANNER[o]][0] + ";color:" + PASTEL[BANNER[o]][2] + ";border:1px solid " + PASTEL[BANNER[o]][1] if o == b["code"] else "opacity:.55"}">'
                        f'{"● " if o == b["code"] else ""}{STATUS[o][1]}</span>' for o in opts), unsafe_allow_html=True)
    c = st.columns([1.2, 1.2, 1.2, 3])
    with c[0]: math("decision", "How this is decided")
    c[1].download_button("Download summary", report.summary_text(r) + "\n\nNext five actions:\n" + "\n".join(f"{i + 1}. {a['action']} ({a['why']})" for i, a in enumerate(b["next5"])),
                         file_name="validateuae-decision.txt", width="stretch")
    c[2].download_button("Export project data", json.dumps(ss.state, default=str), file_name="validateuae-project.json", width="stretch")
    st.write("")
    c1, c2 = st.columns([1.3, 2])
    with c1:
        with st.container(border=True):
            st.markdown("**Validation score**")
            st.markdown(f'<span style="font-size:46px;font-weight:700;color:#2b3047">{round(b["score"])}</span><span class="muted"> / 100</span>'
                        f'<div class="muted">Confidence range {round(b["score_low"])} to {round(b["score_high"])}. The range narrows as real evidence comes in.</div>'
                        + score_bar(b["score"], b["score_low"], b["score_high"]), unsafe_allow_html=True)
            math("validation")
    with c2:
        k = st.columns(3)
        kpi(k[0], 0, f"Chance of paying back in {f['horizon']} months", pct(f["p_payback"]), f"You need {pct(L['min_payback'])}", "p_payback")
        kpi(k[1], 2, "Chance of needing more than your budget", pct(f["p_ruin"]), f"Your limit {pct(L['max_ruin'])}", "p_ruin")
        kpi(k[2], 1, "Evidence confidence", pct(b["confidence"]), f"{b['hypotheses']['validated']} validated · {b['hypotheses']['disproved']} disproved hypotheses", "evidence")
    pn = state.get("panel")
    if pn:
        from app import panel as PN
        ps = PN.synthesise(pn, r)
        x1, x2 = st.columns([5, 1.4])
        x1.markdown(soft(f"<b>Simulated customer panel:</b> {esc(ps['verdict'].lower())}. {esc(ps['headline'])} Top objection: "
                         f"“{esc(ps['objections'][0]['title'] if ps['objections'] else 'none')}”. <span class='muted'>Simulated, so it is not counted as evidence.</span>", "lavender"),
                    unsafe_allow_html=True)
        if x2.button("Open Customer panel", key="g_panel", width="stretch"):
            ss.section = "Customer panel"; st.rerun()
    else:
        x1, x2 = st.columns([5, 1.4])
        x1.markdown(soft("No research yet? Run the <b>Customer panel</b>: simulated UAE customers react to your idea, debate it and show the likely objections.", "lavender"),
                    unsafe_allow_html=True)
        if x2.button("Run a customer panel", key="g_panel0", width="stretch"):
            ss.section = "Customer panel"; st.rerun()
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            section("Strongest supporting evidence", "mint")
            if b["strongest"]:
                for x in b["strongest"]:
                    st.markdown(f"**{esc(x['claim'])}**  \n<span class='muted'>{esc(x['type'])} · {esc(x['area'])} · {esc(x['verification'])}"
                                + (f" · weight {x['weight']:.2f}" if x["type"] != "Validated hypothesis" else "") + "</span>", unsafe_allow_html=True)
            else:
                st.markdown("No real-world evidence yet. The recommendation rests on typical figures and estimates.")
                go_to("Validation lab", "g_lab0")
    with c2:
        with st.container(border=True):
            section("Weakest assumptions", "rose")
            for x in b["weakest"]:
                st.markdown(f"**{esc(x['name'])}**  \n<span class='muted'>{esc(x['why'])} {esc(x['fix'])}</span>", unsafe_allow_html=True)
            if not b["weakest"]: st.markdown("No weak spots flagged.")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            section("Financial risks", "peach")
            st.markdown("\n".join(f"- {esc(x)}" for x in b["risks"]))
            go_to("Financials", "g_fin")
    with c2:
        with st.container(border=True):
            section("Missing evidence", "butter")
            if b["missing"]:
                st.markdown("\n".join(f"- **{esc(x['name'])}**: {esc(x['how'])}" for x in b["missing"]))
            else:
                st.markdown("Every important area has at least some evidence.")
            go_to("Evidence ledger", "g_ev")
    section("Next five actions", "lavender")
    for i, a in enumerate(b["next5"]):
        with st.container(border=True):
            x1, x2 = st.columns([5, 1.4])
            x1.markdown(f"**{i + 1}. {esc(a['action'])}**  \n<span class='muted'>{esc(a['why'])}</span>", unsafe_allow_html=True)
            if a["where"] != "Decision" and x2.button(f"Open {a['where']}", key=f"na{i}", width="stretch"):
                ss.section = a["where"]; st.rerun()
    with st.expander("The idea, the six checks and how simulated customers reacted"):
        report.tab_decision(r, state, show_header=False)
