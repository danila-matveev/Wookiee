"""Tests for shared/signals/kb_patterns.py — load/save KB patterns."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.signals.kb_patterns import load_kb_patterns, save_proposed_patterns


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(
    pattern_name="low_margin",
    description="Margin is low",
    category="margin",
    source_tag="base",
    trigger_condition=None,
    severity="warning",
    action_hint="Raise price",
):
    """Build a single DB row tuple matching the SELECT column order."""
    if trigger_condition is None:
        trigger_condition = {"metric": "margin_pct", "operator": "<", "threshold": 0.1}
    return (pattern_name, description, category, source_tag, trigger_condition, severity, action_hint)


def _mock_conn(rows: list[tuple]) -> MagicMock:
    """Return a mock psycopg2 connection whose cursor.fetchall() yields *rows*."""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_cursor.rowcount = 1

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


# ---------------------------------------------------------------------------
# load_kb_patterns
# ---------------------------------------------------------------------------

class TestLoadKbPatterns:

    def test_load_kb_patterns_returns_list(self):
        """Returns a list of dicts with the expected keys when DB responds."""
        row = _make_row()
        with patch("shared.signals.kb_patterns._get_supabase_conn", return_value=_mock_conn([row])):
            result = load_kb_patterns()

        assert isinstance(result, list)
        assert len(result) == 1

        p = result[0]
        assert p["name"] == "low_margin"
        assert p["description"] == "Margin is low"
        assert p["category"] == "margin"
        assert p["source_tag"] == "base"
        assert p["severity"] == "warning"
        assert p["hint_template"] == "Raise price"
        assert "trigger_condition" in p

    def test_load_kb_patterns_multiple_rows(self):
        """Returns all rows when multiple patterns exist."""
        rows = [_make_row(pattern_name=f"pattern_{i}") for i in range(5)]
        with patch("shared.signals.kb_patterns._get_supabase_conn", return_value=_mock_conn(rows)):
            result = load_kb_patterns()

        assert len(result) == 5
        names = [p["name"] for p in result]
        assert "pattern_0" in names
        assert "pattern_4" in names

    def test_load_kb_patterns_verified_only_true(self):
        """When verified_only=True the SQL must include WHERE verified = TRUE."""
        executed_sql: list[str] = []

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.execute.side_effect = lambda sql, *args: executed_sql.append(sql)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("shared.signals.kb_patterns._get_supabase_conn", return_value=mock_conn):
            load_kb_patterns(verified_only=True)

        assert executed_sql, "execute() was never called"
        assert "verified = TRUE" in executed_sql[0], (
            "Expected 'verified = TRUE' in query but got: %s" % executed_sql[0]
        )

    def test_load_kb_patterns_verified_only_false(self):
        """When verified_only=False the SQL must NOT include WHERE verified = TRUE."""
        executed_sql: list[str] = []

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.execute.side_effect = lambda sql, *args: executed_sql.append(sql)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("shared.signals.kb_patterns._get_supabase_conn", return_value=mock_conn):
            load_kb_patterns(verified_only=False)

        assert executed_sql, "execute() was never called"
        assert "verified = TRUE" not in executed_sql[0], (
            "Unexpected 'verified = TRUE' in query: %s" % executed_sql[0]
        )

    def test_load_kb_patterns_graceful_failure(self):
        """Returns [] when psycopg2.connect raises an exception."""
        with patch(
            "shared.signals.kb_patterns._get_supabase_conn",
            side_effect=Exception("connection refused"),
        ):
            result = load_kb_patterns()

        assert result == []

    def test_load_kb_patterns_empty_table(self):
        """Returns [] when the table is empty (no error)."""
        with patch("shared.signals.kb_patterns._get_supabase_conn", return_value=_mock_conn([])):
            result = load_kb_patterns()

        assert result == []


# ---------------------------------------------------------------------------
# save_proposed_patterns
# ---------------------------------------------------------------------------

class TestSaveProposedPatterns:

    def _sample_pattern(self, name="new_pattern") -> dict:
        return {
            "name": name,
            "description": "Test description",
            "category": "margin",
            "source_tag": "advisor",
            "trigger_condition": {"metric": "margin_pct", "operator": "<", "threshold": 0.05},
            "severity": "warning",
            "hint_template": "Do something",
            "impact_on": "margin",
            "confidence": "medium",
        }

    def test_save_proposed_patterns_returns_count(self):
        """Returns the number of rows INSERT'ed (rowcount sum)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1  # simulate 1 row inserted per execute

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        patterns = [self._sample_pattern("p1"), self._sample_pattern("p2")]

        with patch("shared.signals.kb_patterns._get_supabase_conn", return_value=mock_conn):
            count = save_proposed_patterns(patterns)

        assert count == 2
        assert mock_cursor.execute.call_count == 2
        mock_conn.commit.assert_called_once()

    def test_save_proposed_patterns_insert_called(self):
        """Verifies that INSERT INTO public.kb_patterns is executed."""
        executed_sqls: list[str] = []

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.execute.side_effect = lambda sql, params: executed_sqls.append(sql)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("shared.signals.kb_patterns._get_supabase_conn", return_value=mock_conn):
            save_proposed_patterns([self._sample_pattern()])

        assert any("INSERT INTO public.kb_patterns" in sql for sql in executed_sqls)
        assert any("ON CONFLICT" in sql for sql in executed_sqls)

    def test_save_proposed_patterns_empty_list(self):
        """Returns 0 immediately without opening a connection when given []."""
        with patch("shared.signals.kb_patterns._get_supabase_conn") as mock_get_conn:
            count = save_proposed_patterns([])

        assert count == 0
        mock_get_conn.assert_not_called()

    def test_save_proposed_patterns_graceful_failure(self):
        """Returns 0 when the DB connection fails."""
        with patch(
            "shared.signals.kb_patterns._get_supabase_conn",
            side_effect=Exception("timeout"),
        ):
            count = save_proposed_patterns([self._sample_pattern()])

        assert count == 0

    def test_save_proposed_patterns_conflict_skipped(self):
        """ON CONFLICT DO NOTHING: rowcount=0 means 0 inserted rows counted."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # conflict — nothing inserted

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("shared.signals.kb_patterns._get_supabase_conn", return_value=mock_conn):
            count = save_proposed_patterns([self._sample_pattern()])

        assert count == 0

    def test_save_proposed_patterns_uses_pattern_name_fallback(self):
        """Accepts 'pattern_name' key as fallback for 'name'."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_conn.cursor.return_value  # reuse
        mock_conn.cursor.return_value = mock_cursor

        pattern = {
            "pattern_name": "fallback_pattern",
            "description": "test",
            "category": "margin",
            "trigger_condition": {"metric": "x", "operator": ">", "threshold": 0},
        }

        with patch("shared.signals.kb_patterns._get_supabase_conn", return_value=mock_conn):
            count = save_proposed_patterns([pattern])

        assert count == 1
        # Verify the first positional param passed to execute is the pattern_name
        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]  # second positional arg is the params tuple
        assert params[0] == "fallback_pattern"


