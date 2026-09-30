"""Wharf-ai: the grounded chat assistant.

Claude answers by calling the data tools in wharf_tools.py, which run fixed
pandas queries over the loaded CSVs, so every number it quotes was computed,
not recalled or added up in its head. Box-score data shows what happened, not
zones or structures, so it is told to say when a question needs data we do
not have.

Reads ANTHROPIC_API_KEY from the environment or Streamlit secrets (never
hard-coded). Keys that are not scoped to one workspace also need
ANTHROPIC_WORKSPACE_ID (wrkspc_...). Optional ANTHROPIC_BASE_URL for
non-default API hosts, and FREO_CHAT_MODEL to override the model.
"""

import json
import os
import re

import streamlit as st

import data as D
import settings
import wharf_tools as W

MODEL = os.environ.get("FREO_CHAT_MODEL", "claude-sonnet-5-5")
# "low" is the documented starting point for chat on Sonnet 5.5: it skips
# thinking on most simple requests. Measured on Wharf-ai questions: median 4.7 s
# to an answer (worst 8.8 s) against 7.6 s (worst 14.8 s) at "medium".
EFFORT = os.environ.get("FREO_CHAT_EFFORT", "low")
MAX_TOKENS = 16000
MAX_STEPS = 10           # model requests per question before we stop the loop
# A stalled connection fails in about a minute instead of the SDK's default ten.
# The read timeout is the longest gap between streamed events (the API sends
# pings while the model thinks), not a limit on the whole answer.
READ_TIMEOUT = 60
CONNECT_TIMEOUT = 10
MAX_RETRIES = 2          # the SDK retries overloaded or dropped requests, with backoff
# Server-side refusal fallback (Claude API): a declined request is retried on
# a fallback model inside the same call.
BETAS = ["server-side-fallback-2026-07-01"]

HAS_EXT = os.path.exists(D.TEAM_EXT_CSV) and os.path.exists(D.PLAYER_EXT_CSV)
UNAVAILABLE = (
    ("" if HAS_EXT else "metres gained, pressure acts, score involvements, ")
    + "shot locations, expected score (xG), player positions or zones, and "
    "anything about team structure or set-ups"
)
SOURCES = (
    "afltables.com box scores, plus Champion Data advanced stats from the AFL match "
    "centre (pressure acts, metres gained, score involvements, centre vs stoppage "
    "clearances, intercepts, disposal efficiency, turnovers)"
    if HAS_EXT else "afltables.com box scores"
)

SYSTEM_INTRO = f"""You are Wharf-ai, the analyst for a Fremantle Dockers (AFL) performance dashboard.
You answer tactical and statistical questions about Fremantle's 2025 and 2026 seasons from
the dashboard's data ({SOURCES}). Where both sources carry a stat, the AFL Tables figure is used.

How to answer:
- Use the data tools for every number you state. Call them as many times as you need,
  including several in parallel. Do not quote a figure from memory or work one out in
  your head beyond restating tool output (a simple difference of two tool numbers is fine;
  say which two).
- If a tool returns an error, fix the call and try again.
- If a question needs data we do not have, say so plainly. We do NOT have: {UNAVAILABLE}.
  Box-score data shows what happened, not why or where on the ground.
- Correlations and splits are associations, not causes; say so when it matters.
- Goal accuracy uses team totals (team behinds include rushed behinds; summed player
  behinds do not).
- Substitute markers are blank for all 2026 games (the source did not record them), so
  do not infer subs from low game time; ruckmen routinely play around 45 percent.
- Neither season has a Round 1, and round labels are the source's own (finals are
  EF, QF, SF, PF, GF).
- When a trend or ranking is easier to see than read, call show_chart (at most 2 per
  answer); the app draws it from the data below your answer text, so refer to it as
  "the chart below".
- End every answer with one last line, in exactly this form and nothing after it:
  FOLLOWUPS: <question> | <question> | <question>
  Three short follow-up questions (under 10 words each) the coach might ask next, answerable
  from this data and different from what was just asked. Plain text, no formatting.
- Keep answers short for a coach reading a side panel: lead with the answer, then the few
  numbers that support it. Use short bullet lists rather than tables. Do not use em dashes.
"""


@st.cache_data
def system_text():
    """The stable, cached part of the system prompt: rules, data schema and each
    season's headline record."""
    team = D.load_team()
    lines = [SYSTEM_INTRO, "DATA AVAILABLE TO THE TOOLS", W.describe(), "", "HEADLINES"]
    for season in D.seasons(team):
        rec = D.record(D.team_season(team, season))
        lines.append(f"{season}: {rec['wins']}-{rec['losses']} from {rec['games']} games, "
                     f"avg margin {rec['margin']:+.1f}.")
    return "\n".join(lines)


