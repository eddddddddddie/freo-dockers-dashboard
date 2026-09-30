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


DESKTOP_W, DESKTOP_H = 1280, 600   # the one-screen layout needs at least this much room
SPLIT_W = 1000                     # landscape tablets from here keep Wharf-ai at the side


def mode(width, height):
    """Which layout suits the window.

    phone:   narrower than PHONE_W; one scrolling column, Wharf-ai first.
    desktop: DESKTOP_W x DESKTOP_H or more; everything on one screen.
    split:   a landscape tablet (SPLIT_W or wider, landscape, DESKTOP_H or
             taller); the dashboard scrolls, cards two to a row, with Wharf-ai
             pinned down the right.
    stack:   everything else (portrait tablets, landscape phones, small windows);
             Wharf-ai first, then the dashboard with cards two to a row.
    """
    if width < PHONE_W:
        return "phone"
    if width >= DESKTOP_W and height >= DESKTOP_H:
        return "desktop"
    if width >= SPLIT_W and height >= DESKTOP_H and width > height:
        return "split"
    return "stack"


def is_phone(width):
    return width < PHONE_W


def scroll_sizes(mode_, height, width):
    """Sizes for the scrolling layouts (phone, stack, split): charts get a fixed,
    readable height. With Wharf-ai at the top, its chat scrolls in about half
    the screen; at the side (split) the panel is as tall as the window."""
    sz = {"phone": mode_ == "phone", "mode": mode_, "width": width, "form_rows": 10,
          "mid": 250 if mode_ == "phone" else 270, "bot": 300 if mode_ == "phone" else 320,
          "panel": None, "history": max(300, int(height * 0.55))}
    if mode_ == "split":
        sz["panel"] = height - 44          # leaves room for the page's bottom padding
        sz["history"] = height - 44 - 150   # header, chat box and padding
    return sz


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
        "mode": "desktop",
        "mid": mid,
        "bot": bot,
        "panel": int(722 + extra + wrap),
        "history": int(570 + extra + wrap),
        # Player form rows that fit the bottom card at 12px labels, after the
        # card's takeaway line (about 18px a row).
        "form_rows": max(7, min(24, int((bot - 18 - 68) / 18))),
    }
