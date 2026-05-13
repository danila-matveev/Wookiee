"""Tests for schema validation that runs at API startup.

We assert that `_validate_schema` queries information_schema and raises
RuntimeError when required telemost.meetings columns are missing — so a
container that boots against an un-migrated DB fails loudly instead of
quietly crashing in worker SQL hours later.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from services.telemost_recorder_api import app as app_module


class _FakeConn:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.queries: list[str] = []

    async def fetch(self, query: str) -> list[dict[str, Any]]:
        self.queries.append(query)
        return self._rows


class _FakePool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._conn = _FakeConn(rows)

    def acquire(self):
        conn = self._conn

        @asynccontextmanager
        async def _cm():
            yield conn

        return _cm()


@pytest.mark.asyncio
async def test_validate_schema_passes_on_complete_schema(monkeypatch):
    expected = app_module._EXPECTED_MEETINGS_COLUMNS
    rows = [{"column_name": c} for c in expected]
    pool = _FakePool(rows)

    async def fake_get_pool():
        return pool

    monkeypatch.setattr(app_module, "get_pool", fake_get_pool)
    await app_module._validate_schema()  # must not raise


@pytest.mark.asyncio
async def test_validate_schema_raises_on_missing_column(monkeypatch):
    expected = app_module._EXPECTED_MEETINGS_COLUMNS
    # Drop a critical column to simulate forgotten migration 004.
    partial = [{"column_name": c} for c in expected if c != "notion_page_id"]
    pool = _FakePool(partial)

    async def fake_get_pool():
        return pool

    monkeypatch.setattr(app_module, "get_pool", fake_get_pool)
    with pytest.raises(RuntimeError, match="missing"):
        await app_module._validate_schema()


@pytest.mark.asyncio
async def test_validate_schema_lists_all_missing_columns(monkeypatch):
    expected = app_module._EXPECTED_MEETINGS_COLUMNS
    missing = {"notion_page_id", "deleted_at"}
    partial = [{"column_name": c} for c in expected if c not in missing]
    pool = _FakePool(partial)

    async def fake_get_pool():
        return pool

    monkeypatch.setattr(app_module, "get_pool", fake_get_pool)
    with pytest.raises(RuntimeError) as exc_info:
        await app_module._validate_schema()
    msg = str(exc_info.value)
    for column in missing:
        assert column in msg
