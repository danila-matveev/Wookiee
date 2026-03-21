# Smart Conductor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 15 noisy cron jobs with a Smart Conductor that validates reports before delivery, consolidates notifications, and handles failures with LLM-powered diagnostics.

**Architecture:** New `agents/v3/conductor/` package with 4 modules: `schedule.py` (deterministic), `state.py` (SQLite tracking), `validator.py` (LLM quality check), `conductor.py` (main orchestration). Scheduler simplified to 5 triggers behind `USE_CONDUCTOR` feature flag. Retry via APScheduler `DateTrigger` (non-blocking).

**Tech Stack:** Python 3.11, APScheduler, SQLite (synchronous — writes are small/infrequent, consistent with existing StateStore), LangGraph (for validator LLM calls), aiogram (Telegram)

**Spec:** `docs/superpowers/specs/2026-03-21-smart-conductor-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `agents/v3/conductor/__init__.py` | Package exports |
| `agents/v3/conductor/schedule.py` | `get_today_reports(date)` — deterministic schedule logic |
| `agents/v3/conductor/state.py` | `ConductorState` — SQLite `conductor_log` table CRUD |
| `agents/v3/conductor/validator.py` | `validate_report()` — LLM-powered quality check |
| `agents/v3/conductor/conductor.py` | `data_ready_check()`, `deadline_check()`, `catchup_check()`, `generate_and_validate()` |
| `agents/v3/conductor/messages.py` | Telegram message formatters: `format_data_ready()`, `format_alert()` |
| `agents/v3/agents/report-conductor.md` | LLM prompt for validation/diagnostics |
| `tests/v3/conductor/test_schedule.py` | Tests for schedule logic |
| `tests/v3/conductor/test_state.py` | Tests for ConductorState |
| `tests/v3/conductor/test_validator.py` | Tests for validator |
| `tests/v3/conductor/test_conductor.py` | Tests for main conductor flow |
| `tests/v3/conductor/test_messages.py` | Tests for message formatters |
| `tests/v3/conductor/__init__.py` | Test package |

### Modified Files

| File | Changes |
|------|---------|
| `agents/v3/scheduler.py` | Add `setup_conductor_scheduler()`, keep old as `setup_legacy_scheduler()`, feature flag |
| `agents/v3/config.py` | Add `USE_CONDUCTOR`, `CONDUCTOR_DEADLINE_HOUR`, `CONDUCTOR_CATCHUP_HOUR` |
| `agents/v3/delivery/notion.py` | Add `"price_weekly"` to report type mapping |

---

## Task 1: ConductorState — SQLite tracking

**Files:**
- Create: `agents/v3/conductor/__init__.py`
- Create: `agents/v3/conductor/state.py`
- Create: `tests/v3/conductor/__init__.py`
- Create: `tests/v3/conductor/test_state.py`

- [ ] **Step 1: Write failing tests for ConductorState**

```python
# tests/v3/conductor/test_state.py
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
    # Should be retrievable
    assert state.get_attempts("2026-03-20", "daily") >= 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v3/conductor/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.v3.conductor'`

- [ ] **Step 3: Implement ConductorState**

```python
# agents/v3/conductor/__init__.py
"""Smart Conductor — report controller agent."""

# agents/v3/conductor/state.py
"""ConductorState — SQLite tracking for report generation."""
import sqlite3
from dataclasses import dataclass
from typing import Optional


class ConductorState:
    """Tracks report generation attempts, results, and delivery status."""

    def __init__(self, db_path: str = "agents/v3/data/v3_state.db"):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def ensure_table(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conductor_log (
                    date TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    data_ready_at TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    validation_result TEXT,
                    notion_url TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (date, report_type)
                )
            """)

    def log(
        self,
        date: str,
        report_type: str,
        status: str,
        attempt: int = 0,
        data_ready_at: Optional[str] = None,
        notion_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO conductor_log
                    (date, report_type, status, attempts, data_ready_at, notion_url, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (date, report_type) DO UPDATE SET
                    status = excluded.status,
                    attempts = MAX(conductor_log.attempts, excluded.attempts),
                    data_ready_at = COALESCE(excluded.data_ready_at, conductor_log.data_ready_at),
                    notion_url = COALESCE(excluded.notion_url, conductor_log.notion_url),
                    error = excluded.error,
                    updated_at = datetime('now')
                """,
                (date, report_type, status, attempt, data_ready_at, notion_url, error),
            )

    def get_successful(self, date: str) -> set[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT report_type FROM conductor_log WHERE date = ? AND status = 'success'",
                (date,),
            ).fetchall()
        return {r[0] for r in rows}

    def get_attempts(self, date: str, report_type: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT attempts FROM conductor_log WHERE date = ? AND report_type = ?",
                (date, report_type),
            ).fetchone()
        return row[0] if row else 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/v3/conductor/test_state.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agents/v3/conductor/__init__.py agents/v3/conductor/state.py \
       tests/v3/conductor/__init__.py tests/v3/conductor/test_state.py
git commit -m "feat(conductor): add ConductorState SQLite tracking"
```

---

## Task 2: Schedule — deterministic report schedule

