# tests/reporter/test_validator.py
"""Tests for deterministic report validator."""
from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.validator import validate, ValidationResult


def _insights(confidence: float = 0.85) -> ReportInsights:
    return ReportInsights(
        executive_summary="Test",
        sections=[],
        overall_confidence=confidence,
    )


def test_validate_pass():
    report = "## ▶ 0. Паспорт\n" * 7 + "Тестовый русский текст " * 50
    result = validate(report, _insights())
    assert result.verdict == "PASS"


def test_validate_fail_too_few_sections():
    report = "## ▶ 0. Паспорт\nТестовый текст " * 50
    result = validate(report, _insights())
    assert result.verdict in ("RETRY", "FAIL")
    assert any("sections" in i.lower() or "section" in i.lower() for i in result.issues)


def test_validate_fail_raw_json():
    report = '{"detailed_report": "test"}'
    result = validate(report, _insights())
    assert result.verdict == "RETRY"


def test_validate_low_confidence():
    report = "## ▶ 0. Паспорт\n" * 7 + "Тестовый текст " * 50
    result = validate(report, _insights(confidence=0.1))
    assert any("confidence" in i.lower() for i in result.issues)


def test_validate_too_many_placeholders():
    report = "## ▶ 0.\n" * 7 + "Н/Д " * 10 + "Тестовый текст " * 50
    result = validate(report, _insights())
    assert any("placeholder" in i.lower() for i in result.issues)
