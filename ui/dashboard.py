"""Saved projects with their validation status."""
import datetime as dt

import streamlit as st

from app import priors as P
from app import store
from ui.common import ss, esc, pct, pill_status, PASTEL, STATUS, user_id, open_project


def _when(iso):
    try:
        d = dt.datetime.fromisoformat(iso)
        return d.strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return ""


def page():
    rows = store.list_projects(user_id())
    c1, c2 = st.columns([4, 1])
    c1.header("My projects")
    if c2.button("➕ New project", type="primary", width="stretch"):
        ss.view = "new"; ss.pop("ob", None); st.rerun()
    if not rows:
        st.markdown('<div class="soft" style="background:#f4f2ff;border-color:#e3defb"><b>No projects yet.</b><br>'
                    '<span class="muted">Start a new project: four short steps, about five minutes. You can skip anything you don\'t know.</span></div>', unsafe_allow_html=True)
        return
    counts = {k: sum(r["status"] == k for r in rows) for k in STATUS}
    cols = st.columns(5)
    tiles = [("All projects", len(rows), "lavender")] + [(STATUS[k][1], counts[k], STATUS[k][0]) for k in ("launch", "test", "pivot", "stop")]
    for col, (lab, n, colour) in zip(cols, tiles):
        bg, bd, fg = PASTEL[colour]
        col.markdown(f'<div class="kpi" style="background:{bg};border-color:{bd}"><div class="l">{esc(lab)}</div><div class="v">{n}</div></div>', unsafe_allow_html=True)
    st.write("")
    q = st.text_input("Search projects", placeholder="Name or business type", label_visibility="collapsed")
    for r in rows:
        if q and q.lower() not in f"{r['name']} {P.TYPES.get(r['business_type'], {}).get('label', '')}".lower(): continue
        colour = STATUS.get(r["status"], ("lavender", ""))[0]
        bg, bd, _ = PASTEL[colour]
        with st.container(border=True):
            a, b, c, d = st.columns([3.2, 1.2, 1.2, 1.4])
            a.markdown(f"**{esc(r['name'])}**  \n<span class='muted'>{esc(P.TYPES.get(r['business_type'], {}).get('label', ''))} · {esc(r['emirate'] or '')} · updated {_when(r['updated_at'])}</span>",
                       unsafe_allow_html=True)
            b.markdown(f"<span class='muted' style='font-size:12.5px'>Decision</span><br>{pill_status(r['status'])}", unsafe_allow_html=True)
            c.markdown(f"<span class='muted' style='font-size:12.5px'>Validation score</span><br><b>{'–' if r['score'] is None else round(r['score'])}</b>/100", unsafe_allow_html=True)
            d.markdown(f"<span class='muted' style='font-size:12.5px'>Evidence confidence</span><br><b>{'–' if r['confidence'] is None else pct(r['confidence'])}</b> · {r['evidence_count']} record{'' if r['evidence_count'] == 1 else 's'}",
                       unsafe_allow_html=True)
            e1, e2, _ = st.columns([1, 1, 4])
            if e1.button("Open", key=f"open{r['id']}", type="primary", width="stretch"):
                try:
                    open_project(r["id"]); ss.view = "project"; ss.section = "Decision"; st.rerun()
                except store.NotFound:
                    st.error("This project no longer exists.")
            with e2.popover("Delete", width="stretch"):
                st.write(f"Delete **{r['name']}** with all its evidence, hypotheses and actuals? This cannot be undone.")
                if st.button("Yes, delete it", key=f"del{r['id']}", type="primary"):
                    store.delete_project(user_id(), r["id"])
                    if ss.get("pid") == r["id"]:
                        for k in ("pid", "state", "result", "pname", "baseline"): ss.pop(k, None)
                    st.rerun()
