"""Test that upsert() respects no_update_cols."""
import pytest
from unittest.mock import MagicMock, patch
from services.sheets_etl.loader import upsert


def test_upsert_excludes_no_update_cols():
    """Columns in no_update_cols must be absent from DO UPDATE SET."""
    import psycopg2.extras as extras
    calls = []
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: conn.cursor.return_value
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    rows = [{"sheet_row_id": "abc", "stage": "переговоры", "channel": "instagram"}]
    with patch.object(extras, "execute_values", lambda cur, sql, vals: calls.append(sql)):
        upsert(conn, "crm.integrations", rows, no_update_cols=["stage"])
    assert calls, "execute_values was not called"
    sql = calls[0]
    update_clause = sql.split("DO UPDATE SET")[1]
    assert "stage" not in update_clause, (
        f"'stage' must not appear in DO UPDATE SET clause, got: {sql}"
    )
    assert "channel = EXCLUDED.channel" in sql


def test_upsert_no_update_cols_default_empty():
    """Without no_update_cols, all non-conflict cols are updated."""
    import psycopg2.extras as extras
    calls = []
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: conn.cursor.return_value
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    rows = [{"sheet_row_id": "abc", "stage": "переговоры", "channel": "instagram"}]
    with patch.object(extras, "execute_values", lambda cur, sql, vals: calls.append(sql)):
        upsert(conn, "crm.integrations", rows)
    assert "stage = EXCLUDED.stage" in calls[0]
