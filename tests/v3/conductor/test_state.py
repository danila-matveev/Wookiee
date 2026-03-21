import pytest
import tempfile
import os
from datetime import datetime

from agents.v3.conductor.state import ConductorState


@pytest.fixture
def state():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = ConductorState(db_path=path)
    s.ensure_table()
    yield s
    os.unlink(path)


def test_log_and_get_successful(state: ConductorState):
    state.log("2026-03-20", "daily", status="success", notion_url="https://notion.so/abc")
    result = state.get_successful("2026-03-20")
    assert "daily" in result


def test_get_successful_excludes_failed(state: ConductorState):
    state.log("2026-03-20", "daily", status="failed", error="LLM timeout")
    result = state.get_successful("2026-03-20")
    assert "daily" not in result


def test_get_attempts_default_zero(state: ConductorState):
    assert state.get_attempts("2026-03-20", "daily") == 0


def test_log_increments_attempts(state: ConductorState):
    state.log("2026-03-20", "daily", status="running", attempt=1)
    state.log("2026-03-20", "daily", status="retrying", attempt=2, error="empty sections")
    assert state.get_attempts("2026-03-20", "daily") == 2


def test_log_upserts_same_date_type(state: ConductorState):
    state.log("2026-03-20", "daily", status="running", attempt=1)
    state.log("2026-03-20", "daily", status="success", attempt=1, notion_url="https://notion.so/x")
    result = state.get_successful("2026-03-20")
    assert "daily" in result


def test_multiple_report_types(state: ConductorState):
    state.log("2026-03-20", "daily", status="success")
    state.log("2026-03-20", "weekly", status="failed", error="timeout")
    state.log("2026-03-20", "marketing_weekly", status="success")
    result = state.get_successful("2026-03-20")
    assert result == {"daily", "marketing_weekly"}


def test_data_ready_tracking(state: ConductorState):
    state.log("2026-03-20", "daily", status="running",
              data_ready_at="2026-03-21T06:30:00+03:00")
    assert state.get_attempts("2026-03-20", "daily") >= 0


def test_lifecycle_fields(state: ConductorState):
    """started_at, finished_at, validation_result are stored and preserved on upsert."""
    state.log("2026-03-20", "daily", status="running",
              started_at="2026-03-21T07:00:00+03:00")
    state.log("2026-03-20", "daily", status="success",
              finished_at="2026-03-21T07:05:00+03:00",
              validation_result="pass")
    import sqlite3
    conn = sqlite3.connect(state._db_path)
    row = conn.execute(
        "SELECT started_at, finished_at, validation_result FROM conductor_log "
        "WHERE date = '2026-03-20' AND report_type = 'daily'"
    ).fetchone()
    conn.close()
    assert row[0] == "2026-03-21T07:00:00+03:00"
    assert row[1] == "2026-03-21T07:05:00+03:00"
    assert row[2] == "pass"
