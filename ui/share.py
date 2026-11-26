"""Step 6: the shareable report, downloads for analysts, the team, comments, alerts and the activity log."""
import copy
import csv
import io
import json

import streamlit as st

from app import alerts as AL
from app import evidence as EV
from app import market_size as MZ
from app import report_export as RX
from app import store
from ui.common import ss, esc, section, soft, user_id, can_edit


def _content(r, state):
    ledger = store.list_evidence(user_id(), ss.pid); hyps = store.list_hypotheses(user_id(), ss.pid)
    m = MZ.size(r, state.get("market_overrides"), state.get("panel"))
    return RX.content(r, state, m, ledger, hyps, ss.get("pname", "Project"), ss.user["username"]), ledger


def _mark_shared():
    if can_edit() and not ss.state.get("shared_report"):
        s = copy.deepcopy(ss.state); s["shared_report"] = True
        store.save_project(user_id(), ss.pid, state=s); ss.state = s
    store.log(user_id(), ss.pid, "Downloaded report", "")


def _csv(columns, rows):
    b = io.StringIO(); w = csv.writer(b); w.writerow(columns); w.writerows(rows); return b.getvalue()


def comments_box(where):
    """Comments on one page: anyone with access (viewers too) can comment; anyone can resolve."""
    if not ss.get("pid"): return
    try: cs = store.list_comments(user_id(), ss.pid, where)
    except store.NotFound: return
    with st.expander(f"💬 Comments on this page ({len(cs)})"):
        for c in cs:
            a, b = st.columns([6, 1])
            a.markdown(f"**{esc(c['username'])}** <span class='muted' style='font-size:12px'>{esc(c['created_at'][:16].replace('T', ' '))}</span><br>{esc(c['text'])}", unsafe_allow_html=True)
            if b.button("Resolve", key=f"res{c['id']}"):
                store.resolve_comment(user_id(), ss.pid, c["id"]); st.rerun()
        with st.form(f"cm_{where}", clear_on_submit=True):
            t = st.text_area("Add a comment", height=70, label_visibility="collapsed", placeholder="Ask a question or note something for the team")
            if st.form_submit_button("Post comment") and t.strip():
                store.add_comment(user_id(), ss.pid, where, t); store.log(user_id(), ss.pid, "Comment", f"{where}: {t[:80]}"); st.rerun()


