"""Tests for StateStore (SQLite)."""
from agents.oleg_v2.storage.state_store import StateStore


def test_init_db(temp_sqlite_path):
    store = StateStore(temp_sqlite_path)
    store.init_db()
    # Should not raise — tables created


def test_set_and_get_state(temp_sqlite_path):
    store = StateStore(temp_sqlite_path)
    store.init_db()
    store.set_state("test_key", "test_value")
    value = store.get_state("test_key")
    assert value == "test_value"


def test_get_state_missing_returns_none(temp_sqlite_path):
    store = StateStore(temp_sqlite_path)
    store.init_db()
    value = store.get_state("nonexistent")
    assert value is None


def test_log_report(temp_sqlite_path):
    store = StateStore(temp_sqlite_path)
    store.init_db()
    row_id = store.log_report(
        report_type="daily",
        agent="reporter",
        status="success",
        cost_usd=0.05,
    )
    assert row_id >= 1


def test_consecutive_failures(temp_sqlite_path):
    store = StateStore(temp_sqlite_path)
    store.init_db()
    # log_gate_check writes to gate_history which get_consecutive_failures reads
    store.log_gate_check(marketplace="wb", gate_name="etl", passed=False, is_hard=True, detail="fail1")
    store.log_gate_check(marketplace="wb", gate_name="etl", passed=False, is_hard=True, detail="fail2")
    failures = store.get_consecutive_failures("wb")
    assert failures == 2


def test_log_feedback(temp_sqlite_path):
    store = StateStore(temp_sqlite_path)
    store.init_db()
    store.log_feedback(
        user_id=123,
        feedback_text="Margin is wrong",
        decision="accepted",
        reasoning="Verified through data",
        playbook_update="Added margin check rule",
    )
    history = store.get_feedback_history(last_n=5)
    assert len(history) == 1
    assert history[0]["feedback_text"] == "Margin is wrong"
    assert history[0]["decision"] == "accepted"
