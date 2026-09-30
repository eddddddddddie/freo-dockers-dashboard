"""Sizes the one-screen layout to the browser window.

A tiny custom component (components/viewport) reports the window's width and
height; every fixed pixel height in the layout is derived from that, so the
view fills a laptop, a desktop monitor or a TV without scrolling. Until the
first reading arrives (the first run), the 1440x790 design size is used.
"""

import os

import streamlit as st
import streamlit.components.v1 as components

_viewport = components.declare_component(
    "viewport", path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "components", "viewport"))

DESIGN_H = 790          # usable height the fixed sizes were tuned for (1440x900 laptop)
MIN_H, MAX_H = 660, 1500


PHONE_W = 700           # narrower than this gets the phone layout (one scrolling column)


def window_size():
    """(width, height) of the browser window, or the design size until known.
    Until a size has arrived the component is asked to send one even if this
    browser tab already sent it (a new session in the same tab)."""
    known = "window_size" in st.session_state
    v = _viewport(key="viewport", default=None, need=not known)
    if isinstance(v, dict) and v.get("h"):
        st.session_state["window_size"] = (int(v["w"]), int(v["h"]))
    return st.session_state.get("window_size", (1440, DESIGN_H))


def size_known():
    return "window_size" in st.session_state


def is_phone(width):
    return width < PHONE_W


def phone_sizes(height, width):
    """Sizes for the phone layout: the page scrolls, so charts get a fixed,
    readable height and the chat history about half the screen."""
    return {"phone": True, "mid": 250, "bot": 300, "form_rows": 10,
            "panel": None, "history": max(300, int(height * 0.55)), "width": width}


def sizes(height, width=1440):
    """Pixel sizes for the current window. Extra height is shared between the
    two chart rows; the chat panel grows with the window. Below about 1400px
    wide some card titles and controls wrap onto a second line, so the charts
    give up that height too."""
    h = max(MIN_H, min(MAX_H, height))
    wrap = max(0, min(100, int((1400 - width) * 0.65)))
    extra = h - DESIGN_H - wrap
    mid = int(238 + 0.45 * extra)
    bot = int(262 + 0.55 * extra)
    return {
        "phone": False,
        "mid": mid,
        "bot": bot,
        "panel": int(722 + extra + wrap),
        "history": int(570 + extra + wrap),
        # Player form rows that fit the bottom card at 12px labels, after the
        # card's takeaway line (about 18px a row).
        "form_rows": max(7, min(24, int((bot - 18 - 68) / 18))),
    }
