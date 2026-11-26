"""Project sections shown in the sidebar, in the order a founder works through them."""
import streamlit as st

from app import store
from ui import report, evidence, finance, insights, lab, decision, monitor, panel, market, social, search, loop, share, extra
from ui.common import ss, user_id, can_edit


def header():
    r = ss.result
    c1, c2 = st.columns([5, 1])
    c1.markdown(f"<span class='muted'>{r['intake']['emirate']} · {r['intake']['setup']}</span>", unsafe_allow_html=True)
    if not can_edit():
        c2.markdown("<span class='pill p-info'>View only</span>", unsafe_allow_html=True); return
    with c2.popover("Rename", width="stretch"):
        n = st.text_input("Project name", ss.get("pname", ""), max_chars=120)
        if st.button("Save name") and n.strip():
            store.save_project(user_id(), ss.pid, name=n.strip()); ss.pname = n.strip(); st.rerun()


SECTIONS = {
    "Decision": decision.page,
    "Improve my idea": report.tab_improve,
    "Version history": extra.history_page,
    "Market size": market.page,
    "Search demand": search.page,
    "Competition": report.tab_competition,
    "Customer panel": panel.page,
    "Social listening": social.page,
    "Market and customers": insights.page,
    "Financials": finance.page,
    "What-if lab": report.tab_lab,
    "Funnel (all 10 stages)": report.tab_funnel,
    "Run a test": loop.page,
    "Evidence ledger": evidence.page,
    "Validation lab": lab.page,
    "Monitoring": monitor.page,
    "Import results": extra.import_page,
    "Share and report": share.page,
    "Methods and calibration": extra.methods_page,
    "Audit": report.tab_audit,
    "Assumptions and sources": report.tab_sources,
}
# Full view: six groups that mirror the simple pages; each group has tabs.
GROUPS = {
    "Decision": ["Decision", "Improve my idea", "Version history"],
    "Market": ["Market size", "Search demand", "Competition"],
    "Customers": ["Customer panel", "Social listening", "Market and customers"],
    "Money": ["Financials", "What-if lab", "Funnel (all 10 stages)"],
    "Tests and evidence": ["Run a test", "Evidence ledger", "Validation lab", "Monitoring", "Import results"],
    "Report and method": ["Share and report", "Methods and calibration", "Audit", "Assumptions and sources"],
}
GROUP_OF = {sec: g for g, secs in GROUPS.items() for sec in secs}


def render(name):
    header()
    loop.progress(ss.result, ss.state)
    g = GROUP_OF.get(name, "Decision")
    tabs = GROUPS[g]
    pick = st.segmented_control(g, tabs, default=name if name in tabs else tabs[0], label_visibility="collapsed")
    if pick and pick != name:
        ss.section = pick; st.rerun()
    SECTIONS.get(name, decision.page)(ss.result, ss.state)
    share.comments_box(name)
