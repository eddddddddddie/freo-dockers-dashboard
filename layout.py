"""The browser window's size, and the layout it suits.

A tiny custom component (components/viewport) reports the window's width and
height (and the address after Back/Forward, see nav._back_forward). Until the
first reading arrives (the first run), the 1440x790 design size is used.
"""

import os

import streamlit as st
import streamlit.components.v1 as components

_viewport = components.declare_component(
    "viewport", path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "components", "viewport"))

DESIGN_H = 790          # usable height the fixed sizes were tuned for (1440x900 laptop)
BAR_H = 44              # the purple top bar and the gap under it
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