# ---------------------------------------------------------------------------
# source_tag filtering (pure Python — no mocks needed)
# ---------------------------------------------------------------------------

class TestKbPatternSourceTagFiltering:
    """Tests for the filtering logic used in the orchestrator:
    relevant_kb = [p for p in kb_patterns if p.get("source_tag") == source_tag]
    """

    def _make_patterns(self):
        return [
            {"name": "p1", "source_tag": "base"},
            {"name": "p2", "source_tag": "base"},
            {"name": "p3", "source_tag": "advisor"},
            {"name": "p4", "source_tag": "seo"},
            {"name": "p5"},  # no source_tag key
        ]

    def _filter(self, patterns: list[dict], source_tag: str) -> list[dict]:
        """Mirrors the orchestrator filtering expression."""
        return [p for p in patterns if p.get("source_tag") == source_tag]

    def test_filter_by_base(self):
        result = self._filter(self._make_patterns(), "base")
        assert len(result) == 2
        assert all(p["source_tag"] == "base" for p in result)

    def test_filter_by_advisor(self):
        result = self._filter(self._make_patterns(), "advisor")
        assert len(result) == 1
        assert result[0]["name"] == "p3"

    def test_filter_by_seo(self):
        result = self._filter(self._make_patterns(), "seo")
        assert len(result) == 1
        assert result[0]["name"] == "p4"

    def test_filter_missing_key_not_matched(self):
        """Patterns without source_tag are excluded from any source_tag filter."""
        result = self._filter(self._make_patterns(), "base")
        names = [p["name"] for p in result]
        assert "p5" not in names

    def test_filter_unknown_tag_returns_empty(self):
        result = self._filter(self._make_patterns(), "nonexistent_tag")
        assert result == []

    def test_filter_empty_list_returns_empty(self):
        result = self._filter([], "base")
        assert result == []

    def test_filter_preserves_full_pattern_dict(self):
        """Filtered items are the original dicts (not copies)."""
        patterns = self._make_patterns()
        result = self._filter(patterns, "advisor")
        assert result[0] is patterns[2]
