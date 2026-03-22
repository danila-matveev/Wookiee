import pytest
from agents.v3.conductor.validator import (
    ValidationVerdict,
    ValidationResult,
    quick_validate,
)


def test_validation_verdict_enum():
    assert ValidationVerdict.PASS == "pass"
    assert ValidationVerdict.RETRY == "retry"
    assert ValidationVerdict.FAIL == "fail"


def test_quick_validate_passes_good_report():
    report = {
        "status": "success",
        "report": {
            "detailed_report": "# Report\n## Секция 1\nТекст" * 20,
            "brief_report": "Brief summary text here",
            "telegram_summary": "Сводка за 19 марта 2026:\n• Маржа: 255 тыс\n• Заказы: 1164" + " " * 60,
        },
        "agents_called": 3,
        "agents_succeeded": 3,
        "agents_failed": 0,
    }
    result = quick_validate(report)
    assert result.verdict == ValidationVerdict.PASS


def test_quick_validate_retries_empty_report():
    report = {
        "status": "success",
        "report": {
            "detailed_report": "",
            "brief_report": "",
            "telegram_summary": "",
        },
        "agents_called": 3,
        "agents_succeeded": 0,
        "agents_failed": 3,
    }
    result = quick_validate(report)
    assert result.verdict == ValidationVerdict.RETRY
    assert "пуст" in result.reason.lower() or "empty" in result.reason.lower()


def test_quick_validate_retries_failed_status():
    report = {
        "status": "failed",
        "report": None,
        "agents_called": 3,
        "agents_succeeded": 0,
        "agents_failed": 3,
    }
    result = quick_validate(report)
    assert result.verdict == ValidationVerdict.RETRY


def test_quick_validate_retries_short_telegram_summary():
    report = {
        "status": "success",
        "report": {
            "detailed_report": "# Report\n## Секция\nТекст " * 20,
            "brief_report": "Brief",
            "telegram_summary": "Не удалось сформировать ответ.",
        },
        "agents_called": 3,
        "agents_succeeded": 2,
        "agents_failed": 1,
    }
    result = quick_validate(report)
    assert result.verdict == ValidationVerdict.RETRY


def test_quick_validate_detects_known_failure_phrase():
    report = {
        "status": "success",
        "report": {
            "detailed_report": "Не удалось сформировать ответ.",
            "brief_report": "Не удалось сформировать ответ.",
            "telegram_summary": "Не удалось сформировать ответ.",
        },
        "agents_called": 1,
        "agents_succeeded": 1,
        "agents_failed": 0,
    }
    result = quick_validate(report)
    assert result.verdict == ValidationVerdict.RETRY
    assert "Не удалось" in result.reason
