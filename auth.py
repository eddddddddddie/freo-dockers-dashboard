"""Login gate for the whole app.

Two modes, picked from the secrets:

Google (when an [auth] section with Google's client_id etc. is configured):
anyone with a Google account can sign in, through Streamlit's built-in
st.login. Google verifies the email address and handles the password, 2FA
and resets, so the app never sees or stores a password; only a Google email
marked verified is accepted. Streamlit keeps the sign-in in its own signed,
HttpOnly identity cookie. Each person is identified by a hash of their email,
so Wharf-ai limits and saved chats are per person.

Username and password (the fallback, e.g. local development and CI): the
username and password come from APP_USERNAME / APP_PASSWORD (environment or
Streamlit secrets), never from the code: the repo is public. If neither mode
is configured the app stays locked.

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


# ---- Google ---------------------------------------------------------------------
GOOGLE_KEYS = ("redirect_uri", "cookie_secret", "client_id", "client_secret",
               "server_metadata_url")


def google_configured():
    """True when the secrets hold a complete [auth] section for st.login."""
    try:
        section = st.secrets.get("auth") or {}
        return all(section.get(k) for k in GOOGLE_KEYS)
    except Exception:  # no secrets file
        return False


def person_id(email):
    """A stable, non-reversible id for one person (their email, hashed)."""
    return "g:" + hashlib.sha256(email.strip().lower().encode()).hexdigest()[:24]


def current_user():
    """{"email", "name"} for the signed-in person, or None (password mode)."""
    return st.session_state.get("user")


def _require_google():
    if st.user.is_logged_in:
        email = st.user.get("email")
        if not email or st.user.get("email_verified") is False:
            _login_page("Your Google account's email address isn't verified, so it can't be "
                        "used here. Verify it with Google, then sign in again.", google=True,
                        error=True)
        if st.session_state.get("user", {}).get("email") != email:
            st.session_state["user"] = {"email": email, "name": st.user.get("name") or email}
            st.session_state["authed"] = True
            st.session_state["sid"] = person_id(email)
            st.session_state["restored"] = True  # carry on this person's saved chat
        return
    _login_page(google=True)


def _splash():
    """The sign-in screen (theme.login_hero): the page in purple, the headline,
    then the sign-in under it. Returns the container to draw the form in."""
    import theme
    theme.login_hero()
    return st.container(key="login_card")


def _login_page(message=None, google=False, error=False):
    with _splash():
        if message:
            (st.error if error else st.info)(message)
        if google:
            if st.user.is_logged_in:
                if st.button("Sign out", width="stretch"):
                    st.logout()
            elif st.button("Sign in with Google", type="primary", width="stretch",
                           icon=":material/login:"):
                st.login()
            st.caption("Anyone with a Google account can sign in. The app uses your name and "
                       "email only to keep your Wharf-ai questions and chat separate; Google "
                       "handles your password.")
    st.stop()


def require_login():
    """Sign in with Google (if configured), from a valid cookie, or with the
    username and password; otherwise show the sign-in page and stop the script."""
    if google_configured():
        _require_google()
        return
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
    with _splash():
        if not user or not pw:
            st.error("Login is not configured. Set APP_USERNAME and APP_PASSWORD in the "
                     "app secrets (or environment), then reboot the app.")
            st.stop()
        locked_until = st.session_state.get("locked_until", 0)
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            remember = st.checkbox(f"Keep me signed in for {REMEMBER_DAYS} days", value=True)
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
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
    """End this session; the sign-in page shows next."""
    if google_configured():
        for k in ("authed", "sid", "messages", "restored", "user"):
            st.session_state.pop(k, None)
        st.logout()  # clears Streamlit's identity cookie and reruns
        return
    for k in ("authed", "sid", "messages", "restored"):
        st.session_state.pop(k, None)
    st.session_state["signed_out"] = True  # the old cookie is ignored until it's cleared
    st.session_state["cookie_pending"] = ("clear",)
    st.rerun()
