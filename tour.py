"""Guided tour (components/tour): a step-by-step spotlight on each part of the
Coach View, using driver.js. On a browser's first sign-in a small prompt points
at the ? button ("New here? Take a one-minute tour"); the tour itself runs from
there, or whenever `replay()` is called (the ? button in the header).
"""

import os
import time

import streamlit as st
import streamlit.components.v1 as components

_tour = components.declare_component(
    "tour", path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "components", "tour"))


def show(phone=False):
    """Render the (invisible) tour component; it decides whether to run.
    phone: the shorter tour for the phone layout."""
    _tour(force=st.session_state.get("tour_force"), phone=phone, key="tour", default=None)


def replay():
    st.session_state["tour_force"] = str(time.time())
