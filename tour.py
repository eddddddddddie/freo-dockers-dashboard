"""First-visit guided tour (components/tour): a step-by-step spotlight on each
part of the Coach View, using driver.js. It runs once per browser after the
first sign-in and again whenever `replay()` is called (Deep dives -> App tour).
"""

import os
import time

import streamlit as st
import streamlit.components.v1 as components

_tour = components.declare_component(
    "tour", path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "components", "tour"))


def show():
    """Render the (invisible) tour component; it decides whether to run."""
    _tour(force=st.session_state.get("tour_force"), key="tour", default=None)


def replay():
    st.session_state["tour_force"] = str(time.time())