def page(r, state):
    st.header("Share and report")
    c, ledger = _content(r, state)
    key = (r.get("run_info") or {}).get("input_hash", "") + str(len(ledger)) + str(len(state.get("desk_tests") or {}))
    cache = ss.setdefault("_report_cache", {})
    if cache.get("key") != key:
        with st.spinner("Preparing the report…"):
            cache.update(key=key, pdf=RX.pdf(c), pptx=RX.slides(c))
    section("The report", "lavender", "The verdict, the five answers, the evidence, the desk tests, the method and the sources, as of now.")
    a, b = st.columns(2)
    name = "".join(ch if ch.isalnum() else "-" for ch in ss.get("pname", "project"))[:40]
    a.download_button("📄 Download the PDF report", cache["pdf"], file_name=f"ValidateUAE-{name}.pdf", mime="application/pdf", type="primary", width="stretch", on_click=_mark_shared)
    b.download_button("📊 Download the slides (PowerPoint)", cache["pptx"], file_name=f"ValidateUAE-{name}.pptx",
                      mime="application/vnd.openxmlformats-officedocument.presentationml.presentation", width="stretch", on_click=_mark_shared)
    st.caption(f"{len(c['models'])} methods described in the appendix · run fingerprint {c['run'].get('input_hash', '–')} · model {c['run'].get('model_version', '–')}")

    section("For analysts", "sky")
    ri = r.get("run_info") or {}
    bundle = dict(run=ri, intake=r["intake"], settings=r["settings"], limits=r["limits"], ledger=[{k: v for k, v in x.items() if k != "has_file"} for x in ledger],
                  desk_tests=state.get("desk_tests"), experiments=state.get("experiments"), overrides=state.get("overrides"),
                  outputs=dict(decision=r["decision"]["code"], payback=r["finance"].get("payback"), p_payback=r["stages"]["forecast"]["p_payback"],
                               p_ruin=r["stages"]["forecast"]["p_ruin"], npv_mean=r["stages"]["forecast"]["npv_mean"], evidence=r["evidence"]["strength"],
                               validation=r["validation"]["score"]),
                  how_to_reproduce="Load the intake, settings, ledger and experiments into compute() with the same model version and seed; the input fingerprint must match.")
    x1, x2, x3 = st.columns(3)
    x1.download_button("Reproducibility bundle (JSON)", json.dumps(bundle, default=str, indent=1), file_name=f"{name}-reproduce.json", width="stretch")
    rt = r.get("runs_table")
    if rt: x2.download_button(f"All {len(rt['rows'])} simulated futures (CSV)", _csv(rt["columns"], rt["rows"]), file_name=f"{name}-simulation-runs.csv", width="stretch")
    x3.download_button("Evidence ledger (CSV)", _csv(["claim", "area", "type", "weight", "verification", "geography", "collected_on", "value_likely", "source_url", "limitations"],
                                                     [[e.get("claim"), e.get("area"), EV.TYPES.get(e.get("ev_type"), ("",))[0], round(EV.weight(e)[0], 3), e.get("verification"),
                                                       e.get("geography"), e.get("collected_on"), e.get("value_likely"), e.get("source_url"), e.get("limitations")] for e in ledger]),
                       file_name=f"{name}-evidence.csv", width="stretch")

    section("Team", "mint", "Editors can change the project; viewers can read and comment.")
    members = store.list_members(user_id(), ss.pid)
    for m in members:
        a, b = st.columns([5, 1])
        a.markdown(f"**{esc(m['username'])}** · {m['role']}")
        if ss.get("role", "owner") == "owner" and m["role"] != "owner" and b.button("Remove", key=f"rm{m['id']}"):
            store.unshare_project(user_id(), ss.pid, m["id"]); store.log(user_id(), ss.pid, "Removed member", m["username"]); st.rerun()
    if ss.get("role", "owner") == "owner":
        with st.form("share", clear_on_submit=True):
            a, b, c_ = st.columns([3, 1.4, 1.2])
            who = a.text_input("Their ValidateUAE username", placeholder="username")
            role = b.selectbox("Role", ["viewer", "editor"])
            if c_.form_submit_button("Share", type="primary", width="stretch") and who.strip():
                try:
                    u = store.share_project(user_id(), ss.pid, who, role); store.log(user_id(), ss.pid, "Shared", f"{u['username']} as {role}")
                    ss.flash = f"Shared with {u['username']} as {role}."; st.rerun()
                except ValueError as e:
                    st.error(str(e))
    else:
        st.caption(f"You are a {ss.get('role')} on this project. Only the owner can share it.")

    section("Alerts", "butter", "What needs attention now; optionally sent to you every day.")
    items = AL.for_project(ss.get("pname", ""), state, r, store.list_actuals(user_id(), ss.pid), ss.get("baseline"))
    for i in items: st.markdown(f"<span class='pill p-{i['level']}'>{'Warning' if i['level'] == 'warn' else 'Alert'}</span> {esc(i['text'])}", unsafe_allow_html=True)
    if not items: st.markdown("Nothing needs attention in this project right now.")
    ch = AL.channels(); ct = AL.contact(user_id())
    with st.expander("Get alerts by email or WhatsApp"):
        st.caption(("Email is set up on this server. " if ch["email"] else "Email needs SMTP secrets on the server (see README). ") +
                   ("WhatsApp is set up." if ch["whatsapp"] else "WhatsApp needs Twilio secrets on the server (see README)."))
        with st.form("contact"):
            em = st.text_input("Email", ct.get("email", "")); wa = st.text_input("WhatsApp number with country code", ct.get("whatsapp", ""), placeholder="+9715…")
            daily = st.checkbox("Send me a daily digest of all my projects", ct.get("daily", False))
            s1, s2 = st.columns(2)
            save = s1.form_submit_button("Save"); send = s2.form_submit_button("Send a digest now")
        if save or send:
            AL.save_contact(user_id(), em, wa, daily)
            if send:
                res = AL.send(AL.contact(user_id()), AL.digest_text(AL.for_user(user_id())))
                for chn, ok, msg in res: (st.success if ok else st.warning)(f"{chn}: {msg}")
                if not res: st.info("Add an email or WhatsApp number first.")
            else:
                st.success("Saved.")

    section("Open comments", "rose")
    cs = store.list_comments(user_id(), ss.pid)
    for x in cs: st.markdown(f"**{esc(x['username'])}** on *{esc(x['section'])}*: {esc(x['text'])}")
    if not cs: st.markdown("No open comments. Each page has a comments box at the bottom.")
    with st.expander("Activity log"):
        for x in store.list_activity(user_id(), ss.pid, 100):
            st.markdown(f"<span class='muted' style='font-size:12.5px'>{esc(x['created_at'][:16].replace('T', ' '))}</span> **{esc(x['username'])}** · {esc(x['action'])}"
                        + (f" · {esc(x['detail'])}" if x["detail"] else ""), unsafe_allow_html=True)