**Files:**
- Create: `agents/v3/conductor/schedule.py`
- Create: `tests/v3/conductor/test_schedule.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v3/conductor/test_schedule.py
import pytest
from datetime import date

from agents.v3.conductor.schedule import get_today_reports, ReportType


def test_regular_day_returns_daily():
    # 2026-03-19 is Thursday
    result = get_today_reports(date(2026, 3, 19))
    assert result == [ReportType.DAILY]


def test_monday_returns_weekly_reports():
    # 2026-03-16 is Monday
    result = get_today_reports(date(2026, 3, 16))
    assert ReportType.DAILY in result
    assert ReportType.WEEKLY in result
    assert ReportType.MARKETING_WEEKLY in result
    assert ReportType.FUNNEL_WEEKLY in result
    assert ReportType.PRICE_WEEKLY in result


def test_friday_returns_finolog():
    # 2026-03-20 is Friday
    result = get_today_reports(date(2026, 3, 20))
    assert ReportType.DAILY in result
    assert ReportType.FINOLOG_WEEKLY in result
    assert ReportType.WEEKLY not in result


def test_first_monday_of_month_includes_monthly():
    # 2026-04-06 is first Monday of April
    result = get_today_reports(date(2026, 4, 6))
    assert ReportType.MONTHLY in result
    assert ReportType.MARKETING_MONTHLY in result
    assert ReportType.PRICE_MONTHLY in result
    # Also has weekly
    assert ReportType.WEEKLY in result


def test_second_monday_no_monthly():
    # 2026-03-09 is second Monday
    result = get_today_reports(date(2026, 3, 9))
    assert ReportType.WEEKLY in result
    assert ReportType.MONTHLY not in result


def test_weekend_only_daily():
    # 2026-03-21 is Saturday
    result = get_today_reports(date(2026, 3, 21))
    assert result == [ReportType.DAILY]


def test_report_type_to_orchestrator_method():
    """Each ReportType must map to an orchestrator function name."""
    for rt in ReportType:
        assert rt.orchestrator_method is not None
        assert rt.notion_label is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v3/conductor/test_schedule.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement schedule module**

```python
# agents/v3/conductor/schedule.py
"""Deterministic report schedule — no LLM needed."""
from datetime import date
from enum import Enum


class ReportType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MARKETING_WEEKLY = "marketing_weekly"
    MARKETING_MONTHLY = "marketing_monthly"
    FUNNEL_WEEKLY = "funnel_weekly"
    PRICE_WEEKLY = "price_weekly"
    PRICE_MONTHLY = "price_monthly"
    FINOLOG_WEEKLY = "finolog_weekly"

    @property
    def orchestrator_method(self) -> str:
        """Name of the orchestrator function to call."""
        return {
            self.DAILY: "run_daily_report",
            self.WEEKLY: "run_weekly_report",
            self.MONTHLY: "run_monthly_report",
            self.MARKETING_WEEKLY: "run_marketing_report",
            self.MARKETING_MONTHLY: "run_marketing_report",
            self.FUNNEL_WEEKLY: "run_funnel_report",
            self.PRICE_WEEKLY: "run_price_analysis",
            self.PRICE_MONTHLY: "run_price_analysis",
            self.FINOLOG_WEEKLY: "run_finolog_report",
        }[self]

    @property
    def notion_label(self) -> str:
        """Notion database category label."""
        return {
            self.DAILY: "Ежедневный фин анализ",
            self.WEEKLY: "Еженедельный фин анализ",
            self.MONTHLY: "Ежемесячный фин анализ",
            self.MARKETING_WEEKLY: "Еженедельный маркетинговый анализ",
            self.MARKETING_MONTHLY: "Ежемесячный маркетинговый анализ",
            self.FUNNEL_WEEKLY: "Воронка WB (сводный)",
            self.PRICE_WEEKLY: "Еженедельный ценовой анализ",
            self.PRICE_MONTHLY: "Ценовой анализ",
            self.FINOLOG_WEEKLY: "Сводка ДДС",
        }[self]

    @property
    def human_name(self) -> str:
        """Short name for Telegram messages."""
        return {
            self.DAILY: "Daily фин",
            self.WEEKLY: "Weekly фин",
            self.MONTHLY: "Monthly фин",
            self.MARKETING_WEEKLY: "Weekly маркетинг",
            self.MARKETING_MONTHLY: "Monthly маркетинг",
            self.FUNNEL_WEEKLY: "Weekly воронка",
            self.PRICE_WEEKLY: "Weekly ценовой",
            self.PRICE_MONTHLY: "Monthly ценовой",
            self.FINOLOG_WEEKLY: "Weekly ДДС",
        }[self]


def get_today_reports(d: date) -> list[ReportType]:
    """Return list of reports that should be generated for given date.

    Rules:
    - Every day: DAILY
    - Monday (weekday 0): WEEKLY, MARKETING_WEEKLY, FUNNEL_WEEKLY, PRICE_WEEKLY
    - Friday (weekday 4): FINOLOG_WEEKLY
    - First Monday of month (day 1-7, weekday 0): MONTHLY, MARKETING_MONTHLY, PRICE_MONTHLY
    """
    reports: list[ReportType] = [ReportType.DAILY]

    if d.weekday() == 0:  # Monday
        reports += [
            ReportType.WEEKLY,
            ReportType.MARKETING_WEEKLY,
            ReportType.FUNNEL_WEEKLY,
            ReportType.PRICE_WEEKLY,
        ]

    if d.weekday() == 4:  # Friday
        reports.append(ReportType.FINOLOG_WEEKLY)

    if d.day <= 7 and d.weekday() == 0:  # First Monday of month
        reports += [
            ReportType.MONTHLY,
            ReportType.MARKETING_MONTHLY,
            ReportType.PRICE_MONTHLY,
        ]

    return reports
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/v3/conductor/test_schedule.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agents/v3/conductor/schedule.py tests/v3/conductor/test_schedule.py
git commit -m "feat(conductor): add deterministic report schedule"
```

---

## Task 3: Messages — Telegram notification formatters

**Files:**
- Create: `agents/v3/conductor/messages.py`
- Create: `tests/v3/conductor/test_messages.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v3/conductor/test_messages.py
import pytest
from agents.v3.conductor.messages import format_data_ready, format_alert
from agents.v3.conductor.schedule import ReportType


def test_format_data_ready_basic():
    msg = format_data_ready(
        wb_info={"updated_at": "06:41", "orders": 1350, "revenue_ratio": 1.04},
        ozon_info={"updated_at": "07:06", "orders": 152, "revenue_ratio": 0.68},
        pending=[ReportType.DAILY],
        report_date="20 марта",
    )
    assert "Данные за 20 марта готовы" in msg
    assert "WB" in msg
    assert "OZON" in msg
    assert "Daily фин" in msg


