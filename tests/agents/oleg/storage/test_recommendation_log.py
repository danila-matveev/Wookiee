"""Tests for StateStore.recommendation_log table and related methods."""
import json
import pytest

from agents.oleg.storage.state_store import StateStore


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test_oleg.db")
    s = StateStore(db_path)
    s.init_db()
    return s


# ── log_recommendation ────────────────────────────────────────────────────────

def test_log_recommendation_returns_id(store):
    row_id = store.log_recommendation(
        report_date="2026-03-21",
        report_type="daily_financial",
    )
    assert isinstance(row_id, int)
    assert row_id > 0


def test_log_recommendation_sequential_ids(store):
    id1 = store.log_recommendation(report_date="2026-03-21", report_type="daily_financial")
    id2 = store.log_recommendation(report_date="2026-03-21", report_type="daily_financial")
    assert id2 > id1


def test_log_recommendation_stores_basic_fields(store, tmp_path):
    import sqlite3

    store.log_recommendation(
        report_date="2026-03-21",
        report_type="daily_financial",
        context="financial",
        channel="wb",
        signals_count=5,
        recommendations_count=3,
        validation_verdict="pass",
        validation_attempts=2,
        advisor_cost_usd=0.01,
        validator_cost_usd=0.005,
        total_duration_ms=1200,
    )

    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM recommendation_log ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert row["report_date"] == "2026-03-21"
    assert row["report_type"] == "daily_financial"
    assert row["context"] == "financial"
    assert row["channel"] == "wb"
    assert row["signals_count"] == 5
    assert row["recommendations_count"] == 3
    assert row["validation_verdict"] == "pass"
    assert row["validation_attempts"] == 2
    assert abs(row["advisor_cost_usd"] - 0.01) < 1e-9
    assert abs(row["validator_cost_usd"] - 0.005) < 1e-9
    assert row["total_duration_ms"] == 1200


def test_log_recommendation_serializes_json_fields(store):
    import sqlite3

    signals = [{"sku": "abc", "signal": "low_stock"}]
    recommendations = [{"action": "reorder", "sku": "abc"}]
    validation_details = {"verdict": "pass", "issues": []}
    new_patterns = ["pattern_a", "pattern_b"]

    store.log_recommendation(
        report_date="2026-03-21",
        report_type="daily_financial",
        signals=signals,
        recommendations=recommendations,
        validation_details=validation_details,
        new_patterns=new_patterns,
    )

    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT signals, recommendations, validation_details, new_patterns "
            "FROM recommendation_log ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert json.loads(row["signals"]) == signals
    assert json.loads(row["recommendations"]) == recommendations
    assert json.loads(row["validation_details"]) == validation_details
    assert json.loads(row["new_patterns"]) == new_patterns


def test_log_recommendation_none_json_fields_stored_as_null(store):
    import sqlite3

    store.log_recommendation(
        report_date="2026-03-21",
        report_type="daily_financial",
        signals=None,
        recommendations=None,
        validation_details=None,
        new_patterns=None,
    )

    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT signals, recommendations, validation_details, new_patterns "
            "FROM recommendation_log ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert row["signals"] is None
    assert row["recommendations"] is None
    assert row["validation_details"] is None
    assert row["new_patterns"] is None


def test_log_recommendation_defaults(store):
    import sqlite3

    store.log_recommendation(report_date="2026-03-20", report_type="weekly")

    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM recommendation_log ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert row["context"] == "financial"
    assert row["channel"] is None
    assert row["signals_count"] == 0
    assert row["recommendations_count"] == 0
    assert row["validation_verdict"] == "skipped"
    assert row["validation_attempts"] == 1
    assert row["advisor_cost_usd"] == 0.0
    assert row["validator_cost_usd"] == 0.0
    assert row["total_duration_ms"] == 0


# ── get_recommendation_stats ──────────────────────────────────────────────────

def test_get_recommendation_stats_empty(store):
    stats = store.get_recommendation_stats(days=7)
    assert stats["total_runs"] == 0
    assert stats["pass_count"] == 0
    assert stats["fail_count"] == 0
    assert stats["pass_rate"] == 0.0


def test_get_recommendation_stats_counts(store):
    store.log_recommendation(
        report_date="2026-03-21", report_type="daily_financial",
        signals_count=4, recommendations_count=2, validation_verdict="pass",
    )
    store.log_recommendation(
        report_date="2026-03-21", report_type="daily_financial",
        signals_count=6, recommendations_count=3, validation_verdict="fail",
    )
    store.log_recommendation(
        report_date="2026-03-21", report_type="daily_financial",
        signals_count=2, recommendations_count=1, validation_verdict="pass",
    )

    stats = store.get_recommendation_stats(days=7)

    assert stats["total_runs"] == 3
    assert stats["pass_count"] == 2
    assert stats["fail_count"] == 1
    assert abs(stats["pass_rate"] - 2 / 3) < 1e-9
    assert abs(stats["avg_signals"] - 4.0) < 1e-9
    assert abs(stats["avg_recommendations"] - 2.0) < 1e-9


def test_get_recommendation_stats_pass_rate_all_pass(store):
    for _ in range(5):
        store.log_recommendation(
            report_date="2026-03-21", report_type="daily_financial",
            validation_verdict="pass",
        )

    stats = store.get_recommendation_stats(days=7)
    assert stats["pass_rate"] == 1.0
    assert stats["fail_count"] == 0


def test_get_recommendation_stats_skipped_not_counted_as_pass_or_fail(store):
    store.log_recommendation(
        report_date="2026-03-21", report_type="daily_financial",
        validation_verdict="skipped",
    )

    stats = store.get_recommendation_stats(days=7)
    assert stats["total_runs"] == 1
    assert stats["pass_count"] == 0
    assert stats["fail_count"] == 0
    assert stats["pass_rate"] == 0.0
