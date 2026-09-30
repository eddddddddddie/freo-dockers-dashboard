"""Login gate for the whole app, with an optional 7-day "keep me signed in".

The username and password come from APP_USERNAME / APP_PASSWORD (environment
or Streamlit secrets), never from the code: the repo is public. If they are
not configured the app stays locked.

Staying signed in: after a successful sign-in the browser gets a cookie
holding a signed token (a random session id, the username and an expiry,
HMAC-SHA256). On a new visit, refresh or opened link, a valid unexpired token
signs the user in without the form. The signing key is APP_COOKIE_SECRET if
set, otherwise derived from APP_PASSWORD, so changing the password signs
everyone out. The cookie is set from JavaScript (Streamlit can't set cookies
from Python), so it can't be HttpOnly; it is SameSite=Lax and Secure on https.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

import streamlit as st
import streamlit.components.v1 as components

import settings

MAX_TRIES = 5        # failed attempts before a pause
LOCKOUT_SECONDS = 30
COOKIE = "freo_coach_session"
REMEMBER_DAYS = 7

_cookie = components.declare_component(
    "cookie", path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "components", "cookie"))


def _matches(given, expected):
    return hmac.compare_digest(given.encode(), expected.encode())


# ---- signed tokens ------------------------------------------------------------
def _key():
    secret = settings.get("APP_COOKIE_SECRET")
    if secret:
        return secret.encode()
    pw = settings.get("APP_PASSWORD") or ""
    return hashlib.sha256(("freo-coach-view-remember|" + pw).encode()).digest()


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_token(user, days=REMEMBER_DAYS, sid=None, now=None):
    """A signed token: base64url(json payload) + "." + base64url(hmac)."""
    payload = {"u": user, "sid": sid or secrets.token_urlsafe(16),
               "exp": int((now or time.time()) + days * 86400)}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_key(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token, now=None):
    """The token's payload if its signature is valid, it hasn't expired and it
    names the configured user; otherwise None."""
    try:
        body, sig = str(token).split(".", 1)
        good = _b64(hmac.new(_key(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, TypeError):
        return None
    user = settings.get("APP_USERNAME")
    if payload.get("exp", 0) < (now or time.time()) or not user or payload.get("u") != user:
        return None
    return payload


# ---- cookie ---------------------------------------------------------------------
def _send_cookie(action, value="", max_age=0):
    _cookie(action=action, name=COOKIE, value=value, max_age=max_age,
            nonce=secrets.token_hex(8), key=f"cookie_{action}", default=None)


def cookie_sync():
    """Render any pending cookie change (after sign-in, or on sign-out)."""
    pending = st.session_state.pop("cookie_pending", None)
    if pending:
        _send_cookie(*pending)


def _sign_in(payload):
    st.session_state["authed"] = True
    st.session_state["sid"] = payload["sid"]
    st.session_state.pop("tries", None)


def require_login():
    """Sign in from a valid cookie, or show the login form and stop the script
    until the user is signed in."""
    if st.session_state.get("authed"):
        return
    if not st.session_state.get("signed_out"):
        payload = verify_token(st.context.cookies.get(COOKIE, ""))
        if payload:
            _sign_in(payload)
            st.session_state["restored"] = True   # the app reloads this session's chat
            return
    user, pw = settings.get("APP_USERNAME"), settings.get("APP_PASSWORD")
    cookie_sync()  # a sign-out's "clear the cookie" is rendered here
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
            remember = st.checkbox(f"Keep me signed in for {REMEMBER_DAYS} days", value=True)
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            if time.time() < locked_until:
                st.error(f"Too many attempts. Try again in {int(locked_until - time.time()) + 1} s.")
            elif _matches(u.strip(), user) and _matches(p, pw):
                token = make_token(user)
                _sign_in(verify_token(token))
                st.session_state.pop("signed_out", None)
                if remember:
                    st.session_state["cookie_pending"] = ("set", token, REMEMBER_DAYS * 86400)
                st.rerun()
            else:
                tries = st.session_state.get("tries", 0) + 1
                st.session_state["tries"] = tries
                if tries >= MAX_TRIES:
                    st.session_state["locked_until"] = time.time() + LOCKOUT_SECONDS
                    st.session_state["tries"] = 0
                st.error("Incorrect username or password.")
    st.stop()


def sign_out():
    """End this session and clear the cookie; the login page shows next."""
    for k in ("authed", "sid", "messages", "restored"):
        st.session_state.pop(k, None)
    st.session_state["signed_out"] = True  # the old cookie is ignored until it's cleared
    st.session_state["cookie_pending"] = ("clear",)
    st.rerun()