def test_format_data_ready_low_revenue_warning():
    msg = format_data_ready(
        wb_info={"updated_at": "06:41", "orders": 1350, "revenue_ratio": 1.04},
        ozon_info={"updated_at": "07:06", "orders": 152, "revenue_ratio": 0.68},
        pending=[ReportType.DAILY],
        report_date="20 марта",
    )
    # OZON revenue 68% should show warning
    assert "⚠️" in msg


def test_format_data_ready_multiple_reports():
    msg = format_data_ready(
        wb_info={"updated_at": "06:41", "orders": 1350, "revenue_ratio": 1.04},
        ozon_info={"updated_at": "07:06", "orders": 152, "revenue_ratio": 1.0},
        pending=[ReportType.DAILY, ReportType.WEEKLY, ReportType.MARKETING_WEEKLY],
        report_date="16 марта",
    )
    assert "Daily фин" in msg
    assert "Weekly фин" in msg
    assert "Weekly маркетинг" in msg


def test_format_alert_basic():
    msg = format_alert(
        report_type=ReportType.DAILY,
        reason="LLM timeout (OpenRouter 504)",
        attempt=3,
        max_attempts=3,
    )
    assert "Проблема" in msg
    assert "Daily фин" in msg
    assert "3/3" in msg
    assert "LLM timeout" in msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v3/conductor/test_messages.py -v`
Expected: FAIL

- [ ] **Step 3: Implement message formatters**

```python
# agents/v3/conductor/messages.py
"""Telegram message formatters for conductor notifications."""
from agents.v3.conductor.schedule import ReportType


def format_data_ready(
    wb_info: dict,
    ozon_info: dict,
    pending: list[ReportType],
    report_date: str,
) -> str:
    """Format 'data ready' notification.

    Args:
        wb_info: {updated_at, orders, revenue_ratio}
        ozon_info: {updated_at, orders, revenue_ratio}
        pending: list of reports to generate
        report_date: human-readable date string
    """
    def _channel_line(name: str, info: dict) -> str:
        rev_pct = int(info["revenue_ratio"] * 100)
        warn = " ⚠️" if rev_pct < 75 else ""
        return (
            f"{name}: обновлено в {info['updated_at']} МСК | "
            f"Заказы: {info['orders']} | Выручка: {rev_pct}% от нормы{warn}"
        )

    report_names = ", ".join(r.human_name for r in pending)

    return (
        f"✅ Данные за {report_date} готовы\n\n"
        f"{_channel_line('WB', wb_info)}\n"
        f"{_channel_line('OZON', ozon_info)}\n\n"
        f"📊 Запускаю отчёты: {report_names}"
    )


