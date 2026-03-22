"""Tests for centralized message templates."""
import pytest
from agents.v3.delivery.messages import (
    data_ready,
    report_error,
    report_retries_exhausted,
    watchdog_alert,
    anomaly_alert,
    watchdog_repeated_failures,
    report_exception,
)


def test_data_ready_single_report():
    msg = data_ready("22 марта", ["дневной фин"])
    assert "22 марта" in msg
    assert "дневной фин" in msg


def test_data_ready_multiple_reports():
    msg = data_ready("22 марта", ["дневной фин", "маркетинговый", "воронка"])
    assert "дневной фин" in msg
    assert "воронка" in msg


def test_report_error_includes_attempt():
    msg = report_error("22 марта", "дневной фин", "ConnectionError", 2, 3)
    assert "2/3" in msg
    assert "дневной фин" in msg
    assert "ConnectionError" in msg


def test_report_error_truncates_long_error():
    long_error = "x" * 500
    msg = report_error("22 марта", "дневной фин", long_error, 1, 3)
    assert len(msg) < 400  # error truncated to 200


def test_report_retries_exhausted():
    msg = report_retries_exhausted("22 марта", "дневной фин")
    assert "дневной фин" in msg
    assert "ручной" in msg.lower() or "Требуется" in msg


def test_watchdog_alert_warning():
    msg = watchdog_alert("warning", ["db", "last_run"], ["llm"])
    assert "ПРЕДУПРЕЖДЕНИЕ" in msg
    assert "✗" in msg
    assert "✓" in msg
    assert "База данных" in msg


def test_watchdog_alert_critical():
    msg = watchdog_alert("critical", ["db", "llm", "last_run"], [])
    assert "КРИТИЧНО" in msg


def test_anomaly_alert_negative():
    msg = anomaly_alert("Выручка", "OZON", 141886, 209035, -32.1)
    assert "OZON" in msg
    assert "Выручка" in msg
    assert "↓" in msg
    assert "32.1%" in msg


def test_anomaly_alert_positive():
    msg = anomaly_alert("Заказы", "WB", 1500, 1000, 50.0)
    assert "↑" in msg


def test_watchdog_repeated_failures():
    msg = watchdog_repeated_failures("дневной фин", 3)
    assert "3" in msg
    assert "ручная" in msg.lower() or "проверка" in msg.lower()


def test_report_exception():
    msg = report_exception("дневной", "2026-03-22", "2026-03-22", Exception("timeout"))
    assert "дневной" in msg or "дневного" in msg
    assert "timeout" in msg


def test_anomaly_report_basic():
    from agents.v3.delivery.messages import anomaly_report
    artifact = {
        "summary": {"critical_count": 1, "warning_count": 2, "info_count": 0, "top_priority_anomaly": "Выручка WB"},
        "summary_text": "Падение выручки",
        "anomalies": [
            {"metric": "Выручка", "channel": "WB", "severity": "critical", "deviation_pct": -32.1},
        ],
    }
    msg = anomaly_report(artifact)
    assert "аномалии" in msg.lower() or "Аномалии" in msg
    assert "Критических: 1" in msg
    assert "Выручка" in msg
    assert "[Wookiee v3]" not in msg
