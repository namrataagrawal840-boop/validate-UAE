"""Project sections shown in the sidebar, in the order a founder works through them."""
import streamlit as st

from app import store
from ui import report, evidence, finance, insights, lab, decision
from ui.common import ss, user_id


def header():
    r = ss.result
    c1, c2 = st.columns([5, 1])
    c1.markdown(f"<span class='muted'>{r['intake']['emirate']} · {r['intake']['setup']}</span>", unsafe_allow_html=True)
    with c2.popover("Rename", width="stretch"):
        n = st.text_input("Project name", ss.get("pname", ""), max_chars=120)
        if st.button("Save name") and n.strip():
            store.save_project(user_id(), ss.pid, name=n.strip()); ss.pname = n.strip(); st.rerun()


SECTIONS = {
    "Decision": decision.page,
    "Evidence ledger": evidence.page,
    "Validation lab": lab.page,
    "Financials": finance.page,
    "Market and customers": insights.page,
    "Competition": report.tab_competition,
    "Improve my idea": report.tab_improve,
    "What-if lab": report.tab_lab,
    "Funnel (all 10 stages)": report.tab_funnel,
    "Audit": report.tab_audit,
    "Assumptions and sources": report.tab_sources,
}


def render(name):
    header()
    SECTIONS.get(name, decision.page)(ss.result, ss.state)
