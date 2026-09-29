"""Login gate for the whole app.

The username and password come from APP_USERNAME / APP_PASSWORD (environment
or Streamlit secrets), never from the code: the repo is public. If they are
not configured the app stays locked. Login lasts for the browser session.
"""

import hmac
import time

import streamlit as st

import settings

MAX_TRIES = 5        # failed attempts before a pause
LOCKOUT_SECONDS = 30


def _matches(given, expected):
    return hmac.compare_digest(given.encode(), expected.encode())


def require_login():
    """Show the login form and stop the script until the user is signed in."""
    if st.session_state.get("authed"):
        return
    user, pw = settings.get("APP_USERNAME"), settings.get("APP_PASSWORD")
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.markdown('<div class="login-head"><b>Fremantle Coach View</b>'
                    '<span>Sign in to continue</span></div>', unsafe_allow_html=True)
        if not user or not pw:
            st.error("Login is not configured. Set APP_USERNAME and APP_PASSWORD in the "
                     "app secrets (or environment), then reboot the app.")
            st.stop()
        locked_until = st.session_state.get("locked_until", 0)
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            if time.time() < locked_until:
                st.error(f"Too many attempts. Try again in {int(locked_until - time.time()) + 1} s.")
            elif _matches(u.strip(), user) and _matches(p, pw):
                st.session_state["authed"] = True
                st.session_state.pop("tries", None)
                st.rerun()
            else:
                tries = st.session_state.get("tries", 0) + 1
                st.session_state["tries"] = tries
                if tries >= MAX_TRIES:
                    st.session_state["locked_until"] = time.time() + LOCKOUT_SECONDS
                    st.session_state["tries"] = 0
                st.error("Incorrect username or password.")
    st.stop()
