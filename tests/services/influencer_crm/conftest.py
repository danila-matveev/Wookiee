"""Test fixtures for influencer_crm API."""
from __future__ import annotations

import importlib
import os

import pytest
from fastapi.testclient import TestClient

# Force a known API key BEFORE test modules import config.
# `_set_api_key` fixture below still runs (and force-overrides if a dev
# shell pre-set a different value) — this top-level line just guarantees
# config.py can import successfully during collection, even on CI / fresh
# checkouts where the .env has no INFLUENCER_CRM_API_KEY.
os.environ.setdefault("INFLUENCER_CRM_API_KEY", "test-key-123")


@pytest.fixture(scope="session", autouse=True)
def _set_api_key():
    """Force a known API key for all tests, restore env on teardown."""
    original = os.environ.get("INFLUENCER_CRM_API_KEY")
    os.environ["INFLUENCER_CRM_API_KEY"] = "test-key-123"
    # Re-import config so module-level constants pick up the test key.
    # (importlib.reload alone won't update the parent package attribute,
    # but for pytest's collection order this is sufficient — config is
    # only read at module import in app/auth code, and we reload before
    # any of those imports happen.)
    from services.influencer_crm import config

    importlib.reload(config)
    yield
    if original is None:
        os.environ.pop("INFLUENCER_CRM_API_KEY", None)
    else:
        os.environ["INFLUENCER_CRM_API_KEY"] = original


@pytest.fixture()
def client():
    from services.influencer_crm.app import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth():
    """Headers dict with valid API key."""
    return {"X-API-Key": "test-key-123"}
