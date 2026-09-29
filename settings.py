"""Read a setting from the environment, then Streamlit secrets. Secrets
(API keys, the login) are never hard-coded: set them in the environment,
.streamlit/secrets.toml locally (gitignored), or the app's Secrets on
Streamlit Cloud."""

import os

import streamlit as st


def get(name):
    value = os.environ.get(name)
    if not value:
        try:
            value = st.secrets.get(name)
        except Exception:  # no secrets file configured
            value = None
    return str(value).strip() if value else None
