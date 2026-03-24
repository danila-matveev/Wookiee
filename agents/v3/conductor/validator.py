"""Report quality validation — quick checks + LLM validation."""
import re
from dataclasses import dataclass, field
from enum import Enum


class ValidationVerdict(str, Enum):
    PASS = "pass"
    RETRY = "retry"
    FAIL = "fail"


@dataclass
class ValidationResult:
    verdict: ValidationVerdict
    reason: str = ""
    details: dict = field(default_factory=dict)


_FAILURE_PHRASES = [
    "Не удалось сформировать",
    "не удалось сформировать",
    "Error generating",
    "Failed to generate",
]

MIN_TELEGRAM_SUMMARY_LEN = 100
MIN_DETAILED_REPORT_LEN = 500


def quick_validate(report: dict) -> ValidationResult:
    """Fast deterministic validation — no LLM call.

    Checks:
    1. Report status is not "failed"
    2. Report dict has required keys with non-empty values
    3. No known failure phrases in content
    4. telegram_summary length >= MIN_TELEGRAM_SUMMARY_LEN
    5. detailed_report length >= MIN_DETAILED_REPORT_LEN
    6. Content quality: Russian text + toggle headers (## ▶)
    """
    # 1. Failed status
    if report.get("status") == "failed" or report.get("report") is None:
        return ValidationResult(
            verdict=ValidationVerdict.RETRY,
            reason="Статус отчёта: failed или report=None",
            details={"agents_failed": report.get("agents_failed", 0)},
        )

    r = report["report"]
    detailed = r.get("detailed_report", "") or ""
    telegram = r.get("telegram_summary", "") or ""

    # Handle non-string detailed_report (compiler returned dict/list)
    if not isinstance(detailed, str):
        return ValidationResult(
            verdict=ValidationVerdict.RETRY,
            reason=f"detailed_report is {type(detailed).__name__}, not string",
        )

    # 2. Empty content
    if not detailed.strip():
        return ValidationResult(
            verdict=ValidationVerdict.RETRY,
            reason="Подробный отчёт пуст (detailed_report)",
        )

    if not telegram.strip():
        # If detailed_report is substantial, allow delivery —
        # orchestrator will generate telegram_summary from detailed_report
        if len(detailed) >= MIN_DETAILED_REPORT_LEN:
            pass  # continue to remaining checks
        else:
            return ValidationResult(
                verdict=ValidationVerdict.RETRY,
                reason="Telegram-саммари пуст и detailed_report слишком короткий",
            )

    # 3. Known failure phrases
    for phrase in _FAILURE_PHRASES:
        if phrase in detailed or phrase in telegram:
            return ValidationResult(
                verdict=ValidationVerdict.RETRY,
                reason=f"Обнаружена фраза ошибки: '{phrase}'",
                details={"phrase": phrase},
            )

    # 4. Too short (skip telegram check if detailed_report is substantial — fallback will generate summary)
    if len(telegram) < MIN_TELEGRAM_SUMMARY_LEN and len(detailed) < MIN_DETAILED_REPORT_LEN:
        return ValidationResult(
            verdict=ValidationVerdict.RETRY,
            reason=f"Telegram-саммари слишком короткий ({len(telegram)} < {MIN_TELEGRAM_SUMMARY_LEN}) и detailed_report тоже",
        )

    if len(detailed) < MIN_DETAILED_REPORT_LEN:
        return ValidationResult(
            verdict=ValidationVerdict.RETRY,
            reason=f"Подробный отчёт слишком короткий ({len(detailed)} < {MIN_DETAILED_REPORT_LEN})",
        )

    # 5. Content quality — must contain Russian text and toggle headers
    has_russian = bool(re.search(r'[а-яА-ЯёЁ]', detailed))
    has_toggles = "## ▶" in detailed
    has_tables = "|" in detailed and "---" in detailed

    if not has_russian:
        return ValidationResult(
            verdict=ValidationVerdict.RETRY,
            reason="detailed_report не содержит русский текст (возможно raw JSON)",
        )

    if not has_toggles and not has_tables:
        return ValidationResult(
            verdict=ValidationVerdict.RETRY,
            reason="detailed_report без toggle-заголовков и таблиц (неправильный формат)",
        )

    # All checks passed
    return ValidationResult(verdict=ValidationVerdict.PASS)
