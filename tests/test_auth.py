"""Stay-signed-in tokens: only a genuine, unexpired token for the configured
user signs anyone in."""

import base64
import json
import time

import pytest

import auth
import settings


@pytest.fixture
def config(monkeypatch):
    values = {"APP_USERNAME": "coach", "APP_PASSWORD": "pw-one", "APP_COOKIE_SECRET": None}
    monkeypatch.setattr(settings, "get", lambda name: values.get(name))
    return values


def test_a_fresh_token_is_accepted(config):
    payload = auth.verify_token(auth.make_token("coach"))
    assert payload and payload["u"] == "coach" and payload["sid"]


def test_tampered_or_forged_tokens_are_rejected(config):
    body, sig = auth.make_token("coach").split(".")
    assert auth.verify_token(body + "." + sig[::-1]) is None
    forged = base64.urlsafe_b64encode(json.dumps(
        {"u": "coach", "sid": "x", "exp": 9_999_999_999}).encode()).rstrip(b"=").decode()
    assert auth.verify_token(forged + "." + sig) is None
    assert auth.verify_token("") is None and auth.verify_token("junk") is None


def test_expired_tokens_are_rejected(config):
    old = auth.make_token("coach", now=time.time() - (auth.REMEMBER_DAYS + 1) * 86400)
    assert auth.verify_token(old) is None


def test_changing_the_password_signs_everyone_out(config):
    token = auth.make_token("coach")
    config["APP_PASSWORD"] = "pw-two"
    assert auth.verify_token(token) is None


def test_a_token_for_another_user_is_rejected(config):
    token = auth.make_token("coach")
    config["APP_USERNAME"] = "someone-else"
    assert auth.verify_token(token) is None


def test_an_explicit_cookie_secret_is_used_when_set(config):
    config["APP_COOKIE_SECRET"] = "s3"
    token = auth.make_token("coach")
    config["APP_COOKIE_SECRET"] = "different"
    assert auth.verify_token(token) is None


def test_person_id_is_stable_case_insensitive_and_not_the_email():
    a = auth.person_id("Coach.Name@Example.com")
    assert a == auth.person_id(" coach.name@example.com ")
    assert a != auth.person_id("other@example.com")
    assert "example" not in a and a.startswith("g:")


def test_google_mode_needs_a_complete_auth_section(monkeypatch):
    import streamlit as st

    class Secrets(dict):
        def get(self, k, default=None):
            return dict.get(self, k, default)
    monkeypatch.setattr(st, "secrets", Secrets(auth={"client_id": "x"}))
    assert not auth.google_configured()
    full = {k: "x" for k in auth.GOOGLE_KEYS}
    monkeypatch.setattr(st, "secrets", Secrets(auth=full))
    assert auth.google_configured()
