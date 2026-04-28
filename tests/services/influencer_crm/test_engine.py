"""Engine connects + uses search_path = crm,public."""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("INFLUENCER_CRM_API_KEY", "test")


def test_engine_search_path_is_crm_public():
    """search_path must include `crm` so unqualified table names resolve."""
    from shared.data_layer.influencer_crm._engine import session_factory

    with session_factory() as session:
        result = session.execute(__import__("sqlalchemy").text("SHOW search_path")).scalar()
    # PG returns it like "crm, public"
    assert "crm" in result and "public" in result


def test_engine_runs_select_one():
    from sqlalchemy import text
    from shared.data_layer.influencer_crm._engine import session_factory

    with session_factory() as session:
        v = session.execute(text("SELECT 1")).scalar()
    assert v == 1
