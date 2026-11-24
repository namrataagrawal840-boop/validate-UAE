"""ValidateUAE - Streamlit app.

Run locally:   streamlit run streamlit_app.py
Deploy:        share.streamlit.io -> New app -> this repository -> streamlit_app.py
Secrets:       ANTHROPIC_API_KEY (optional), DATABASE_URL (recommended on Streamlit Cloud so projects survive restarts),
               SECRET_KEY (optional), ALLOW_SIGNUP ("false" to stop new accounts)
"""
import logging
import os
import sys
import traceback

import streamlit as st

st.set_page_config(page_title="ValidateUAE", page_icon="🌿", layout="wide")

# Secrets -> environment, before the backend is imported. Secrets never appear in code or in the repository.
for _k in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "WEB_SEARCH_TOOL", "SIM_MODE", "DATABASE_URL", "SECRET_KEY", "ALLOW_SIGNUP"):
    try:
        if _k in st.secrets and not os.getenv(_k):
            os.environ[_k] = str(st.secrets[_k])
    except Exception:
        pass
os.environ.setdefault("SIM_MODE", "fast")  # Streamlit Cloud has modest CPU; set SIM_MODE="full" in secrets for more replays
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
log = logging.getLogger("validateuae")

from app import store  # noqa: E402
from ui import auth, dashboard, onboarding, glossary  # noqa: E402
from ui.common import ss, styles, esc, pill_status, user_id, open_project  # noqa: E402
from ui import sections  # noqa: E402

styles()


def restore_session():
    """A page reload starts a new Streamlit session. The page address keeps a signed sign-in key (s),
    the open project (p) and section (sec), so the user comes straight back to where they were."""
    qp = st.query_params
    if not ss.get("user") and qp.get("s"):
        try:
            ss.user = store.get_user(store.read_token(qp["s"]))
        except (store.AuthError, store.NotFound):
            st.query_params.clear(); return
    if ss.get("user") and qp.get("p") and not ss.get("pid") and not ss.get("_restored"):
        ss._restored = True
        try:
            open_project(qp["p"]); ss.view = "project"; ss.section = qp.get("sec", "Decision")
        except store.NotFound:
            del st.query_params["p"]
    if ss.get("user") and qp.get("v") == "new" and not ss.get("view"):
        ss.view = "new"


def sync_address():
    """Write where the user is into the page address (only ids, never data)."""
    want = {"s": st.query_params.get("s")}
    v = ss.get("view", "dashboard")
    if v == "project" and ss.get("pid"):
        want.update(p=ss.pid, sec=ss.get("section", "Decision"))
    elif v == "new":
        want["v"] = "new"
    want = {k: x for k, x in want.items() if x}
    if dict(st.query_params) != want:
        st.query_params.from_dict(want)


restore_session()


def guarded(fn, *args):
    """Show a friendly message instead of a stack trace; keep the details for debugging."""
    try:
        fn(*args)
    except store.NotFound:
        st.error("That item was not found or belongs to another account.")
        for k in ("pid", "state", "result"): ss.pop(k, None)
    except Exception as e:  # noqa: BLE001
        log.exception("Page error")
        st.error(f"Something went wrong on this page: {e}")
        with st.expander("Technical details"):
            st.code(traceback.format_exc())


if not ss.get("user"):
    guarded(auth.page)
else:
    try:
        store.get_user(user_id())
    except store.NotFound:
        auth.logout()
    with st.sidebar:
        st.markdown(f"### 🌿 ValidateUAE\n<span class='muted'>Signed in as **{esc(ss.user['username'])}**</span>", unsafe_allow_html=True)
        if st.button("My projects", width="stretch", type="primary" if ss.get("view", "dashboard") == "dashboard" else "secondary"):
            ss.view = "dashboard"; st.rerun()
        if st.button("➕ New project", width="stretch", type="primary" if ss.get("view") == "new" else "secondary"):
            ss.view = "new"; ss.pop("ob", None); st.rerun()
        if ss.get("pid") and ss.get("result"):
            st.divider()
            st.markdown(f"**{esc(ss.get('pname', 'Project'))}** {pill_status(ss.result['decision']['code'])}", unsafe_allow_html=True)
            if ss.get("view") != "project" and st.button("Back to this project", width="stretch"):
                ss.view = "project"; st.rerun()
            names = list(sections.SECTIONS)
            cur = ss.get("section", "Decision")
            choice = st.radio("Project sections", names, index=names.index(cur) if cur in names else 0, label_visibility="collapsed")
            if choice != cur:
                ss.section = choice; ss.view = "project"; st.rerun()
        st.divider()
        if st.button("Glossary of terms", width="stretch"):
            ss.view = "glossary"; st.rerun()
        if st.button("Log out", width="stretch"):
            auth.logout()

    view = ss.get("view", "dashboard")
    if ss.get("flash"): st.success(ss.pop("flash"))
    if view == "new":
        guarded(onboarding.page)
    elif view == "glossary":
        guarded(glossary.page)
    elif view == "project" and ss.get("pid") and ss.get("result"):
        guarded(sections.render, ss.get("section", "Decision"))
    else:
        guarded(dashboard.page)

if ss.get("user"):
    sync_address()

st.markdown('<p class="muted" style="margin-top:40px;font-size:12.5px">ValidateUAE is decision support, not financial advice. Typical figures and the simulated population are illustrative; '
            'simulated and AI-generated figures are never real customer behaviour.</p>', unsafe_allow_html=True)
