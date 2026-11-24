"""Log in and create an account. Passwords are stored as salted PBKDF2 hashes (app/store.py)."""
import os

import streamlit as st

from app import store
from ui.common import ss, chip


def page():
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.markdown(chip("ValidateUAE", "lavender"), unsafe_allow_html=True)
        st.title("Test a business idea against the UAE market before you spend on it")
        st.markdown('<p class="muted" style="font-size:17px">A guided validation workspace: describe the idea in four short steps, collect real evidence, '
                    'run cheap experiments and get a clear Launch, Test first, Pivot or Stop recommendation, explained in plain words.</p>', unsafe_allow_html=True)
        st.markdown('<div class="box"><b>What you get</b><ul class="muted" style="margin:6px 0 0 0">'
                    '<li>A ten-stage analysis with a customer-by-customer market simulation</li>'
                    '<li>An evidence ledger that keeps facts, estimates and simulations apart</li>'
                    '<li>A validation lab for hypotheses, interviews, surveys and landing pages</li>'
                    '<li>Three financial scenarios, break-even, cash runway and sensitivity</li>'
                    '<li>Monitoring of your real results against the forecast</li></ul></div>', unsafe_allow_html=True)
    with right:
        signup_ok = os.getenv("ALLOW_SIGNUP", "true").lower() != "false"
        tabs = st.tabs(["Log in", "Create account"] if signup_ok else ["Log in"])
        with tabs[0], st.form("login"):
            u = st.text_input("Username", autocomplete="username")
            p = st.text_input("Password", type="password", autocomplete="current-password")
            if st.form_submit_button("Log in", type="primary", width="stretch"):
                try:
                    ss.user = store.authenticate(u, p); remember(); st.rerun()
                except store.AuthError as e:
                    st.error(str(e))
        if signup_ok:
            with tabs[1], st.form("signup"):
                u = st.text_input("Choose a username", help="3-64 characters: letters, numbers, . _ @ -")
                p = st.text_input("Choose a password", type="password", help="At least 8 characters.")
                p2 = st.text_input("Repeat the password", type="password")
                if st.form_submit_button("Create account", type="primary", width="stretch"):
                    if p != p2:
                        st.error("The two passwords do not match.")
                    else:
                        try:
                            ss.user = store.create_user(u, p); remember(); st.rerun()
                        except store.AuthError as e:
                            st.error(str(e))
        st.caption(f"Projects are private to your account. Storage: {store.backend_name()}.")


def remember():
    """Keep the user signed in across page reloads for 7 days (a signed key in the page address)."""
    st.query_params.from_dict({"s": store.make_token(ss.user["id"], hours=24 * 7)})


def logout():
    for k in list(ss.keys()):
        del ss[k]
    st.query_params.clear()
    st.rerun()