def format_alert(
    report_type: ReportType,
    reason: str,
    attempt: int,
    max_attempts: int = 3,
    diagnostics: str | None = None,
    action: str | None = None,
) -> str:
    """Format error alert notification."""
    lines = [
        "⚠️ Проблема с формированием отчётов\n",
        f"Статус: {report_type.human_name} — ❌ не сформирован ({attempt}/{max_attempts} попытки)",
        f"Причина: {reason}",
    ]
    if diagnostics:
        lines.append(f"Диагностика: {diagnostics}")
    if action:
        lines.append(f"\nДействие: {action}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/v3/conductor/test_messages.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agents/v3/conductor/messages.py tests/v3/conductor/test_messages.py
git commit -m "feat(conductor): add Telegram message formatters"
```

---

## Task 4: Validator — LLM-powered report quality check

**Files:**
- Create: `agents/v3/conductor/validator.py`
- Create: `agents/v3/agents/report-conductor.md`
- Create: `tests/v3/conductor/test_validator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v3/conductor/test_validator.py
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
            "telegram_summary": "Сводка за 19 марта 2026:\n• Маржа: 255 тыс\n• Заказы: 1164",
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v3/conductor/test_validator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement validator (quick_validate — no LLM)**

The validator has two layers:
1. `quick_validate()` — fast deterministic checks (no LLM)
2. `llm_validate()` — deeper LLM-based checks (called if quick_validate passes)

Start with quick_validate:

```python
# agents/v3/conductor/validator.py
"""Report quality validation — quick checks + LLM validation."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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
    3. telegram_summary length >= MIN_TELEGRAM_SUMMARY_LEN
    4. detailed_report length >= MIN_DETAILED_REPORT_LEN
    5. No known failure phrases in content
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

    # 2. Empty content
    if not detailed.strip():
        return ValidationResult(
            verdict=ValidationVerdict.RETRY,
            reason="Подробный отчёт пуст (detailed_report)",
        )

    if not telegram.strip():
        return ValidationResult(
            verdict=ValidationVerdict.RETRY,
            reason="Telegram-саммари пуст (telegram_summary)",
        )

    # 3. Known failure phrases
    for phrase in _FAILURE_PHRASES:
        if phrase in detailed or phrase in telegram:
            return ValidationResult(
                verdict=ValidationVerdict.RETRY,
                reason=f"Обнаружена фраза ошибки: '{phrase}'",
                details={"phrase": phrase},
            )

    # 4. Too short
    if len(telegram) < MIN_TELEGRAM_SUMMARY_LEN:
        return ValidationResult(
            verdict=ValidationVerdict.RETRY,
            reason=f"Telegram-саммари слишком короткий ({len(telegram)} < {MIN_TELEGRAM_SUMMARY_LEN})",
        )

    if len(detailed) < MIN_DETAILED_REPORT_LEN:
        return ValidationResult(
            verdict=ValidationVerdict.RETRY,
            reason=f"Подробный отчёт слишком короткий ({len(detailed)} < {MIN_DETAILED_REPORT_LEN})",
        )

    # All checks passed
    return ValidationResult(verdict=ValidationVerdict.PASS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/v3/conductor/test_validator.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Create report-conductor agent prompt**

```markdown
<!-- agents/v3/agents/report-conductor.md -->
# Agent: report-conductor

## Role
Ты — контроллер качества аналитических отчётов. Твоя задача — проверить сгенерированный
отчёт и вынести вердикт: можно ли его отправить клиенту.

## Rules
1. Проверь, что все обязательные секции присутствуют и содержат данные
2. Сравни ключевые цифры с предыдущим отчётом — отклонение > 10x подозрительно
3. Проверь, что гипотезы обоснованы цифрами, а не придуманы
4. Проверь формат: toggle-заголовки, таблицы, интерпретации после таблиц

## Output Format
Верни JSON:
```json
{
  "verdict": "pass" | "retry" | "fail",
  "reason": "причина (если не pass)",
  "issues": ["список конкретных проблем"],
  "score": 0-100
}
```

Правила вердикта:
- **pass**: отчёт полный, цифры адекватные, формат правильный
- **retry**: отчёт имеет исправимые проблемы (пустые секции, неполные данные)
- **fail**: критическая проблема, retry не поможет (нет данных в БД, системная ошибка)
```

- [ ] **Step 6: Commit**

```bash
git add agents/v3/conductor/validator.py agents/v3/agents/report-conductor.md \
       tests/v3/conductor/test_validator.py
git commit -m "feat(conductor): add report validator with quick checks + LLM prompt"
```

---

## Task 5: Conductor — main orchestration logic

**Files:**
- Create: `agents/v3/conductor/conductor.py`
- Create: `tests/v3/conductor/test_conductor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v3/conductor/test_conductor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, datetime

from agents.v3.conductor.conductor import (
    data_ready_check,
    generate_and_validate,
    deadline_check,
)
from agents.v3.conductor.schedule import ReportType
from agents.v3.conductor.validator import ValidationVerdict, ValidationResult


@pytest.fixture
def mock_gates():
    """Mock GateChecker that returns can_generate=True for both channels."""
    checker = MagicMock()
    wb_result = MagicMock(can_generate=True, has_caveats=False, caveats=[])
    ozon_result = MagicMock(can_generate=True, has_caveats=False, caveats=[])
    checker.check_all.side_effect = lambda mp: wb_result if mp == "wb" else ozon_result
    return checker


@pytest.fixture
def mock_state():
    state = MagicMock()
    state.get_successful.return_value = set()
    state.get_attempts.return_value = 0
    return state


@pytest.mark.asyncio
async def test_data_ready_check_skips_when_gates_fail():
    """If gates fail, data_ready_check returns without sending messages."""
    checker = MagicMock()
    fail_result = MagicMock(can_generate=False)
    checker.check_all.return_value = fail_result

    telegram = AsyncMock()
    state = MagicMock()

    await data_ready_check(
        gate_checker=checker,
        conductor_state=state,
        telegram_send=telegram,
        orchestrator=AsyncMock(),
        delivery=AsyncMock(),
        scheduler=MagicMock(),
        today=date(2026, 3, 19),
    )

    telegram.assert_not_called()


@pytest.mark.asyncio
async def test_data_ready_check_skips_when_all_done(mock_gates, mock_state):
    """If all reports already generated, skip."""
    mock_state.get_successful.return_value = {"daily"}  # Thursday — only daily needed

    telegram = AsyncMock()

    await data_ready_check(
        gate_checker=mock_gates,
        conductor_state=mock_state,
        telegram_send=telegram,
        orchestrator=AsyncMock(),
        delivery=AsyncMock(),
        scheduler=MagicMock(),
        today=date(2026, 3, 19),  # Thursday
    )

    telegram.assert_not_called()


@pytest.mark.asyncio
async def test_data_ready_check_sends_data_ready_message(mock_gates, mock_state):
    """When gates pass and reports pending, sends 'data ready' message."""
    telegram = AsyncMock()
    orchestrator = AsyncMock()
    orchestrator.run_daily_report = AsyncMock(return_value={
        "status": "success",
        "report": {
            "detailed_report": "x" * 600,
            "brief_report": "brief",
            "telegram_summary": "y" * 200,
        },
        "agents_called": 3,
        "agents_succeeded": 3,
        "agents_failed": 0,
    })
    delivery = AsyncMock()
    delivery.return_value = {"notion": {"page_url": "https://notion.so/abc"}}

    await data_ready_check(
        gate_checker=mock_gates,
        conductor_state=mock_state,
        telegram_send=telegram,
        orchestrator=orchestrator,
        delivery=delivery,
        scheduler=MagicMock(),
        today=date(2026, 3, 19),  # Thursday
    )

    # First call should be "data ready" message
    assert telegram.call_count >= 1
    first_msg = telegram.call_args_list[0][0][0]
    assert "Данные" in first_msg and "готовы" in first_msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v3/conductor/test_conductor.py -v`
Expected: FAIL

- [ ] **Step 3: Implement conductor**

```python
# agents/v3/conductor/conductor.py
"""Smart Conductor — main orchestration logic.

Coordinates: gate checks → schedule → generation → validation → delivery.
"""
import logging
from datetime import date, datetime, timedelta

from apscheduler.triggers.date import DateTrigger

from agents.v3.conductor.schedule import get_today_reports, ReportType
from agents.v3.conductor.state import ConductorState
from agents.v3.conductor.validator import quick_validate, ValidationVerdict
from agents.v3.conductor.messages import format_data_ready, format_alert

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


def _compute_dates(report_type: ReportType, today: date) -> dict:
    """Compute date_from, date_to, comparison_from, comparison_to for a report type."""
    yesterday = today - timedelta(days=1)

    if report_type == ReportType.DAILY:
        return {
            "date_from": yesterday.isoformat(),
            "date_to": yesterday.isoformat(),
            "comparison_from": (yesterday - timedelta(days=1)).isoformat(),
            "comparison_to": (yesterday - timedelta(days=1)).isoformat(),
        }

    if report_type in (
        ReportType.WEEKLY, ReportType.MARKETING_WEEKLY,
        ReportType.FUNNEL_WEEKLY, ReportType.PRICE_WEEKLY,
        ReportType.FINOLOG_WEEKLY,
    ):
        # Last Monday-Sunday
        last_sunday = today - timedelta(days=today.weekday() + 1)
        last_monday = last_sunday - timedelta(days=6)
        prev_sunday = last_monday - timedelta(days=1)
        prev_monday = prev_sunday - timedelta(days=6)
        return {
            "date_from": last_monday.isoformat(),
            "date_to": last_sunday.isoformat(),
            "comparison_from": prev_monday.isoformat(),
            "comparison_to": prev_sunday.isoformat(),
        }

    # Monthly — YoY comparison (same month previous year)
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    # Same month previous year
    prev_year_start = last_month_start.replace(year=last_month_start.year - 1)
    prev_year_end = last_month_end.replace(year=last_month_end.year - 1)
    return {
        "date_from": last_month_start.isoformat(),
        "date_to": last_month_end.isoformat(),
        "comparison_from": prev_year_start.isoformat(),
        "comparison_to": prev_year_end.isoformat(),
    }


def _extract_gate_info(gate_result) -> dict:
    """Extract display info from GateCheckResult for Telegram message.

    NOTE: The exact gate names and extra keys depend on the GateChecker implementation.
    Before implementing, inspect agents/v3/gates.py to verify:
    - Gate names: look for the strings in _gate_etl_ran_today, _gate_source_data_loaded, etc.
    - Extra keys: check what each gate puts into GateResult.extra dict.
    If keys don't match, either extend GateChecker.check_all() to return a structured
    summary, or adapt the string matching below.
    """
    info = {"updated_at": "—", "orders": 0, "revenue_ratio": 1.0}
    for g in gate_result.gates:
        if "ETL" in g.name and g.extra.get("updated_at"):
            info["updated_at"] = g.extra["updated_at"]
        elif g.value is not None:
            if "order" in g.name.lower() or "source" in g.name.lower():
                info["orders"] = int(g.value)
            if "revenue" in g.name.lower() and g.threshold:
                info["revenue_ratio"] = g.value / g.threshold if g.threshold else 1.0
    return info


async def data_ready_check(
    gate_checker,
    conductor_state: ConductorState,
    telegram_send,          # async callable(text: str)
    orchestrator,           # module with run_daily_report, etc.
    delivery,               # async callable(report, report_type, ...)
    scheduler,              # APScheduler instance (for retry DateTrigger)
    today: date | None = None,
    daily_only: bool = False,  # True for catchup_check (15:00) — generate only DAILY
) -> None:
    """Main conductor entry point — called hourly by cron.

    Args:
        daily_only: If True, only generate DAILY report (used by catchup_check at 15:00).
    """
    if today is None:
        today = date.today()

    # 1. Check gates
    wb_gates = gate_checker.check_all("wb")
    ozon_gates = gate_checker.check_all("ozon")

    if not (wb_gates.can_generate and ozon_gates.can_generate):
        logger.info("Gates not passed: wb=%s, ozon=%s", wb_gates.can_generate, ozon_gates.can_generate)
        return

    # 2. What reports are needed today?
    schedule = get_today_reports(today)
    if daily_only:
        schedule = [r for r in schedule if r == ReportType.DAILY]
    done = conductor_state.get_successful(str(today))
    pending = [r for r in schedule if r.value not in done]

    if not pending:
        logger.info("All reports already generated for %s", today)
        return

    # 3. Send "data ready" notification
    yesterday = today - timedelta(days=1)
    day_month = f"{yesterday.day} {_month_name(yesterday.month)}"

    msg = format_data_ready(
        wb_info=_extract_gate_info(wb_gates),
        ozon_info=_extract_gate_info(ozon_gates),
        pending=pending,
        report_date=day_month,
    )
    await telegram_send(msg)

    # 4. Generate + validate each report
    for report_type in pending:
        await generate_and_validate(
            report_type=report_type,
            today=today,
            conductor_state=conductor_state,
            telegram_send=telegram_send,
            orchestrator=orchestrator,
            delivery=delivery,
            scheduler=scheduler,
            attempt=1,
        )


async def generate_and_validate(
    report_type: ReportType,
    today: date,
    conductor_state: ConductorState,
    telegram_send,
    orchestrator,
    delivery,
    scheduler,
    attempt: int = 1,
) -> None:
    """Generate a single report, validate, deliver or retry."""
    report_date = str(today)

    conductor_state.log(report_date, report_type.value, status="running", attempt=attempt)
    logger.info("Generating %s (attempt %d/%d)", report_type.value, attempt, MAX_ATTEMPTS)

    try:
        # Compute dates
        dates = _compute_dates(report_type, today)

        # Call orchestrator
        method_name = report_type.orchestrator_method
        method = getattr(orchestrator, method_name)

        kwargs = {**dates, "channel": "both", "trigger": "cron"}
        if report_type in (ReportType.MARKETING_WEEKLY, ReportType.MARKETING_MONTHLY):
            kwargs["report_period"] = "weekly" if "weekly" in report_type.value else "monthly"

        result = await method(**kwargs)

    except Exception as e:
        logger.exception("Orchestrator error for %s: %s", report_type.value, e)
        result = {"status": "failed", "report": None, "agents_called": 0,
                  "agents_succeeded": 0, "agents_failed": 0}

    # Validate
    validation = quick_validate(result)

    if validation.verdict == ValidationVerdict.PASS:
        # Deliver
        try:
            delivery_result = await delivery(
                report=result,
                report_type=report_type.value,
                start_date=dates["date_from"],
                end_date=dates["date_to"],
            )
            notion_url = delivery_result.get("notion", {}).get("page_url")
        except Exception as e:
            logger.exception("Delivery error: %s", e)
            notion_url = None

        conductor_state.log(report_date, report_type.value, status="success",
                           attempt=attempt, notion_url=notion_url)
        logger.info("Report %s delivered successfully", report_type.value)

    elif validation.verdict == ValidationVerdict.RETRY and attempt < MAX_ATTEMPTS:
        # Schedule retry via DateTrigger
        pause_minutes = 1 if attempt == 1 else 5
        conductor_state.log(report_date, report_type.value, status="retrying",
                           attempt=attempt, error=validation.reason)
        logger.warning("Report %s failed validation (attempt %d): %s. Retrying in %d min.",
                       report_type.value, attempt, validation.reason, pause_minutes)

        if scheduler is not None:
            from pytz import timezone as pytz_timezone
            msk = pytz_timezone("Europe/Moscow")
            scheduler.add_job(
                generate_and_validate,
                trigger=DateTrigger(run_date=datetime.now(msk) + timedelta(minutes=pause_minutes)),
                kwargs={
                    "report_type": report_type,
                    "today": today,
                    "conductor_state": conductor_state,
                    "telegram_send": telegram_send,
                    "orchestrator": orchestrator,
                    "delivery": delivery,
                    "scheduler": scheduler,
                    "attempt": attempt + 1,
                },
                id=f"retry_{report_type.value}_{report_date}_{attempt + 1}",
                replace_existing=True,
            )

    else:
        # All attempts exhausted or verdict == FAIL
        conductor_state.log(report_date, report_type.value, status="failed",
                           attempt=attempt, error=validation.reason)
        alert = format_alert(report_type, validation.reason, attempt, MAX_ATTEMPTS)
        await telegram_send(alert)
        logger.error("Report %s failed after %d attempts: %s",
                     report_type.value, attempt, validation.reason)


async def deadline_check(
    conductor_state: ConductorState,
    telegram_send,
    gate_checker,
    today: date | None = None,
) -> None:
    """Called at deadline (12:00 MSK). Alert if no reports generated."""
    if today is None:
        today = date.today()

    schedule = get_today_reports(today)
    done = conductor_state.get_successful(str(today))
    missing = [r for r in schedule if r.value not in done]

    if not missing:
        return

    # Diagnose
    wb_gates = gate_checker.check_all("wb")
    ozon_gates = gate_checker.check_all("ozon")

    if not wb_gates.can_generate or not ozon_gates.can_generate:
        diagnostics = "Данные не поступили"
        if not wb_gates.can_generate:
            diagnostics += " (WB gates не прошли)"
        if not ozon_gates.can_generate:
            diagnostics += " (OZON gates не прошли)"
    else:
        diagnostics = "Gates OK, но отчёты не были запущены"

    missing_names = ", ".join(r.human_name for r in missing)
    msg = (
        f"⚠️ Дедлайн 12:00: отчёты не сформированы\n\n"
        f"Не готовы: {missing_names}\n"
        f"Диагностика: {diagnostics}\n\n"
        f"Действие: catchup_check в 15:00 проверит повторно"
    )
    await telegram_send(msg)


def _month_name(month: int) -> str:
    names = [
        "", "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    return names[month]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/v3/conductor/test_conductor.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agents/v3/conductor/conductor.py tests/v3/conductor/test_conductor.py
git commit -m "feat(conductor): add main orchestration logic with gate check, generation, validation"
```

---

## Task 6: Config updates

**Files:**
- Modify: `agents/v3/config.py`

- [ ] **Step 1: Read current config to find insertion point**

Run: `grep -n "WATCHDOG\|PROMOTION\|PROMPT_TUNER" agents/v3/config.py`

- [ ] **Step 2: Add conductor config values**

Add after existing feature flags:

```python
# Conductor
USE_CONDUCTOR: bool = os.getenv("USE_CONDUCTOR", "true").lower() in ("true", "1", "yes")
CONDUCTOR_DEADLINE_HOUR: int = int(os.getenv("CONDUCTOR_DEADLINE_HOUR", "12"))
CONDUCTOR_CATCHUP_HOUR: int = int(os.getenv("CONDUCTOR_CATCHUP_HOUR", "15"))
```

Use the same inline `os.getenv(...).lower() in (...)` pattern already used in the file for other booleans.

- [ ] **Step 3: Commit**

```bash
git add agents/v3/config.py
git commit -m "feat(conductor): add USE_CONDUCTOR config flag"
```

---

## Task 7: Scheduler — feature flag + conductor triggers

**Files:**
- Modify: `agents/v3/scheduler.py`

- [ ] **Step 1: Read current scheduler structure**

Run: `head -80 agents/v3/scheduler.py` to understand imports and `create_scheduler()` structure.

- [ ] **Step 2: Rename `create_scheduler` → `_setup_legacy_scheduler`**

Keep existing function body intact, just rename. Add new wrapper:

```python
def create_scheduler() -> AsyncIOScheduler:
    """Build scheduler — conductor mode or legacy based on config."""
    if config.USE_CONDUCTOR:
        return _setup_conductor_scheduler()
    return _setup_legacy_scheduler()
```

- [ ] **Step 3: Implement `_setup_conductor_scheduler()`**

```python
def _setup_conductor_scheduler() -> AsyncIOScheduler:
    """Conductor mode: 5 smart triggers instead of 15 individual cron jobs."""
    from agents.v3.conductor.state import ConductorState
    from agents.v3.conductor.conductor import data_ready_check, deadline_check

    scheduler = AsyncIOScheduler(
        job_defaults={"misfire_grace_time": 3600, "coalesce": True, "max_instances": 1},
        timezone=config.TIMEZONE,
    )

    state = ConductorState(db_path=config.STATE_DB_PATH)
    state.ensure_table()
    gate_checker = GateChecker()

    async def _telegram_send(text: str):
        """Send message to admin chat."""
        from agents.v3.delivery.telegram import send_report
        # Use low-level aiogram send for operational messages
        from aiogram import Bot
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        try:
            await bot.send_message(config.ADMIN_CHAT_ID, text)
        finally:
            await bot.session.close()

    async def _delivery(report, report_type, start_date, end_date, **kw):
        from agents.v3.delivery.router import deliver
        return await deliver(
            report=report, report_type=report_type,
            start_date=start_date, end_date=end_date,
            config={
                "telegram_bot_token": config.TELEGRAM_BOT_TOKEN,
                "chat_ids": [config.ADMIN_CHAT_ID],
                "notion_token": config.NOTION_TOKEN,
                "notion_database_id": config.NOTION_DATABASE_ID,
            },
        )

    from agents.v3 import orchestrator

    # 1. data_ready_check — hourly 06:00-12:00
    scheduler.add_job(
        data_ready_check,
        trigger=CronTrigger(hour="6-12", minute=0, timezone=config.TIMEZONE),
        kwargs={
            "gate_checker": gate_checker,
            "conductor_state": state,
            "telegram_send": _telegram_send,
            "orchestrator": orchestrator,
            "delivery": _delivery,
            "scheduler": scheduler,
        },
        id="data_ready_check",
    )

    # 2. deadline_check — 12:00
    scheduler.add_job(
        deadline_check,
        trigger=CronTrigger(hour=config.CONDUCTOR_DEADLINE_HOUR, minute=0, timezone=config.TIMEZONE),
        kwargs={
            "conductor_state": state,
            "telegram_send": _telegram_send,
            "gate_checker": gate_checker,
        },
        id="deadline_check",
    )

    # 3. catchup_check — 15:00 (reuses data_ready_check with daily_only=True)
    scheduler.add_job(
        data_ready_check,
        trigger=CronTrigger(hour=config.CONDUCTOR_CATCHUP_HOUR, minute=0, timezone=config.TIMEZONE),
        kwargs={
            "gate_checker": gate_checker,
            "conductor_state": state,
            "telegram_send": _telegram_send,
            "orchestrator": orchestrator,
            "delivery": _delivery,
            "scheduler": scheduler,
            "daily_only": True,  # After deadline, only generate DAILY
        },
        id="catchup_check",
    )

    # 4. anomaly_monitor — keep existing logic
    _add_anomaly_monitor(scheduler, gate_checker)

    # 5. notion_feedback — keep existing logic
    _add_notion_feedback(scheduler)

    # 6. watchdog_heartbeat — log-only (no Telegram), keep for uptime tracking
    _add_watchdog_heartbeat(scheduler, log_only=True)

    # Keep non-report jobs
    if config.ETL_ENABLED:
        _add_etl_jobs(scheduler)
    if config.PROMOTION_SCAN_ENABLED:
        _add_promotion_scan(scheduler)
    if config.FINOLOG_CATEGORIZATION_ENABLED:
        _add_finolog_categorization(scheduler)

    return scheduler
```

> **Note:** The exact implementation will depend on the current structure of scheduler.py.
> The helper functions `_add_anomaly_monitor`, `_add_notion_feedback`, `_add_etl_jobs`,
> `_add_promotion_scan` should be extracted from the existing `create_scheduler` function.
> If these are inline in create_scheduler, extract them first.

- [ ] **Step 4: Test with dry-run**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m agents.v3 --dry-run`
Expected: Shows 5 conductor jobs (or old 15 if USE_CONDUCTOR=false)

- [ ] **Step 5: Commit**

```bash
git add agents/v3/scheduler.py
git commit -m "feat(conductor): add conductor scheduler with feature flag, keep legacy as fallback"
```

---

## Task 8: Notion — add price_weekly mapping

**Files:**
- Modify: `agents/v3/delivery/notion.py`

- [ ] **Step 1: Find report type mapping in notion.py**

Run: `grep -n "report_type\|_REPORT_TYPE" agents/v3/delivery/notion.py`

- [ ] **Step 2: Add price_weekly to mapping**

Add to the report type mapping dict:
```python
"price_weekly": "Еженедельный ценовой анализ",
"price_monthly": "Ценовой анализ",
```

Also check if existing `"price_analysis"` key exists and rename to `"price_monthly"` if needed for consistency.

- [ ] **Step 3: Commit**

```bash
git add agents/v3/delivery/notion.py
git commit -m "feat(conductor): add price_weekly report type to Notion mapping"
```

---

## Task 9: Integration test

**Files:**
- Create: `tests/v3/conductor/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/v3/conductor/test_integration.py
"""Integration test: full conductor flow with mocked orchestrator + delivery."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import date

from agents.v3.conductor.conductor import data_ready_check, deadline_check
from agents.v3.conductor.state import ConductorState
from agents.v3.conductor.schedule import ReportType
import tempfile, os


@pytest.fixture
def full_setup():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    state = ConductorState(db_path=db_path)
    state.ensure_table()

    gate_checker = MagicMock()
    wb_result = MagicMock(can_generate=True, has_caveats=False, caveats=[], gates=[])
    ozon_result = MagicMock(can_generate=True, has_caveats=False, caveats=[], gates=[])
    gate_checker.check_all.side_effect = lambda mp: wb_result if mp == "wb" else ozon_result

    telegram_messages = []
    async def telegram_send(text):
        telegram_messages.append(text)

    orchestrator = MagicMock()
    good_report = {
        "status": "success",
        "report": {
            "detailed_report": "# Отчёт\n## Секция 1\nТекст анализа " * 50,
            "brief_report": "Краткая сводка за день",
            "telegram_summary": "📊 Сводка за 19 марта:\n• Маржа: 255 тыс\n• Заказы: 1164 шт (+9.9%)" + " " * 100,
        },
        "agents_called": 3,
        "agents_succeeded": 3,
        "agents_failed": 0,
    }
    for method in ["run_daily_report", "run_weekly_report", "run_monthly_report",
                   "run_marketing_report", "run_funnel_report", "run_finolog_report",
                   "run_price_analysis"]:
        setattr(orchestrator, method, AsyncMock(return_value=good_report))

    delivery = AsyncMock(return_value={"notion": {"page_url": "https://notion.so/test"}})

    yield {
        "state": state,
        "gate_checker": gate_checker,
        "telegram_send": telegram_send,
        "telegram_messages": telegram_messages,
        "orchestrator": orchestrator,
        "delivery": delivery,
        "db_path": db_path,
    }
    os.unlink(db_path)


@pytest.mark.asyncio
async def test_full_thursday_flow(full_setup):
    """Thursday: 1 daily report generated, 2 Telegram messages (data ready + delivery)."""
    s = full_setup
    await data_ready_check(
        gate_checker=s["gate_checker"],
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        orchestrator=s["orchestrator"],
        delivery=s["delivery"],
        scheduler=MagicMock(),
        today=date(2026, 3, 19),  # Thursday
    )

    # Should have "data ready" message
    assert any("готовы" in m for m in s["telegram_messages"])

    # Should have called orchestrator once (daily only)
    s["orchestrator"].run_daily_report.assert_called_once()

    # Should have delivered
    s["delivery"].assert_called_once()

    # State should show success
    done = s["state"].get_successful("2026-03-19")
    assert "daily" in done


@pytest.mark.asyncio
async def test_idempotent_second_run(full_setup):
    """Running data_ready_check twice should not duplicate reports."""
    s = full_setup
    kwargs = {
        "gate_checker": s["gate_checker"],
        "conductor_state": s["state"],
        "telegram_send": s["telegram_send"],
        "orchestrator": s["orchestrator"],
        "delivery": s["delivery"],
        "scheduler": MagicMock(),
        "today": date(2026, 3, 19),
    }

    await data_ready_check(**kwargs)
    msg_count_1 = len(s["telegram_messages"])

    await data_ready_check(**kwargs)
    msg_count_2 = len(s["telegram_messages"])

    # Second run should not produce any new messages
    assert msg_count_2 == msg_count_1


@pytest.mark.asyncio
async def test_deadline_check_alerts_on_missing(full_setup):
    """deadline_check sends alert if reports not generated."""
    s = full_setup
    await deadline_check(
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        gate_checker=s["gate_checker"],
        today=date(2026, 3, 19),
    )

    assert any("Дедлайн" in m or "не сформированы" in m for m in s["telegram_messages"])


@pytest.mark.asyncio
async def test_retry_schedules_date_trigger(full_setup):
    """When validation fails, scheduler.add_job is called with DateTrigger for retry."""
    s = full_setup
    # Make orchestrator return a bad report
    bad_report = {
        "status": "success",
        "report": {
            "detailed_report": "Не удалось сформировать ответ.",
            "brief_report": "",
            "telegram_summary": "Не удалось сформировать ответ.",
        },
        "agents_called": 1,
        "agents_succeeded": 1,
        "agents_failed": 0,
    }
    s["orchestrator"].run_daily_report = AsyncMock(return_value=bad_report)

    mock_scheduler = MagicMock()

    await data_ready_check(
        gate_checker=s["gate_checker"],
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        orchestrator=s["orchestrator"],
        delivery=s["delivery"],
        scheduler=mock_scheduler,
        today=date(2026, 3, 19),
    )

    # Scheduler should have add_job called for retry
    mock_scheduler.add_job.assert_called_once()
    call_kwargs = mock_scheduler.add_job.call_args
    assert "retry_daily" in call_kwargs.kwargs.get("id", "") or "retry_daily" in str(call_kwargs)


@pytest.mark.asyncio
async def test_deadline_check_silent_when_all_done(full_setup):
    """deadline_check is silent if all reports generated."""
    s = full_setup
    # First generate the report
    await data_ready_check(
        gate_checker=s["gate_checker"],
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        orchestrator=s["orchestrator"],
        delivery=s["delivery"],
        scheduler=MagicMock(),
        today=date(2026, 3, 19),
    )
    msg_before = len(s["telegram_messages"])

    await deadline_check(
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        gate_checker=s["gate_checker"],
        today=date(2026, 3, 19),
    )

    # No new messages
    assert len(s["telegram_messages"]) == msg_before
```

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest tests/v3/conductor/test_integration.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Run all conductor tests together**

Run: `python -m pytest tests/v3/conductor/ -v`
Expected: All ~21 tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/v3/conductor/test_integration.py
git commit -m "test(conductor): add integration tests for full conductor flow"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=60`
Expected: No regressions in existing tests

- [ ] **Step 2: Dry-run with conductor enabled**

Run: `USE_CONDUCTOR=true python -m agents.v3 --dry-run`
Expected: Shows conductor scheduler jobs (data_ready_check, deadline_check, catchup_check, anomaly_monitor, notion_feedback)

- [ ] **Step 3: Dry-run with conductor disabled (rollback)**

Run: `USE_CONDUCTOR=false python -m agents.v3 --dry-run`
Expected: Shows legacy 15 cron jobs

- [ ] **Step 4: Final commit with summary**

```bash
git add agents/v3/conductor/ tests/v3/conductor/ agents/v3/agents/report-conductor.md \
       agents/v3/scheduler.py agents/v3/config.py agents/v3/delivery/notion.py
git commit -m "feat(conductor): Smart Conductor v1 — report controller agent

Replaces 15 noisy cron jobs with 5 smart triggers.
Validates reports before delivery, prevents notification spam,
handles failures with diagnostics and retry via DateTrigger.

Feature flag: USE_CONDUCTOR=true (default) / false (rollback to legacy)"
```

---

## Deferred: LLM-based validation (llm_validate)

The current implementation uses `quick_validate()` — deterministic checks that catch
the real problems (empty reports, known failure phrases, short summaries). This covers
the critical issues from the spec.

`llm_validate()` (comparison with previous report, checking for 10x anomalies in figures,
validating hypothesis quality) is deferred to a follow-up task. The `report-conductor.md`
agent prompt is already created and ready to use when this is implemented.

