"""Navigation helpers shared by v2.py and the cards it reuses from views.py.

Streamlit won't let a control's value change after the control is drawn in
the same run, so a click that moves somewhere else queues the move (`go`) and
reruns; v2.apply reads it at the top of the next run, before any control is
drawn, and translates the old views (Match, Player, Scout) to places.
"""

from urllib.parse import parse_qsl

import streamlit as st


def go(**state):
    """Move from a reused card: go(view="Match", season=2026, game="GF")."""
    st.session_state["pending_nav"] = state
    st.rerun()


def _back_forward():
    """The address after a browser Back/Forward, if one just happened. The
    viewport component sends it: Streamlit's st.query_params keeps the old
    address on that rerun."""
    v = st.session_state.get("viewport")
    if not isinstance(v, dict) or not v.get("pop") or v["pop"] == st.session_state.get("_last_pop"):
        return None
    st.session_state["_last_pop"] = v["pop"]
    return dict(parse_qsl(str(v.get("search", "")).lstrip("?")))


def clicked(event):
    """The first clicked point of a chart selection event, or None."""
    try:
        points = event.selection["points"]
    except (AttributeError, KeyError, TypeError):
        return None
    return points[0] if points else None
