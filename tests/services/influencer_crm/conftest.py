"""Test fixtures for influencer_crm API."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _set_api_key():
    """All API tests run with a known key. Real .env values are NOT loaded."""
    os.environ.setdefault("INFLUENCER_CRM_API_KEY", "test-key-123")
    # Force config re-import in case earlier test had different env
    import importlib
    from services.influencer_crm import config
    importlib.reload(config)


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
