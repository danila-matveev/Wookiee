"""Config loads required env vars."""
from __future__ import annotations

import os
import pytest


def test_config_loads_api_key(monkeypatch):
    monkeypatch.setenv("INFLUENCER_CRM_API_KEY", "test-secret")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")

    # Force reload — config caches at import time
    import importlib
    from services.influencer_crm import config
    importlib.reload(config)

    assert config.API_KEY == "test-secret"
    assert config.DB_DSN.startswith("postgresql+psycopg2://u:p@h:")


def test_config_raises_on_missing_api_key(monkeypatch):
    monkeypatch.delenv("INFLUENCER_CRM_API_KEY", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")

    import importlib
    from services.influencer_crm import config
    with pytest.raises(RuntimeError, match="INFLUENCER_CRM_API_KEY"):
        importlib.reload(config)