def get_client():
    """Return an Anthropic client, or None if the key or SDK is unavailable."""
    api_key = settings.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    kwargs = {"api_key": api_key, "max_retries": MAX_RETRIES,
              "timeout": anthropic.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT)}
    workspace_id = (
        settings.get("ANTHROPIC_WORKSPACE_ID")
        or settings.get("ANTHROPIC_AWS_WORKSPACE_ID")
    )
    if workspace_id:
        kwargs["default_headers"] = {"anthropic-workspace-id": workspace_id}
    base_url = settings.get("ANTHROPIC_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return anthropic.Anthropic(**kwargs)


def _tool_input(block):
    """Tool inputs stream eagerly, so the API does not validate them; make sure
    we have a JSON object before running anything."""
    args = block.input
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return None
    return args if isinstance(args, dict) else None


MARKER = "FOLLOWUPS:"


def parse_followups(text):
    """'a? | b? | c?' -> up to three clean questions."""
    parts = [re.sub(r"^[\s*_\-\d.)]+|[\s*_]+$", "", p) for p in text.split("|")]
    return [p for p in parts if 3 < len(p) < 120][:3]


def _hold_back_marker(chunks, on_followups):
    """Pass answer text through, but strip the trailing FOLLOWUPS line and hand
    it to on_followups. Holds back a few characters so a marker split across
    chunks is still caught."""
    buf, capturing, tail = "", False, ""
    for chunk in chunks:
        if capturing:
            tail += chunk
            continue
        buf += chunk
        i = buf.find(MARKER)
        if i >= 0:
            out, tail, capturing = buf[:i].rstrip(" *_\n"), buf[i + len(MARKER):], True
            buf = ""
            if out:
                yield out
            continue
        safe = len(buf) - (len(MARKER) - 1)
        if safe > 0:
            yield buf[:safe]
            buf = buf[safe:]
    if buf and not capturing:
        yield buf
    if on_followups:
        on_followups(parse_followups(tail.strip().splitlines()[0]) if tail.strip() else [])


def stream_answer(client, current_season, history, opening=None, on_tool=None,
                  on_chart=None, focus=None, on_followups=None, on_usage=None, on_step=None):
    """Yield answer text (without the FOLLOWUPS line); see _stream_answer.
    on_usage(usage) receives each model request's token usage."""
    yield from _hold_back_marker(
        _stream_answer(client, current_season, history, opening, on_tool, on_chart, focus,
                       on_usage, on_step),
        on_followups)


def friendly_error(exc):
    """A short message for an API failure, or None to show the raw error."""
    try:
        import anthropic
    except ImportError:
        return None
    if isinstance(exc, anthropic.APITimeoutError):
        return "Wharf-ai took too long to respond. Please ask again."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Wharf-ai couldn't reach the Claude API. Check the connection and ask again."
    if isinstance(exc, (anthropic.OverloadedError, anthropic.RateLimitError,
                        anthropic.InternalServerError, anthropic.ServiceUnavailableError)):
        return "The Claude API is busy right now. Wait a few seconds and ask again."
    return None


def _stream_answer(client, current_season, history, opening=None, on_tool=None,
                   on_chart=None, focus=None, on_usage=None, on_step=None):
    """Yield answer text as it streams, running tool calls in between.

    history: prior turns as plain text ({"role", "content"}), ending with the
    user's question. Within one question the message list is append-only and
    each assistant turn is passed back whole (thinking and tool_use blocks
    included), as preserved thinking requires. on_tool(name, args) is called
    before each tool runs, for a progress line in the UI; on_chart(fig) receives
    each chart the model asks for. focus: what the user is looking at (a match).
    on_step(n) is called when model request n (0, 1, ...) starts, so the UI can
    show that work is moving while the model thinks.
    """
    note = f"The user is currently viewing the {current_season} season."
    if focus:
        note += f" They are looking at one match: {focus}."
    if opening:
        note += (" The panel shows these insights in rotation (computed from the data), "
                 f"which the user may ask about: {opening}")
    # Tools render before system, so this breakpoint caches tools + rules + schema.
    system = [
        {"type": "text", "text": system_text(), "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": note},
    ]
    # Only role and content go to the API (history entries may also carry charts).
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    wrote_text = False
    for step in range(MAX_STEPS):
        if on_step:
            on_step(step)
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            output_config={"effort": EFFORT},
            system=system,
            tools=W.TOOLS,
            messages=messages,
            betas=BETAS,
            fallbacks="default",
        ) as stream:
            if wrote_text:
                yield "\n\n"
            for text in stream.text_stream:
                wrote_text = True
                yield text
            response = stream.get_final_message()
        if on_usage:
            on_usage(response.usage)

        if response.stop_reason == "refusal":
            yield "\n\nWharf-ai can't help with that one."
            return
        if response.stop_reason == "max_tokens":
            yield "\n\n(Answer cut short: it hit the length limit.)"
            return
        if response.stop_reason != "tool_use":
            return

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            args = _tool_input(block)
            if args is None:
                text, is_error = "INVALID_JSON: tool input was not a JSON object. Retry.", True
            else:
                if on_tool:
                    on_tool(block.name, args)
                text, is_error, fig = W.run(block.name, args)
                if fig is not None and on_chart:
                    on_chart(fig)
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": text, "is_error": is_error})
        # All results for this step go back in one user message.
        messages.append({"role": "user", "content": results})

    yield "\n\n(Stopped after too many calculation steps. Try a narrower question.)"
