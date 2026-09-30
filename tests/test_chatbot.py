"""Wharf-ai's client can't hang for minutes, API failures get a plain message,
and the FOLLOWUPS line is stripped from the answer (no API calls)."""

import anthropic
import httpx2

import chatbot as C


def test_client_has_a_timeout_and_retries(monkeypatch):
    monkeypatch.setattr(C.settings, "get", lambda k: "sk-test" if k == "ANTHROPIC_API_KEY" else None)
    client = C.get_client()
    assert client.max_retries == C.MAX_RETRIES
    assert client.timeout.read == C.READ_TIMEOUT and client.timeout.connect == C.CONNECT_TIMEOUT


def test_friendly_errors():
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    assert "too long" in C.friendly_error(anthropic.APITimeoutError(request=req))
    assert "couldn't reach" in C.friendly_error(anthropic.APIConnectionError(request=req))
    assert C.friendly_error(ValueError("something else")) is None


def test_followups_line_is_held_back():
    got = []
    chunks = ["Freo won 21.\n", "FOLLOW", "UPS: Who kicked most? | How were the finals?"]
    text = "".join(C._hold_back_marker(iter(chunks), got.extend))
    assert text == "Freo won 21." and got == ["Who kicked most?", "How were the finals?"]
