"""Config loads required env vars."""
from __future__ import annotations

import sys

import pytest


def _evict_config() -> None:
    """Remove cached config module so the next import re-executes its body."""
    sys.modules.pop("services.influencer_crm.config", None)
    pkg = sys.modules.get("services.influencer_crm")
    if pkg is not None:
        pkg.__dict__.pop("config", None)


def test_config_loads_api_key(monkeypatch):
    monkeypatch.setenv("INFLUENCER_CRM_API_KEY", "test-secret")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")

    _evict_config()

    from services.influencer_crm import config

    assert config.API_KEY == "test-secret"
    assert config.DB_DSN.startswith("postgresql+psycopg2://u:p@h:")


def test_config_raises_on_missing_api_key(monkeypatch):
    monkeypatch.delenv("INFLUENCER_CRM_API_KEY", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")

    _evict_config()

    with pytest.raises(RuntimeError, match="INFLUENCER_CRM_API_KEY"):
        from services.influencer_crm import config  # noqa: F401
