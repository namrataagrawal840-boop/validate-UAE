"""Saved projects with their validation status."""
import datetime as dt

import streamlit as st

from app import priors as P
from app import store
import json

import pandas as pd

from ui.common import ss, esc, pct, aed, pill_status, PASTEL, STATUS, user_id, open_project, approx


def _when(iso):
    try:
        d = dt.datetime.fromisoformat(iso)
        return d.strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return ""


def page():
    rows = store.list_projects(user_id())
    try:
        return _page(rows)
    finally:
        account()


def _page(rows):
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
    try:
        from app import alerts as AL
        items = AL.for_user(user_id())
    except Exception:
        items = []
    if items:
        with st.container(border=True):
            st.markdown(f"**{len(items)} thing{'s' if len(items) > 1 else ''} need{'' if len(items) > 1 else 's'} attention**")
            for i in items[:6]: st.markdown(f"<span class='pill p-{i['level']}'>{esc(i['project'])}</span> {esc(i['text'])}", unsafe_allow_html=True)
    view = st.segmented_control("Show", ["List", "Pipeline", "Compare"], default="List", label_visibility="collapsed") or "List"
    if view == "Pipeline": return pipeline(rows)
    if view == "Compare": return compare(rows)
    q = st.text_input("Search projects", placeholder="Name or business type", label_visibility="collapsed")
    for r in rows:
        if q and q.lower() not in f"{r['name']} {P.TYPES.get(r['business_type'], {}).get('label', '')}".lower(): continue
        colour = STATUS.get(r["status"], ("lavender", ""))[0]
        bg, bd, _ = PASTEL[colour]
        with st.container(border=True):
            a, b, c, d = st.columns([3.2, 1.2, 1.2, 1.4])
            shared = f" <span class='pill p-info'>Shared by {esc(r['owner'])} · {r['role']}</span>" if r.get("role") != "owner" else ""
            a.markdown(f"**{esc(r['name'])}**{shared}  \n<span class='muted'>{esc(P.TYPES.get(r['business_type'], {}).get('label', ''))} · {esc(r['emirate'] or '')} · updated {_when(r['updated_at'])}</span>",
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
            if r.get("role") != "owner":
                if e2.button("Leave", key=f"leave{r['id']}", width="stretch"):
                    me = user_id(); store.unshare_project(me, r["id"], me); st.rerun()
                continue
            with e2.popover("Delete", width="stretch"):
                st.write(f"Delete **{r['name']}** with all its evidence, hypotheses and actuals? This cannot be undone.")
                if st.button("Yes, delete it", key=f"del{r['id']}", type="primary"):
                    store.delete_project(user_id(), r["id"])
                    if ss.get("pid") == r["id"]:
                        for k in ("pid", "state", "result", "pname", "baseline"): ss.pop(k, None)
                    st.rerun()



def pipeline(rows):
    """Every idea by stage, like a stage-gate board."""
    cols = st.columns(4)
    for col, k in zip(cols, ("test", "pivot", "launch", "stop")):
        c, label = STATUS[k]; bg, bd, fg = PASTEL[c]
        group = [r for r in rows if r["status"] == k]
        col.markdown(f'<div class="kpi" style="background:{bg};border-color:{bd}"><div class="l">{label}</div><div class="v">{len(group)}</div></div>', unsafe_allow_html=True)
        for r in group:
            with col.container(border=True):
                st.markdown(f"**{esc(r['name'])}**  \n<span class='muted' style='font-size:12.5px'>score {'–' if r['score'] is None else round(r['score'])} · "
                            f"evidence {'–' if r['confidence'] is None else pct(r['confidence'])} · {r['evidence_count']} records</span>", unsafe_allow_html=True)
                if st.button("Open", key=f"po{r['id']}", width="stretch"):
                    open_project(r["id"]); ss.view = "project"; ss.section = "Decision"; st.rerun()
    st.caption("Moves right as evidence comes in: Test first → Launch with changes / Launch, or Stop.")


def compare(rows):
    from app import market_size as MZ
    names = {r["id"]: r["name"] for r in rows}
    pick = st.multiselect("Pick 2 to 4 projects to compare", list(names), format_func=names.get, max_selections=4, default=list(names)[:min(3, len(names))])
    if len(pick) < 2:
        st.info("Pick at least two projects."); return
    table = {}
    for p in store.project_summaries(user_id(), pick):
        r, s_ = p["result"], p["state"] or {}
        if not r or "decision" not in r: continue
        f = r["stages"]["forecast"]; pv = (r.get("finance") or {}).get("payback") or {}
        m = MZ.size(r, s_.get("market_overrides"), s_.get("panel")); R = m.get("ranges") or {}
        parts = (r["validation"].get("parts") or {})
        table[p["name"]] = {
            "Decision": r["decision"]["label"], "Typical payback": f"month {pv['typical']}" if pv.get("typical") else f"> {f['horizon']} months",
            "6 in 10 futures paid back by": f"month {pv['safe']}" if pv.get("safe") else "beyond plan", "Time limit": f"{f['horizon']} months",
            "Paid back in time": pct(f["p_payback"]), "Budget risk": pct(f["p_ruin"]), "Expected value (NPV)": aed(f["npv_mean"]),
            "Cash to have ready": aed(r["finance"]["runway"]["cash_need_p90"]), "Evidence confidence": pct(r["evidence"]["strength"]),
            "Validation score": f"{round(r['validation']['score'])}/100", **{p_["name"]: f"{round(p_['score'])}" for p_ in parts.values()},
            "Customers you could win (SOM)": f"{approx(R['som'][0])}–{approx(R['som'][1])}" if "som" in R else approx(m["som"]["people"]),
            "Desk tests done": str(sum(1 for t in (s_.get("desk_tests") or {}).values() if t.get("status") == "done")),
            "What matters most": r["finance"]["tornado"]["rows"][0]["name"]}
    df = pd.DataFrame(table)
    st.dataframe(df, width="stretch", height=36 * (len(df) + 1) + 4)
    st.caption("Same method, same safety standard and the same published figures for every project, so the columns are comparable.")


def account():
    with st.expander("Your account and data"):
        st.download_button("Download everything (JSON backup)", json.dumps(store.export_account(user_id()), default=str), file_name="validateuae-backup.json")
        st.markdown("**Delete my account.** Deletes your account, all your projects with their evidence, tests and history, and removes you from shared projects. This cannot be undone.")
        t = st.text_input("Type your username to confirm", key="del_acct")
        if st.button("Delete my account and all data", type="primary", disabled=t != ss.user["username"]):
            store.delete_account(user_id())
            from ui import auth
            auth.logout()
