"""Tests for /api/marketing/sync endpoints (Task B.2.1).

Covers:
- POST /api/marketing/sync/{job_name}        — happy path returns 200 with sync_log_id
- GET  /api/marketing/sync/{job_name}/status — returns latest log row
- 404 for unknown job names (both verbs)
- Auth: 401 when X-API-Key missing/invalid
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# Ensure ANALYTICS_API_KEY is set BEFORE importing the app — the module-level
# CORS + router setup is fine without it, but the dependency reads via os.getenv
# on each request, so this just guarantees a stable value across the file.
os.environ.setdefault("ANALYTICS_API_KEY", "test-key")

from services.analytics_api.app import app  # noqa: E402

client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}


# -----------------------------------------------------------------------------
# 404 — unknown job
# -----------------------------------------------------------------------------
def test_trigger_sync_unknown_job_returns_404():
    r = client.post("/api/marketing/sync/unknown-job", headers=HEADERS)
    assert r.status_code == 404
    assert "Unknown job" in r.json().get("detail", "")


def test_status_unknown_job_returns_404():
    r = client.get("/api/marketing/sync/unknown-job/status", headers=HEADERS)
    assert r.status_code == 404


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
def test_trigger_sync_without_api_key_returns_401():
    r = client.post("/api/marketing/sync/search-queries")
    assert r.status_code == 401


def test_trigger_sync_with_wrong_api_key_returns_401():
    r = client.post(
        "/api/marketing/sync/search-queries",
        headers={"X-API-Key": "wrong-key"},
    )
    assert r.status_code == 401


# -----------------------------------------------------------------------------
# Happy path — POST
# -----------------------------------------------------------------------------
@patch("services.analytics_api.marketing.run_sync_subprocess")
@patch("services.analytics_api.marketing.create_sync_log_entry", return_value=42)
def test_trigger_sync_creates_log_and_returns_running(mock_create, mock_run):
    r = client.post("/api/marketing/sync/search-queries", headers=HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job_name"] == "search-queries"
    assert body["status"] == "running"
    assert body["sync_log_id"] == 42
    assert "started_at" in body
    mock_create.assert_called_once_with("search-queries")
    # BackgroundTasks runs after the response in TestClient — assert it was scheduled.
    mock_run.assert_called_once_with("search-queries", 42)


@patch("services.analytics_api.marketing.run_sync_subprocess")
@patch("services.analytics_api.marketing.create_sync_log_entry", return_value=77)
def test_trigger_sync_promocodes_job(mock_create, mock_run):
    r = client.post("/api/marketing/sync/promocodes", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["job_name"] == "promocodes"
    assert body["sync_log_id"] == 77
    mock_run.assert_called_once_with("promocodes", 77)


@patch("services.analytics_api.marketing.create_sync_log_entry", side_effect=RuntimeError("db down"))
def test_trigger_sync_db_failure_returns_500(_mock_create):
    r = client.post("/api/marketing/sync/search-queries", headers=HEADERS)
    assert r.status_code == 500
    assert "db down" in r.json().get("detail", "")


# -----------------------------------------------------------------------------
# Happy path — GET status
# -----------------------------------------------------------------------------
class _FakeCursor:
    def __init__(self, row):
        self._row = row
        self.execute_calls: list[tuple] = []

    def execute(self, *args, **_kwargs):
        self.execute_calls.append(args)
        return None

    def fetchone(self):
        return self._row

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, row):
        self._row = row
        self.cursors: list[_FakeCursor] = []

    def cursor(self):
        cur = _FakeCursor(self._row)
        self.cursors.append(cur)
        return cur

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


@patch("shared.data_layer._connection._get_supabase_connection")
def test_status_returns_latest_row(mock_conn):
    started = datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 5, 12, 10, 5, 0, tzinfo=timezone.utc)
    row = (101, "success", started, finished, 1234, None)
    mock_conn.return_value = _FakeConn(row)

    r = client.get("/api/marketing/sync/search-queries/status", headers=HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == 101
    assert body["status"] == "success"
    assert body["job_name"] == "search-queries"
    assert body["rows_processed"] == 1234
    assert body["error_message"] is None
    assert body["started_at"].startswith("2026-05-12T10:00:00")


@patch("shared.data_layer._connection._get_supabase_connection")
def test_status_never_run_returns_marker(mock_conn):
    mock_conn.return_value = _FakeConn(None)
    r = client.get("/api/marketing/sync/promocodes/status", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "never_run"
    assert body["job_name"] == "promocodes"


# -----------------------------------------------------------------------------
# Canonical sync_log job_name (R.2.1)
#
# The API exposes hyphenated URL slugs ("search-queries"/"promocodes"), but
# marketing.sync_log stores the snake_case name written by cron scripts so the
# frontend sees one unified history. These tests pin that contract.
# -----------------------------------------------------------------------------
@patch("shared.data_layer._connection._get_supabase_connection")
def test_create_sync_log_persists_canonical_search_queries_name(mock_conn):
    fake = _FakeConn((123,))
    mock_conn.return_value = fake

    from services.analytics_api.marketing import create_sync_log_entry

    new_id = create_sync_log_entry("search-queries")
    assert new_id == 123

    assert fake.cursors, "cursor() was never called"
    calls = fake.cursors[0].execute_calls
    assert calls, "execute() was never called"
    sql, params = calls[0]
    assert "INSERT INTO marketing.sync_log" in sql
    # First bound parameter is job_name — must be canonical snake_case.
    assert params[0] == "search_queries_sync"


@patch("shared.data_layer._connection._get_supabase_connection")
def test_create_sync_log_persists_canonical_promocodes_name(mock_conn):
    fake = _FakeConn((456,))
    mock_conn.return_value = fake

    from services.analytics_api.marketing import create_sync_log_entry

    create_sync_log_entry("promocodes")

    calls = fake.cursors[0].execute_calls
    sql, params = calls[0]
    assert "INSERT INTO marketing.sync_log" in sql
    assert params[0] == "promo_codes_sync"


@patch("shared.data_layer._connection._get_supabase_connection")
def test_status_queries_canonical_job_name(mock_conn):
    started = datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc)
    fake = _FakeConn((1, "success", started, started, 0, None))
    mock_conn.return_value = fake

    r = client.get("/api/marketing/sync/search-queries/status", headers=HEADERS)
    assert r.status_code == 200

    # SELECT must filter by canonical name, not the URL slug.
    calls = fake.cursors[0].execute_calls
    sql, params = calls[0]
    assert "FROM marketing.sync_log" in sql
    assert params[0] == "search_queries_sync"
