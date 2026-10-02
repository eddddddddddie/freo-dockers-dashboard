"""Shared test setup: run from the repo root, with test-only login secrets."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# Streamlit copies .streamlit/secrets.toml into the environment when it starts, so
# a local run must sign in with the login from that file. In CI there is no
# secrets file and the test-only login below is used.
try:
    import tomllib
    with open(os.path.join(ROOT, ".streamlit", "secrets.toml"), "rb") as f:
        _local = tomllib.load(f)
except (FileNotFoundError, ValueError):
    _local = {}
for _key, _test_value in (("APP_USERNAME", "ci-user"), ("APP_PASSWORD", "ci-pass")):
    os.environ[_key] = str(_local.get(_key) or os.environ.get(_key) or _test_value)

# Never the live usage database (its URL may be in the local secrets file): the
# usage log uses a temporary SQLite file, or a test database that
# tests/test_usage_pg.py switches on. Inherited by the app the UI tests start.
os.environ["FREO_TESTS"] = "1"
os.environ.pop("USAGE_TEST_DB_ACTIVE", None)


def pytest_configure(config):
    config.addinivalue_line("markers", "ui: browser tests (need Playwright and a browser)")
