# Reporter V4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace broken V3 multi-agent reporting system with a reliable single-LLM pipeline (Collect → Analyze → Format → Validate → Deliver).

**Architecture:** Deterministic DataCollectors (Python/SQL via shared/data_layer) gather all metrics upfront. A single LLM call (Gemini 2.5 Flash via OpenRouter) returns structured Pydantic output. Jinja2 templates render Notion markdown and Telegram HTML. Supabase stores state, playbook rules, and notification dedup. Three cron jobs replace fifteen.

**Tech Stack:** Python 3.11+, asyncio, Pydantic v2, Jinja2, aiogram 3.x, APScheduler, supabase-py, OpenRouter (openai SDK), psycopg2 (existing data_layer)

**Spec:** `docs/superpowers/specs/2026-03-28-reporter-v4-design.md`

---

## File Structure

```
agents/reporter/
├── __init__.py
├── __main__.py                  # Entry point: scheduler + bot
├── config.py                    # V4 configuration (env vars, models, thresholds)
├── types.py                     # ReportType enum, ReportScope dataclass
├── pipeline.py                  # run_pipeline(): collect → analyze → format → validate
├── conductor.py                 # run_report(), data_ready_check(), deadline_check()
├── scheduler.py                 # APScheduler: 3 cron jobs
├── gates.py                     # Copied from v3/gates.py with minimal changes
├── state.py                     # Supabase client: report_runs, analytics_rules, notification_log
├── collector/
│   ├── __init__.py
│   ├── base.py                  # BaseCollector ABC, CollectedData model
│   ├── financial.py             # FinancialCollector
│   ├── marketing.py             # MarketingCollector
│   └── funnel.py                # FunnelCollector
├── analyst/
│   ├── __init__.py
│   ├── analyst.py               # analyze(): single LLM call, returns ReportInsights
│   ├── schemas.py               # Pydantic: ReportInsights, SectionInsight, MetricChange, etc.
│   ├── circuit_breaker.py       # CircuitBreaker: CLOSED → OPEN → HALF_OPEN
│   └── prompts/                 # 7 markdown prompt files
│       ├── financial_daily.md
│       ├── financial_weekly.md
│       ├── financial_monthly.md
│       ├── marketing_weekly.md
│       ├── marketing_monthly.md
│       ├── funnel_weekly.md
│       └── funnel_monthly.md
├── formatter/
│   ├── __init__.py
│   ├── notion.py                # Jinja2 → Notion markdown with toggle sections
│   ├── telegram.py              # Jinja2 → Telegram HTML summary
│   └── templates/               # 7 Jinja2 template files
│       ├── financial_daily.md.j2
│       ├── financial_weekly.md.j2
│       ├── financial_monthly.md.j2
│       ├── marketing_weekly.md.j2
│       ├── marketing_monthly.md.j2
│       ├── funnel_weekly.md.j2
│       └── funnel_monthly.md.j2
├── playbook/
│   ├── __init__.py
│   ├── loader.py                # Load active rules from Supabase
│   └── updater.py               # Save LLM-discovered patterns as pending_review
├── delivery/
│   ├── __init__.py
│   ├── notion.py                # upsert_notion(): find → clear → append
│   └── telegram.py              # send_or_edit(): edit existing or send new
├── bot/
│   ├── __init__.py
│   ├── bot.py                   # aiogram 3.x polling + dispatcher setup
│   ├── handlers.py              # /status, /run, /rules, /pending, /logs, /health
│   └── keyboards.py             # Inline keyboards for playbook review
└── MIGRATION.md                 # Kill switch checklist
```

**Tests:**
```
tests/reporter/
├── __init__.py
├── test_types.py
├── test_config.py
├── test_schemas.py
├── test_circuit_breaker.py
├── test_state.py
├── test_collector_financial.py
├── test_collector_marketing.py
├── test_collector_funnel.py
├── test_analyst.py
├── test_formatter_notion.py
├── test_formatter_telegram.py
├── test_validator.py
├── test_playbook.py
├── test_pipeline.py
├── test_conductor.py
└── test_delivery.py
```

---

## Wave 1: Foundation

### Task 1: Config & Types

**Files:**
- Create: `agents/reporter/__init__.py`
- Create: `agents/reporter/config.py`
- Create: `agents/reporter/types.py`
- Test: `tests/reporter/__init__.py`
- Test: `tests/reporter/test_types.py`

- [ ] **Step 1: Create package init**

```python
# agents/reporter/__init__.py
"""Wookiee Reporter V4 — single-LLM reporting pipeline."""
```

- [ ] **Step 2: Write config.py**

```python
# agents/reporter/config.py
"""Reporter V4 configuration — all settings from environment."""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── OpenRouter LLM ────────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
MODEL_PRIMARY: str = os.getenv("REPORTER_MODEL_PRIMARY", "google/gemini-2.5-flash")
MODEL_FALLBACK: str = os.getenv("REPORTER_MODEL_FALLBACK", "google/gemini-2.5-pro-preview-03-25")
MODEL_FREE: str = "openrouter/free"

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("REPORTER_V4_BOT_TOKEN", "")
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))

# ── Notion ────────────────────────────────────────────────────────────────────
NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "")

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# ── Database (read-only analytics) ────────────────────────────────────────────
DB_HOST: str = os.getenv("DB_HOST", "")
DB_PORT: int = int(os.getenv("DB_PORT", "6433"))

# ── Timezone & Schedule ───────────────────────────────────────────────────────
TIMEZONE: str = "Europe/Moscow"
DATA_READY_CHECK_HOURS: list[int] = [6, 7, 8, 9, 10, 11, 12]
DEADLINE_HOUR: int = 13
HEARTBEAT_INTERVAL_HOURS: int = 6

# ── Circuit Breaker ───────────────────────────────────────────────────────────
CB_FAILURE_THRESHOLD: int = 3
CB_COOLDOWN_SEC: float = 3600.0

# ── Validator ─────────────────────────────────────────────────────────────────
MIN_TOGGLE_SECTIONS: int = 6
MIN_REPORT_LENGTH: int = 500
MIN_CONFIDENCE: float = 0.3
MAX_PLACEHOLDERS: int = 5

# ── Pipeline ──────────────────────────────────────────────────────────────────
MAX_ATTEMPTS: int = 3
LLM_TIMEOUT: float = 120.0
LLM_MAX_TOKENS: int = 8000

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Paths ─────────────────────────────────────────────────────────────────────
PROMPTS_DIR: Path = Path(__file__).parent / "analyst" / "prompts"
TEMPLATES_DIR: Path = Path(__file__).parent / "formatter" / "templates"
```

- [ ] **Step 3: Write types.py**

```python
# agents/reporter/types.py
"""Core types: ReportType enum and ReportScope dataclass."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


class ReportType(str, Enum):
    FINANCIAL_DAILY = "financial_daily"
    FINANCIAL_WEEKLY = "financial_weekly"
    FINANCIAL_MONTHLY = "financial_monthly"
    MARKETING_WEEKLY = "marketing_weekly"
    MARKETING_MONTHLY = "marketing_monthly"
    FUNNEL_WEEKLY = "funnel_weekly"
    FUNNEL_MONTHLY = "funnel_monthly"

    @property
    def collector_kind(self) -> str:
        """Return collector category: 'financial', 'marketing', or 'funnel'."""
        return self.value.rsplit("_", 1)[0].split("_")[0]

    @property
    def period_kind(self) -> str:
        """Return period: 'daily', 'weekly', or 'monthly'."""
        return self.value.rsplit("_", 1)[-1]

    @property
    def human_name(self) -> str:
        names = {
            "financial_daily": "Дневной фин. отчёт",
            "financial_weekly": "Недельный фин. отчёт",
            "financial_monthly": "Месячный фин. отчёт",
            "marketing_weekly": "Маркетинг (неделя)",
            "marketing_monthly": "Маркетинг (месяц)",
            "funnel_weekly": "Воронка (неделя)",
            "funnel_monthly": "Воронка (месяц)",
        }
        return names[self.value]

    @property
    def notion_label(self) -> str:
        labels = {
            "financial_daily": "Ежедневный фин анализ",
            "financial_weekly": "Еженедельный фин анализ",
            "financial_monthly": "Ежемесячный фин анализ",
            "marketing_weekly": "Маркетинговый анализ (неделя)",
            "marketing_monthly": "Маркетинговый анализ (месяц)",
            "funnel_weekly": "Воронка продаж (неделя)",
            "funnel_monthly": "Воронка продаж (месяц)",
        }
        return labels[self.value]


@dataclass(frozen=True)
class ReportScope:
    report_type: ReportType
    period_from: date
    period_to: date
    comparison_from: date
    comparison_to: date
    marketplace: str = "all"      # "wb", "ozon", "all"
    legal_entity: str = "all"     # "IP", "OOO", "all"
    model: Optional[str] = None
    article: Optional[str] = None

    @property
    def scope_hash(self) -> str:
        parts = [
            self.period_from.isoformat(),
            self.period_to.isoformat(),
            self.report_type.value,
            self.marketplace,
            self.legal_entity,
            self.model or "",
            self.article or "",
        ]
        return hashlib.md5("|".join(parts).encode()).hexdigest()[:12]

    @property
    def period_str(self) -> str:
        if self.period_from == self.period_to:
            return self.period_from.isoformat()
        return f"{self.period_from.isoformat()} — {self.period_to.isoformat()}"

    def to_dict(self) -> dict:
        return {
            "report_type": self.report_type.value,
            "period_from": self.period_from.isoformat(),
            "period_to": self.period_to.isoformat(),
            "comparison_from": self.comparison_from.isoformat(),
            "comparison_to": self.comparison_to.isoformat(),
            "marketplace": self.marketplace,
            "legal_entity": self.legal_entity,
            "model": self.model,
            "article": self.article,
        }


def compute_scope(report_type: ReportType, today: date) -> ReportScope:
    """Compute default scope for a report type based on today's date."""
    from datetime import timedelta

    if report_type.period_kind == "daily":
        yesterday = today - timedelta(days=1)
        day_before = yesterday - timedelta(days=1)
        return ReportScope(
            report_type=report_type,
            period_from=yesterday,
            period_to=yesterday,
            comparison_from=day_before,
            comparison_to=day_before,
        )
    elif report_type.period_kind == "weekly":
        # Last full week (Mon-Sun)
        days_since_monday = today.weekday()
        last_sunday = today - timedelta(days=days_since_monday)
        last_monday = last_sunday - timedelta(days=6)
        prev_sunday = last_monday - timedelta(days=1)
        prev_monday = prev_sunday - timedelta(days=6)
        return ReportScope(
            report_type=report_type,
            period_from=last_monday,
            period_to=last_sunday,
            comparison_from=prev_monday,
            comparison_to=prev_sunday,
        )
    else:  # monthly
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        prev_month_end = last_month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        return ReportScope(
            report_type=report_type,
            period_from=last_month_start,
            period_to=last_month_end,
            comparison_from=prev_month_start,
            comparison_to=prev_month_end,
        )


def get_today_reports(today: date) -> list[ReportType]:
    """Which reports should run today."""
    reports = [ReportType.FINANCIAL_DAILY]

    if today.weekday() == 0:  # Monday
        reports.extend([
            ReportType.FINANCIAL_WEEKLY,
            ReportType.MARKETING_WEEKLY,
            ReportType.FUNNEL_WEEKLY,
        ])
        # First Monday of month (day 1-7)
        if today.day <= 7:
            reports.extend([
                ReportType.FINANCIAL_MONTHLY,
                ReportType.MARKETING_MONTHLY,
                ReportType.FUNNEL_MONTHLY,
            ])

    return reports
```

- [ ] **Step 4: Write test for types**

```python
# tests/reporter/__init__.py
```

```python
# tests/reporter/test_types.py
"""Tests for ReportType, ReportScope, compute_scope, get_today_reports."""
from datetime import date

from agents.reporter.types import (
    ReportScope,
    ReportType,
    compute_scope,
    get_today_reports,
)


def test_report_type_collector_kind():
    assert ReportType.FINANCIAL_DAILY.collector_kind == "financial"
    assert ReportType.MARKETING_WEEKLY.collector_kind == "marketing"
    assert ReportType.FUNNEL_MONTHLY.collector_kind == "funnel"


def test_report_type_period_kind():
    assert ReportType.FINANCIAL_DAILY.period_kind == "daily"
    assert ReportType.FINANCIAL_WEEKLY.period_kind == "weekly"
    assert ReportType.FINANCIAL_MONTHLY.period_kind == "monthly"


def test_scope_hash_deterministic():
    scope = ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )
    assert scope.scope_hash == scope.scope_hash
    assert len(scope.scope_hash) == 12


def test_scope_hash_differs_with_marketplace():
    base = dict(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )
    s1 = ReportScope(**base, marketplace="wb")
    s2 = ReportScope(**base, marketplace="ozon")
    assert s1.scope_hash != s2.scope_hash


def test_compute_scope_daily():
    scope = compute_scope(ReportType.FINANCIAL_DAILY, date(2026, 3, 28))
    assert scope.period_from == date(2026, 3, 27)
    assert scope.period_to == date(2026, 3, 27)
    assert scope.comparison_from == date(2026, 3, 26)
    assert scope.comparison_to == date(2026, 3, 26)


def test_compute_scope_weekly():
    # Monday March 30 2026
    scope = compute_scope(ReportType.FINANCIAL_WEEKLY, date(2026, 3, 30))
    assert scope.period_from == date(2026, 3, 23)  # last Monday
    assert scope.period_to == date(2026, 3, 29)    # last Sunday
    assert scope.comparison_from == date(2026, 3, 16)
    assert scope.comparison_to == date(2026, 3, 22)


def test_compute_scope_monthly():
    scope = compute_scope(ReportType.FINANCIAL_MONTHLY, date(2026, 4, 6))
    assert scope.period_from == date(2026, 3, 1)
    assert scope.period_to == date(2026, 3, 31)
    assert scope.comparison_from == date(2026, 2, 1)
    assert scope.comparison_to == date(2026, 2, 28)


def test_get_today_reports_tuesday():
    reports = get_today_reports(date(2026, 3, 24))  # Tuesday
    assert reports == [ReportType.FINANCIAL_DAILY]


def test_get_today_reports_monday():
    reports = get_today_reports(date(2026, 3, 30))  # Monday, not first of month
    assert ReportType.FINANCIAL_WEEKLY in reports
    assert ReportType.MARKETING_WEEKLY in reports
    assert ReportType.FUNNEL_WEEKLY in reports
    assert ReportType.FINANCIAL_MONTHLY not in reports


def test_get_today_reports_first_monday():
    reports = get_today_reports(date(2026, 4, 6))  # First Monday of April
    assert ReportType.FINANCIAL_MONTHLY in reports
    assert ReportType.MARKETING_MONTHLY in reports
    assert ReportType.FUNNEL_MONTHLY in reports


def test_scope_to_dict_roundtrip():
    scope = ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
        marketplace="wb",
        model="wendy",
    )
    d = scope.to_dict()
    assert d["marketplace"] == "wb"
    assert d["model"] == "wendy"
    assert d["report_type"] == "financial_daily"
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/reporter/test_types.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add agents/reporter/__init__.py agents/reporter/config.py agents/reporter/types.py tests/reporter/
git commit -m "feat(reporter): add V4 config and core types (ReportType, ReportScope)"
```

---

### Task 2: Pydantic Schemas (ReportInsights)

**Files:**
- Create: `agents/reporter/analyst/__init__.py`
- Create: `agents/reporter/analyst/schemas.py`
- Test: `tests/reporter/test_schemas.py`

- [ ] **Step 1: Write schemas.py**

```python
# agents/reporter/analyst/__init__.py
```

```python
# agents/reporter/analyst/schemas.py
"""Pydantic models for LLM structured output."""
from __future__ import annotations

from pydantic import BaseModel, Field


class MetricChange(BaseModel):
    metric: str = Field(description="Metric name: revenue, margin_pct, drr, orders, etc.")
    current: float
    previous: float
    delta_pct: float = Field(description="Percentage change from previous to current")
    direction: str = Field(description="up, down, or flat")


class RootCause(BaseModel):
    description: str = Field(description="Root cause explanation in Russian")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(description="Specific data points supporting this cause")
    recommendation: str = Field(description="Actionable recommendation in Russian")


class SectionInsight(BaseModel):
    section_id: int = Field(ge=0, le=12)
    title: str
    summary: str = Field(description="2-3 sentence summary in Russian")
    key_changes: list[MetricChange] = Field(default_factory=list)
    root_causes: list[RootCause] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)


class DiscoveredPattern(BaseModel):
    pattern: str = Field(description="Pattern description in Russian")
    evidence: str
    suggested_action: str
    confidence: float = Field(ge=0.0, le=1.0)


class ReportInsights(BaseModel):
    executive_summary: str = Field(description="3-5 sentences for Telegram, in Russian")
    sections: list[SectionInsight]
    discovered_patterns: list[DiscoveredPattern] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    analysis_notes: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Write test**

```python
# tests/reporter/test_schemas.py
"""Tests for Pydantic schema validation."""
from agents.reporter.analyst.schemas import (
    DiscoveredPattern,
    MetricChange,
    ReportInsights,
    RootCause,
    SectionInsight,
)


def test_metric_change_valid():
    mc = MetricChange(
        metric="revenue",
        current=1_000_000,
        previous=900_000,
        delta_pct=11.1,
        direction="up",
    )
    assert mc.metric == "revenue"


def test_section_insight_defaults():
    si = SectionInsight(
        section_id=1,
        title="Executive Summary",
        summary="Тестовый раздел",
    )
    assert si.key_changes == []
    assert si.root_causes == []
    assert si.anomalies == []


def test_report_insights_full():
    ri = ReportInsights(
        executive_summary="Выручка выросла на 11%",
        sections=[
            SectionInsight(
                section_id=0,
                title="Паспорт",
                summary="Период: 27.03.2026",
            ),
        ],
        discovered_patterns=[
            DiscoveredPattern(
                pattern="ДРР > 20% коррелирует с падением маржи",
                evidence="Wendy: DRR 22%, margin -6%",
                suggested_action="Снизить ставки",
                confidence=0.8,
            ),
        ],
        overall_confidence=0.85,
    )
    assert len(ri.sections) == 1
    assert len(ri.discovered_patterns) == 1
    assert ri.overall_confidence == 0.85


def test_report_insights_json_schema():
    schema = ReportInsights.model_json_schema()
    assert "properties" in schema
    assert "executive_summary" in schema["properties"]
    assert "sections" in schema["properties"]
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/reporter/test_schemas.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add agents/reporter/analyst/ tests/reporter/test_schemas.py
git commit -m "feat(reporter): add Pydantic schemas for LLM structured output"
```

---

### Task 3: Circuit Breaker

**Files:**
- Create: `agents/reporter/analyst/circuit_breaker.py`
- Test: `tests/reporter/test_circuit_breaker.py`

- [ ] **Step 1: Write test**

```python
# tests/reporter/test_circuit_breaker.py
"""Tests for CircuitBreaker state machine."""
import time
from unittest.mock import patch

from agents.reporter.analyst.circuit_breaker import CircuitBreaker, CircuitState


def test_initial_state_closed():
    cb = CircuitBreaker(failure_threshold=3, cooldown_sec=60)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute


def test_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=2, cooldown_sec=60)
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert not cb.can_execute


def test_half_open_after_cooldown():
    cb = CircuitBreaker(failure_threshold=1, cooldown_sec=0.1)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    time.sleep(0.15)
    assert cb.can_execute  # transitions to HALF_OPEN
    assert cb.state == CircuitState.HALF_OPEN


def test_success_resets_to_closed():
    cb = CircuitBreaker(failure_threshold=2, cooldown_sec=0.1)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    time.sleep(0.15)
    _ = cb.can_execute  # HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


def test_failure_in_half_open_reopens():
    cb = CircuitBreaker(failure_threshold=1, cooldown_sec=0.1)
    cb.record_failure()
    time.sleep(0.15)
    _ = cb.can_execute  # HALF_OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
```

- [ ] **Step 2: Write implementation**

```python
# agents/reporter/analyst/circuit_breaker.py
"""Circuit breaker for LLM calls — stops retrying after N failures."""
from __future__ import annotations

import time
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Stopped — too many failures
    HALF_OPEN = "half_open" # Testing with single request


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_sec: float = 3600.0):
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self._last_failure_time: float = 0.0

    @property
    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.cooldown_sec:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow one try
        return True

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self._last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/reporter/test_circuit_breaker.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add agents/reporter/analyst/circuit_breaker.py tests/reporter/test_circuit_breaker.py
git commit -m "feat(reporter): add circuit breaker for LLM call protection"
```

---

### Task 4: Supabase State Manager

**Files:**
- Create: `agents/reporter/state.py`
- Test: `tests/reporter/test_state.py`

- [ ] **Step 1: Write test**

```python
# tests/reporter/test_state.py
"""Tests for Supabase state manager (mocked)."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.reporter.state import ReporterState
from agents.reporter.types import ReportScope, ReportType


@pytest.fixture
def mock_supabase():
    client = MagicMock()
    client.table = MagicMock(return_value=client)
    client.insert = MagicMock(return_value=client)
    client.upsert = MagicMock(return_value=client)
    client.select = MagicMock(return_value=client)
    client.eq = MagicMock(return_value=client)
    client.execute = MagicMock(return_value=MagicMock(data=[]))
    return client


@pytest.fixture
def scope():
    return ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )


def test_create_run(mock_supabase, scope):
    state = ReporterState(client=mock_supabase)
    run_id = state.create_run(scope)
    mock_supabase.table.assert_called_with("report_runs")
    assert mock_supabase.upsert.called


def test_update_run(mock_supabase, scope):
    state = ReporterState(client=mock_supabase)
    state.update_run(scope, status="success", confidence=0.85)
    mock_supabase.table.assert_called_with("report_runs")


def test_was_notified(mock_supabase):
    mock_supabase.execute.return_value = MagicMock(data=[])
    state = ReporterState(client=mock_supabase)
    result = state.was_notified("error:financial_daily:2026-03-28")
    assert result is False


def test_was_notified_true(mock_supabase):
    mock_supabase.execute.return_value = MagicMock(data=[{"id": "123"}])
    state = ReporterState(client=mock_supabase)
    result = state.was_notified("error:financial_daily:2026-03-28")
    assert result is True
```

- [ ] **Step 2: Write implementation**

```python
# agents/reporter/state.py
"""Supabase state management for report runs, notifications, and playbook."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


class ReporterState:
    """Supabase-backed state for Reporter V4.

    Tables: report_runs, notification_log, analytics_rules
    """

    def __init__(self, client: Any):
        self._sb = client

    def create_run(self, scope: ReportScope) -> str:
        """Upsert a report run. Returns scope_hash as run ID."""
        row = {
            "report_date": scope.period_from.isoformat(),
            "report_type": scope.report_type.value,
            "scope_hash": scope.scope_hash,
            "scope_json": scope.to_dict(),
            "status": "pending",
            "attempt": 1,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._sb.table("report_runs").upsert(
            row, on_conflict="report_date,report_type,scope_hash"
        ).execute()
        return scope.scope_hash

    def update_run(
        self,
        scope: ReportScope,
        *,
        status: str,
        notion_url: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
        confidence: Optional[float] = None,
        cost_usd: Optional[float] = None,
        duration_sec: Optional[float] = None,
        issues: Optional[list[str]] = None,
        error: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_tokens_in: Optional[int] = None,
        llm_tokens_out: Optional[int] = None,
    ) -> None:
        row: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if notion_url is not None:
            row["notion_url"] = notion_url
        if telegram_message_id is not None:
            row["telegram_message_id"] = telegram_message_id
        if confidence is not None:
            row["confidence"] = confidence
        if cost_usd is not None:
            row["cost_usd"] = cost_usd
        if duration_sec is not None:
            row["duration_sec"] = duration_sec
        if issues is not None:
            row["issues"] = issues
        if error is not None:
            row["error"] = error
        if llm_model is not None:
            row["llm_model"] = llm_model
        if llm_tokens_in is not None:
            row["llm_tokens_in"] = llm_tokens_in
        if llm_tokens_out is not None:
            row["llm_tokens_out"] = llm_tokens_out

        self._sb.table("report_runs").update(row).eq(
            "report_date", scope.period_from.isoformat()
        ).eq("report_type", scope.report_type.value).eq(
            "scope_hash", scope.scope_hash
        ).execute()

    def increment_attempt(self, scope: ReportScope) -> None:
        """Increment attempt counter for a run."""
        # Read current attempt
        resp = (
            self._sb.table("report_runs")
            .select("attempt")
            .eq("report_date", scope.period_from.isoformat())
            .eq("report_type", scope.report_type.value)
            .eq("scope_hash", scope.scope_hash)
            .execute()
        )
        current = resp.data[0]["attempt"] if resp.data else 0
        self._sb.table("report_runs").update(
            {"attempt": current + 1, "status": "pending",
             "updated_at": datetime.utcnow().isoformat()}
        ).eq("report_date", scope.period_from.isoformat()).eq(
            "report_type", scope.report_type.value
        ).eq("scope_hash", scope.scope_hash).execute()

    def get_successful_today(self, today: date) -> set[str]:
        """Return set of report_type values with status='success' for today."""
        resp = (
            self._sb.table("report_runs")
            .select("report_type")
            .eq("report_date", today.isoformat())
            .eq("status", "success")
            .execute()
        )
        return {row["report_type"] for row in resp.data}

    def get_attempt_count(self, scope: ReportScope) -> int:
        resp = (
            self._sb.table("report_runs")
            .select("attempt")
            .eq("report_date", scope.period_from.isoformat())
            .eq("report_type", scope.report_type.value)
            .eq("scope_hash", scope.scope_hash)
            .execute()
        )
        return resp.data[0]["attempt"] if resp.data else 0

    def get_telegram_message_id(self, scope: ReportScope) -> Optional[int]:
        resp = (
            self._sb.table("report_runs")
            .select("telegram_message_id")
            .eq("report_date", scope.period_from.isoformat())
            .eq("report_type", scope.report_type.value)
            .eq("scope_hash", scope.scope_hash)
            .execute()
        )
        if resp.data and resp.data[0].get("telegram_message_id"):
            return resp.data[0]["telegram_message_id"]
        return None

    # ── Notification dedup ─────────────────────────────────────────────────

    def was_notified(self, key: str) -> bool:
        resp = (
            self._sb.table("notification_log")
            .select("id")
            .eq("notification_key", key)
            .execute()
        )
        return len(resp.data) > 0

    def mark_notified(self, key: str, telegram_message_id: Optional[int] = None) -> None:
        row = {"notification_key": key}
        if telegram_message_id:
            row["telegram_message_id"] = telegram_message_id
        self._sb.table("notification_log").upsert(
            row, on_conflict="notification_key"
        ).execute()

    # ── Playbook rules ─────────────────────────────────────────────────────

    def get_active_rules(self, report_type: Optional[str] = None) -> list[dict]:
        q = (
            self._sb.table("analytics_rules")
            .select("*")
            .eq("status", "active")
        )
        if report_type:
            q = q.contains("report_types", [report_type])
        return q.execute().data

    def save_pending_pattern(self, pattern: dict) -> None:
        self._sb.table("analytics_rules").insert(pattern).execute()

    def update_rule_status(self, rule_id: str, status: str) -> None:
        self._sb.table("analytics_rules").update(
            {"status": status, "reviewed_at": datetime.utcnow().isoformat()}
        ).eq("id", rule_id).execute()

    # ── Status summary ─────────────────────────────────────────────────────

    def get_today_status(self, today: date) -> list[dict]:
        """All runs for today with their statuses."""
        return (
            self._sb.table("report_runs")
            .select("report_type,status,attempt,confidence,notion_url,error,updated_at")
            .eq("report_date", today.isoformat())
            .execute()
            .data
        )
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/reporter/test_state.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add agents/reporter/state.py tests/reporter/test_state.py
git commit -m "feat(reporter): add Supabase state manager for report runs and notifications"
```

---

### Task 5: Gates (copy from V3)

**Files:**
- Create: `agents/reporter/gates.py` (adapted copy of `agents/v3/gates.py`)

- [ ] **Step 1: Copy and adapt gates.py**

Copy `agents/v3/gates.py` to `agents/reporter/gates.py`. Changes:
1. Update import: use `agents.reporter.config` instead of `agents.v3.config`
2. Keep all 6 gate checks identical (they work correctly)
3. Keep GateResult and GateCheckResult dataclasses

```bash
cp agents/v3/gates.py agents/reporter/gates.py
```

Then edit the import at the top:

```python
# Replace:
# from agents.v3.config import DB_HOST, DB_PORT, ...
# With:
from agents.reporter.config import DB_HOST, DB_PORT
```

The core logic remains unchanged — GateChecker with check_all() and check_both().

- [ ] **Step 2: Verify import works**

Run: `python -c "from agents.reporter.gates import GateChecker, GateCheckResult; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add agents/reporter/gates.py
git commit -m "feat(reporter): copy gate checker from V3 (6 data quality gates)"
```

---

## Wave 2: Data Collection

### Task 6: Base Collector

**Files:**
- Create: `agents/reporter/collector/__init__.py`
- Create: `agents/reporter/collector/base.py`
- Test: `tests/reporter/test_collector_financial.py` (placeholder import test)

- [ ] **Step 1: Write base.py**

```python
# agents/reporter/collector/__init__.py
```

```python
# agents/reporter/collector/base.py
"""Base collector and CollectedData model."""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


class TopLevelMetrics(BaseModel):
    revenue_before_spp: float = 0.0
    revenue_after_spp: float = 0.0
    orders_count: int = 0
    orders_rub: float = 0.0
    sales_count: int = 0
    margin: float = 0.0
    margin_pct: float = 0.0
    adv_internal: float = 0.0
    adv_external: float = 0.0
    adv_total: float = 0.0
    drr_pct: float = 0.0
    spp_pct: float = 0.0
    logistics: float = 0.0
    storage: float = 0.0
    cost_of_goods: float = 0.0
    commission: float = 0.0
    buyout_pct: float = 0.0


class MarketplaceMetrics(BaseModel):
    marketplace: str  # "wb" or "ozon"
    metrics: TopLevelMetrics
    prev_metrics: TopLevelMetrics


class ModelMetrics(BaseModel):
    model: str
    rank: int
    metrics: TopLevelMetrics
    prev_metrics: TopLevelMetrics


class TrendData(BaseModel):
    daily_series: list[dict] = Field(default_factory=list)
    weekly_breakdown: list[dict] = Field(default_factory=list)


class ContextData(BaseModel):
    stock_by_model: dict[str, float] = Field(default_factory=dict)
    turnover_by_model: dict[str, dict] = Field(default_factory=dict)
    price_changes: list[dict] = Field(default_factory=list)
    ad_campaigns: list[dict] = Field(default_factory=list)
    ad_breakdown: dict = Field(default_factory=dict)


class CollectedData(BaseModel):
    scope: dict
    collected_at: str
    current: TopLevelMetrics
    previous: TopLevelMetrics
    marketplace_breakdown: list[MarketplaceMetrics] = Field(default_factory=list)
    model_breakdown: list[ModelMetrics] = Field(default_factory=list)
    trends: TrendData = Field(default_factory=TrendData)
    context: ContextData = Field(default_factory=ContextData)
    warnings: list[str] = Field(default_factory=list)


class BaseCollector(ABC):
    """Abstract base for data collectors. Subclasses implement _collect_sync()."""

    @abstractmethod
    def _collect_sync(self, scope: ReportScope) -> CollectedData:
        """Collect data synchronously (uses psycopg2 from shared/data_layer)."""
        ...

    async def collect(self, scope: ReportScope) -> CollectedData:
        """Async wrapper — runs sync collection in thread pool."""
        logger.info("Collecting data for %s", scope.report_type.value)
        data = await asyncio.to_thread(self._collect_sync, scope)
        logger.info(
            "Collected: %d models, %d warnings",
            len(data.model_breakdown),
            len(data.warnings),
        )
        return data
```

- [ ] **Step 2: Commit**

```bash
git add agents/reporter/collector/
git commit -m "feat(reporter): add base collector with CollectedData model"
```

---

### Task 7: Financial Collector

**Files:**
- Create: `agents/reporter/collector/financial.py`
- Test: `tests/reporter/test_collector_financial.py`

- [ ] **Step 1: Write test (mocked data_layer)**

```python
# tests/reporter/test_collector_financial.py
"""Tests for FinancialCollector with mocked data_layer."""
from datetime import date
from unittest.mock import patch, MagicMock

from agents.reporter.collector.financial import FinancialCollector
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )


def _mock_wb_finance():
    """Simulate get_wb_finance return: (abc_rows, orders_rows)."""
    abc_rows = [
        # period, sales_count, revenue_before_spp, spp_amount, revenue_after_spp,
        # adv_internal, adv_vk, adv_bloggers, adv_creators, cost_of_goods,
        # logistics, storage, commission, margin, nds, orders_count, orders_rub
        ("current", 100, 500000, 50000, 450000, 30000, 5000, 3000, 2000,
         150000, 40000, 10000, 25000, 135000, 0, 120, 600000),
        ("previous", 90, 450000, 45000, 405000, 25000, 4000, 2000, 1000,
         135000, 38000, 9000, 22000, 129000, 0, 110, 540000),
    ]
    orders_rows = [
        ("current", 120, 600000),
        ("previous", 110, 540000),
    ]
    return abc_rows, orders_rows


def _mock_wb_by_model():
    return [
        ("current", "wendy", 50, 250000, 15000, 3000, 70000, 75000),
        ("previous", "wendy", 45, 220000, 12000, 2000, 63000, 68000),
        ("current", "vuki", 30, 150000, 10000, 1000, 40000, 50000),
        ("previous", "vuki", 28, 140000, 9000, 800, 38000, 47000),
    ]


@patch("agents.reporter.collector.financial.get_wb_finance")
@patch("agents.reporter.collector.financial.get_ozon_finance")
@patch("agents.reporter.collector.financial.get_wb_by_model")
@patch("agents.reporter.collector.financial.get_ozon_by_model")
@patch("agents.reporter.collector.financial.get_wb_daily_series")
@patch("agents.reporter.collector.financial.get_ozon_daily_series")
@patch("agents.reporter.collector.financial.get_wb_avg_stock")
@patch("agents.reporter.collector.financial.get_ozon_avg_stock")
@patch("agents.reporter.collector.financial.get_wb_turnover_by_model")
@patch("agents.reporter.collector.financial.get_wb_price_changes")
@patch("agents.reporter.collector.financial.get_wb_external_ad_breakdown")
@patch("agents.reporter.collector.financial.validate_wb_data_quality")
def test_financial_collector_daily(
    mock_quality, mock_ad_breakdown, mock_price_changes,
    mock_turnover, mock_ozon_stock, mock_wb_stock,
    mock_ozon_series, mock_wb_series,
    mock_ozon_model, mock_wb_model,
    mock_ozon_finance, mock_wb_finance,
):
    mock_wb_finance.return_value = _mock_wb_finance()
    mock_ozon_finance.return_value = ([], [])
    mock_wb_model.return_value = _mock_wb_by_model()
    mock_ozon_model.return_value = []
    mock_wb_series.return_value = []
    mock_ozon_series.return_value = []
    mock_wb_stock.return_value = {}
    mock_ozon_stock.return_value = {}
    mock_turnover.return_value = {}
    mock_price_changes.return_value = []
    mock_ad_breakdown.return_value = []
    mock_quality.return_value = {"warnings": []}

    collector = FinancialCollector()
    data = collector._collect_sync(_scope())

    assert data.current.revenue_before_spp == 500000
    assert data.previous.revenue_before_spp == 450000
    assert len(data.marketplace_breakdown) >= 1
    assert len(data.model_breakdown) >= 1
    assert data.model_breakdown[0].model == "wendy"
```

- [ ] **Step 2: Write implementation**

```python
# agents/reporter/collector/financial.py
"""Financial data collector — uses shared/data_layer for all SQL queries."""
from __future__ import annotations

import logging
from datetime import datetime

from shared.data_layer.finance import (
    get_wb_finance,
    get_wb_by_model,
    get_ozon_finance,
    get_ozon_by_model,
)
from shared.data_layer.advertising import get_wb_external_ad_breakdown
from shared.data_layer.inventory import (
    get_wb_avg_stock,
    get_ozon_avg_stock,
    get_wb_turnover_by_model,
)
from shared.data_layer.time_series import get_wb_daily_series, get_ozon_daily_series
from shared.data_layer.pricing import get_wb_price_changes
from shared.data_layer.quality import validate_wb_data_quality

from agents.reporter.collector.base import (
    BaseCollector,
    CollectedData,
    ContextData,
    MarketplaceMetrics,
    ModelMetrics,
    TopLevelMetrics,
    TrendData,
)
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


def _safe_div(a: float, b: float) -> float:
    return round(a / b * 100, 2) if b else 0.0


def _parse_abc_row(row: tuple) -> TopLevelMetrics:
    """Parse a row from get_wb_finance / get_ozon_finance abc_date result."""
    # Columns: period, sales_count, revenue_before_spp, spp_amount,
    # revenue_after_spp, adv_internal, adv_vk, adv_bloggers, adv_creators,
    # cost_of_goods, logistics, storage, commission, margin, nds,
    # orders_count, orders_rub
    (_, sales, rev_before, spp_amount, rev_after,
     adv_int, adv_vk, adv_blog, adv_creators,
     cogs, logistics, storage, commission, margin, nds,
     orders_count, orders_rub) = row

    adv_external = float(adv_vk or 0) + float(adv_blog or 0) + float(adv_creators or 0)
    adv_total = float(adv_int or 0) + adv_external
    rev_b = float(rev_before or 0)

    return TopLevelMetrics(
        revenue_before_spp=rev_b,
        revenue_after_spp=float(rev_after or 0),
        orders_count=int(orders_count or 0),
        orders_rub=float(orders_rub or 0),
        sales_count=int(sales or 0),
        margin=float(margin or 0),
        margin_pct=_safe_div(float(margin or 0), rev_b),
        adv_internal=float(adv_int or 0),
        adv_external=adv_external,
        adv_total=adv_total,
        drr_pct=_safe_div(adv_total, rev_b),
        spp_pct=_safe_div(float(spp_amount or 0), rev_b),
        logistics=float(logistics or 0),
        storage=float(storage or 0),
        cost_of_goods=float(cogs or 0),
        commission=float(commission or 0),
    )


def _parse_model_rows(rows: list[tuple]) -> list[ModelMetrics]:
    """Parse by-model rows into ModelMetrics list, sorted by current revenue."""
    models: dict[str, dict] = {}  # {model: {current: ..., previous: ...}}

    for row in rows:
        # period, model, sales_count, revenue_before_spp, adv_internal,
        # adv_external, margin, cost_of_goods
        period, model, sales, rev, adv_int, adv_ext, margin, cogs = row
        bucket = "current" if period == "current" else "previous"

        if model not in models:
            models[model] = {"current": TopLevelMetrics(), "previous": TopLevelMetrics()}

        adv_total = float(adv_int or 0) + float(adv_ext or 0)
        rev_f = float(rev or 0)
        models[model][bucket] = TopLevelMetrics(
            revenue_before_spp=rev_f,
            sales_count=int(sales or 0),
            margin=float(margin or 0),
            margin_pct=_safe_div(float(margin or 0), rev_f),
            adv_internal=float(adv_int or 0),
            adv_external=float(adv_ext or 0),
            adv_total=adv_total,
            drr_pct=_safe_div(adv_total, rev_f),
            cost_of_goods=float(cogs or 0),
        )

    # Sort by current revenue descending
    sorted_models = sorted(
        models.items(), key=lambda x: x[1]["current"].revenue_before_spp, reverse=True
    )
    return [
        ModelMetrics(
            model=name,
            rank=i + 1,
            metrics=data["current"],
            prev_metrics=data["previous"],
        )
        for i, (name, data) in enumerate(sorted_models)
    ]


class FinancialCollector(BaseCollector):
    def _collect_sync(self, scope: ReportScope) -> CollectedData:
        cs = scope.period_from.isoformat()
        ce = scope.period_to.isoformat()
        ps = scope.comparison_from.isoformat()

        warnings: list[str] = []

        # ── Layer 1: Top-level metrics ─────────────────────────────────
        wb_abc, wb_orders = get_wb_finance(cs, ps, ce)
        ozon_abc, ozon_orders = get_ozon_finance(cs, ps, ce)

        current = TopLevelMetrics()
        previous = TopLevelMetrics()
        wb_current = TopLevelMetrics()
        wb_previous = TopLevelMetrics()
        ozon_current = TopLevelMetrics()
        ozon_previous = TopLevelMetrics()

        for row in wb_abc:
            parsed = _parse_abc_row(row)
            if row[0] == "current":
                wb_current = parsed
            else:
                wb_previous = parsed

        for row in ozon_abc:
            parsed = _parse_abc_row(row)
            if row[0] == "current":
                ozon_current = parsed
            else:
                ozon_previous = parsed

        # Merge WB + OZON (weighted averages for percentages)
        for period_label, wb, oz, target in [
            ("current", wb_current, ozon_current, None),
            ("previous", wb_previous, ozon_previous, None),
        ]:
            merged = TopLevelMetrics(
                revenue_before_spp=wb.revenue_before_spp + oz.revenue_before_spp,
                revenue_after_spp=wb.revenue_after_spp + oz.revenue_after_spp,
                orders_count=wb.orders_count + oz.orders_count,
                orders_rub=wb.orders_rub + oz.orders_rub,
                sales_count=wb.sales_count + oz.sales_count,
                margin=wb.margin + oz.margin,
                adv_internal=wb.adv_internal + oz.adv_internal,
                adv_external=wb.adv_external + oz.adv_external,
                adv_total=wb.adv_total + oz.adv_total,
                logistics=wb.logistics + oz.logistics,
                storage=wb.storage + oz.storage,
                cost_of_goods=wb.cost_of_goods + oz.cost_of_goods,
                commission=wb.commission + oz.commission,
            )
            # Weighted averages
            total_rev = merged.revenue_before_spp
            merged.margin_pct = _safe_div(merged.margin, total_rev)
            merged.drr_pct = _safe_div(merged.adv_total, total_rev)
            merged.spp_pct = _safe_div(
                wb.spp_pct * wb.revenue_before_spp + oz.spp_pct * oz.revenue_before_spp,
                total_rev,
            ) if total_rev else 0.0

            if period_label == "current":
                current = merged
            else:
                previous = merged

        # ── Layer 2: Marketplace breakdown ─────────────────────────────
        mp_breakdown = []
        if wb_current.revenue_before_spp > 0 or wb_previous.revenue_before_spp > 0:
            mp_breakdown.append(MarketplaceMetrics(
                marketplace="wb", metrics=wb_current, prev_metrics=wb_previous
            ))
        if ozon_current.revenue_before_spp > 0 or ozon_previous.revenue_before_spp > 0:
            mp_breakdown.append(MarketplaceMetrics(
                marketplace="ozon", metrics=ozon_current, prev_metrics=ozon_previous
            ))

        # ── Layer 3: By model ──────────────────────────────────────────
        wb_models = get_wb_by_model(cs, ps, ce)
        ozon_models = get_ozon_by_model(cs, ps, ce)
        all_model_rows = wb_models + ozon_models
        model_breakdown = _parse_model_rows(all_model_rows)

        # ── Layer 4: Trends ────────────────────────────────────────────
        wb_series = get_wb_daily_series(ce, lookback_days=14)
        ozon_series = get_ozon_daily_series(ce, lookback_days=14)

        # ── Layer 5: Context ───────────────────────────────────────────
        wb_stock = get_wb_avg_stock(cs, ce)
        ozon_stock = get_ozon_avg_stock(cs, ce)
        all_stock = {**wb_stock, **ozon_stock}

        turnover = get_wb_turnover_by_model(cs, ce)
        price_changes = get_wb_price_changes(cs, ce)

        try:
            ad_breakdown = get_wb_external_ad_breakdown(cs, ps, ce)
        except Exception as e:
            logger.warning("Ad breakdown failed: %s", e)
            ad_breakdown = []

        # ── Data quality ───────────────────────────────────────────────
        try:
            quality = validate_wb_data_quality(ce)
            if quality.get("warnings"):
                warnings.extend(quality["warnings"])
        except Exception as e:
            logger.warning("Quality check failed: %s", e)

        return CollectedData(
            scope=scope.to_dict(),
            collected_at=datetime.utcnow().isoformat(),
            current=current,
            previous=previous,
            marketplace_breakdown=mp_breakdown,
            model_breakdown=model_breakdown,
            trends=TrendData(
                daily_series=wb_series + ozon_series,
            ),
            context=ContextData(
                stock_by_model=all_stock,
                turnover_by_model=turnover,
                price_changes=price_changes,
                ad_breakdown={"rows": ad_breakdown},
            ),
            warnings=warnings,
        )
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/reporter/test_collector_financial.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add agents/reporter/collector/financial.py tests/reporter/test_collector_financial.py
git commit -m "feat(reporter): add FinancialCollector with greedy data collection"
```

---

### Task 8: Marketing Collector

**Files:**
- Create: `agents/reporter/collector/marketing.py`
- Test: `tests/reporter/test_collector_marketing.py`

- [ ] **Step 1: Write implementation**

```python
# agents/reporter/collector/marketing.py
"""Marketing data collector — ad campaigns, organic vs paid, DRR breakdown."""
from __future__ import annotations

import logging
from datetime import datetime

from shared.data_layer.advertising import (
    get_wb_external_ad_breakdown,
    get_ozon_external_ad_breakdown,
    get_wb_campaign_stats,
    get_wb_model_ad_roi,
    get_ozon_model_ad_roi,
    get_wb_organic_vs_paid_funnel,
    get_wb_ad_daily_series,
    get_ozon_ad_daily_series,
)
from shared.data_layer.traffic import (
    get_wb_traffic,
    get_wb_traffic_by_model,
    get_ozon_traffic,
)
from shared.data_layer.finance import get_wb_finance, get_ozon_finance

from agents.reporter.collector.base import (
    BaseCollector,
    CollectedData,
    ContextData,
    MarketplaceMetrics,
    ModelMetrics,
    TopLevelMetrics,
    TrendData,
)
from agents.reporter.collector.financial import _parse_abc_row, _safe_div
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


class MarketingCollector(BaseCollector):
    def _collect_sync(self, scope: ReportScope) -> CollectedData:
        cs = scope.period_from.isoformat()
        ce = scope.period_to.isoformat()
        ps = scope.comparison_from.isoformat()

        warnings: list[str] = []

        # ── Base financials (for DRR context) ──────────────────────────
        wb_abc, _ = get_wb_finance(cs, ps, ce)
        ozon_abc, _ = get_ozon_finance(cs, ps, ce)

        current = TopLevelMetrics()
        previous = TopLevelMetrics()
        for row in wb_abc:
            parsed = _parse_abc_row(row)
            if row[0] == "current":
                current = parsed
            else:
                previous = parsed

        # ── Ad breakdown (internal/external/VK/bloggers) ──────────────
        wb_ad_breakdown = get_wb_external_ad_breakdown(cs, ps, ce)
        ozon_ad_breakdown = get_ozon_external_ad_breakdown(cs, ps, ce)

        # ── Campaign stats ─────────────────────────────────────────────
        campaign_stats = get_wb_campaign_stats(cs, ps, ce)

        # ── Model-level ad ROI ─────────────────────────────────────────
        wb_roi = get_wb_model_ad_roi(cs, ps, ce)
        ozon_roi = get_ozon_model_ad_roi(cs, ps, ce)

        model_breakdown = []
        for i, row in enumerate(wb_roi[:10]):
            model_breakdown.append(ModelMetrics(
                model=str(row[1]) if len(row) > 1 else f"model_{i}",
                rank=i + 1,
                metrics=TopLevelMetrics(),
                prev_metrics=TopLevelMetrics(),
            ))

        # ── Organic vs paid ────────────────────────────────────────────
        try:
            organic_funnel, paid_funnel = get_wb_organic_vs_paid_funnel(cs, ps, ce)
        except Exception as e:
            logger.warning("Organic vs paid failed: %s", e)
            organic_funnel, paid_funnel = [], []

        # ── Traffic by model ───────────────────────────────────────────
        traffic_by_model = get_wb_traffic_by_model(cs, ps, ce)

        # ── Ad time series ─────────────────────────────────────────────
        wb_ad_series = get_wb_ad_daily_series(cs, ps, ce)
        ozon_ad_series = get_ozon_ad_daily_series(cs, ps, ce)

        return CollectedData(
            scope=scope.to_dict(),
            collected_at=datetime.utcnow().isoformat(),
            current=current,
            previous=previous,
            model_breakdown=model_breakdown,
            trends=TrendData(daily_series=wb_ad_series + ozon_ad_series),
            context=ContextData(
                ad_breakdown={
                    "wb": wb_ad_breakdown,
                    "ozon": ozon_ad_breakdown,
                },
                ad_campaigns=campaign_stats,
            ),
            warnings=warnings,
        )
```

- [ ] **Step 2: Write test**

```python
# tests/reporter/test_collector_marketing.py
"""Tests for MarketingCollector with mocked data_layer."""
from datetime import date
from unittest.mock import patch

from agents.reporter.collector.marketing import MarketingCollector
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.MARKETING_WEEKLY,
        period_from=date(2026, 3, 23),
        period_to=date(2026, 3, 29),
        comparison_from=date(2026, 3, 16),
        comparison_to=date(2026, 3, 22),
    )


@patch("agents.reporter.collector.marketing.get_wb_finance", return_value=([], []))
@patch("agents.reporter.collector.marketing.get_ozon_finance", return_value=([], []))
@patch("agents.reporter.collector.marketing.get_wb_external_ad_breakdown", return_value=[])
@patch("agents.reporter.collector.marketing.get_ozon_external_ad_breakdown", return_value=[])
@patch("agents.reporter.collector.marketing.get_wb_campaign_stats", return_value=[])
@patch("agents.reporter.collector.marketing.get_wb_model_ad_roi", return_value=[])
@patch("agents.reporter.collector.marketing.get_ozon_model_ad_roi", return_value=[])
@patch("agents.reporter.collector.marketing.get_wb_organic_vs_paid_funnel", return_value=([], []))
@patch("agents.reporter.collector.marketing.get_wb_traffic_by_model", return_value=[])
@patch("agents.reporter.collector.marketing.get_wb_ad_daily_series", return_value=[])
@patch("agents.reporter.collector.marketing.get_ozon_ad_daily_series", return_value=[])
def test_marketing_collector_returns_collected_data(*mocks):
    collector = MarketingCollector()
    data = collector._collect_sync(_scope())
    assert data.scope["report_type"] == "marketing_weekly"
    assert isinstance(data.warnings, list)
```

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/reporter/test_collector_marketing.py -v`

```bash
git add agents/reporter/collector/marketing.py tests/reporter/test_collector_marketing.py
git commit -m "feat(reporter): add MarketingCollector"
```

---

### Task 9: Funnel Collector

**Files:**
- Create: `agents/reporter/collector/funnel.py`
- Test: `tests/reporter/test_collector_funnel.py`

- [ ] **Step 1: Write implementation**

```python
# agents/reporter/collector/funnel.py
"""Funnel data collector — conversion stages, SEO, article-level funnel."""
from __future__ import annotations

import logging
from datetime import datetime

from shared.data_layer.funnel_seo import (
    get_wb_article_funnel,
    get_wb_article_funnel_wow,
    get_wb_seo_keyword_positions,
)
from shared.data_layer.traffic import get_wb_traffic, get_ozon_traffic
from shared.data_layer.finance import get_wb_finance, get_ozon_finance

from agents.reporter.collector.base import (
    BaseCollector,
    CollectedData,
    ContextData,
    TopLevelMetrics,
    TrendData,
)
from agents.reporter.collector.financial import _parse_abc_row
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


class FunnelCollector(BaseCollector):
    def _collect_sync(self, scope: ReportScope) -> CollectedData:
        cs = scope.period_from.isoformat()
        ce = scope.period_to.isoformat()
        ps = scope.comparison_from.isoformat()

        warnings: list[str] = []

        # Base financials for context
        wb_abc, _ = get_wb_finance(cs, ps, ce)
        current = TopLevelMetrics()
        previous = TopLevelMetrics()
        for row in wb_abc:
            parsed = _parse_abc_row(row)
            if row[0] == "current":
                current = parsed
            else:
                previous = parsed

        # Article-level funnel (TOP-10)
        article_funnel = get_wb_article_funnel(cs, ce, top_n=10)

        # Week-over-week funnel comparison
        try:
            funnel_wow = get_wb_article_funnel_wow(cs, ps, ce)
        except Exception as e:
            logger.warning("Funnel WoW failed: %s", e)
            funnel_wow = []

        # Traffic (organic + ad)
        try:
            wb_organic, wb_ad = get_wb_traffic(cs, ps, ce)
        except Exception as e:
            logger.warning("WB traffic failed: %s", e)
            wb_organic, wb_ad = [], []

        try:
            ozon_traffic = get_ozon_traffic(cs, ps, ce)
        except Exception as e:
            logger.warning("OZON traffic failed: %s", e)
            ozon_traffic = []

        # SEO keywords
        try:
            seo_keywords = get_wb_seo_keyword_positions(limit=50)
        except Exception as e:
            logger.warning("SEO keywords failed: %s", e)
            seo_keywords = []

        return CollectedData(
            scope=scope.to_dict(),
            collected_at=datetime.utcnow().isoformat(),
            current=current,
            previous=previous,
            trends=TrendData(daily_series=[]),
            context=ContextData(
                ad_campaigns=[],
                ad_breakdown={
                    "article_funnel": article_funnel,
                    "funnel_wow": funnel_wow,
                    "wb_organic": wb_organic,
                    "wb_ad": wb_ad,
                    "ozon_traffic": ozon_traffic,
                    "seo_keywords": seo_keywords,
                },
            ),
            warnings=warnings,
        )
```

- [ ] **Step 2: Write test and commit**

```python
# tests/reporter/test_collector_funnel.py
"""Tests for FunnelCollector with mocked data_layer."""
from datetime import date
from unittest.mock import patch

from agents.reporter.collector.funnel import FunnelCollector
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.FUNNEL_WEEKLY,
        period_from=date(2026, 3, 23),
        period_to=date(2026, 3, 29),
        comparison_from=date(2026, 3, 16),
        comparison_to=date(2026, 3, 22),
    )


@patch("agents.reporter.collector.funnel.get_wb_finance", return_value=([], []))
@patch("agents.reporter.collector.funnel.get_ozon_finance", return_value=([], []))
@patch("agents.reporter.collector.funnel.get_wb_article_funnel", return_value=[])
@patch("agents.reporter.collector.funnel.get_wb_article_funnel_wow", return_value=[])
@patch("agents.reporter.collector.funnel.get_wb_traffic", return_value=([], []))
@patch("agents.reporter.collector.funnel.get_ozon_traffic", return_value=[])
@patch("agents.reporter.collector.funnel.get_wb_seo_keyword_positions", return_value=[])
def test_funnel_collector_returns_collected_data(*mocks):
    collector = FunnelCollector()
    data = collector._collect_sync(_scope())
    assert data.scope["report_type"] == "funnel_weekly"
```

Run: `python -m pytest tests/reporter/test_collector_funnel.py -v`

```bash
git add agents/reporter/collector/funnel.py tests/reporter/test_collector_funnel.py
git commit -m "feat(reporter): add FunnelCollector"
```

---

## Wave 3: LLM Analyst & Playbook

### Task 10: LLM Analyst

**Files:**
- Create: `agents/reporter/analyst/analyst.py`
- Test: `tests/reporter/test_analyst.py`

- [ ] **Step 1: Write test**

```python
# tests/reporter/test_analyst.py
"""Tests for LLM analyst with mocked OpenRouter."""
import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from agents.reporter.analyst.analyst import analyze
from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.collector.base import CollectedData, TopLevelMetrics
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )


def _collected_data():
    return CollectedData(
        scope=_scope().to_dict(),
        collected_at="2026-03-28T10:00:00",
        current=TopLevelMetrics(revenue_before_spp=500000, margin=100000),
        previous=TopLevelMetrics(revenue_before_spp=450000, margin=90000),
    )


def _mock_insights_json():
    return json.dumps({
        "executive_summary": "Выручка выросла на 11%",
        "sections": [{
            "section_id": 0,
            "title": "Паспорт",
            "summary": "Отчёт за 27.03.2026",
        }],
        "discovered_patterns": [],
        "overall_confidence": 0.85,
        "analysis_notes": [],
    })


@pytest.mark.asyncio
@patch("agents.reporter.analyst.analyst._call_llm")
async def test_analyze_returns_report_insights(mock_llm):
    mock_llm.return_value = {
        "content": _mock_insights_json(),
        "usage": {"input_tokens": 1000, "output_tokens": 500},
        "model": "google/gemini-2.5-flash",
    }
    insights, meta = await analyze(_collected_data(), _scope(), [])
    assert isinstance(insights, ReportInsights)
    assert insights.overall_confidence == 0.85
    assert meta["model"] == "google/gemini-2.5-flash"


@pytest.mark.asyncio
@patch("agents.reporter.analyst.analyst._call_llm")
async def test_analyze_fallback_on_failure(mock_llm):
    mock_llm.side_effect = [
        Exception("Primary failed"),
        {
            "content": _mock_insights_json(),
            "usage": {"input_tokens": 1000, "output_tokens": 500},
            "model": "openrouter/free",
        },
    ]
    insights, meta = await analyze(_collected_data(), _scope(), [])
    assert isinstance(insights, ReportInsights)
    assert mock_llm.call_count == 2
```

- [ ] **Step 2: Write implementation**

```python
# agents/reporter/analyst/analyst.py
"""Single-LLM analyst — the only point where LLM is called in the pipeline."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from agents.reporter.analyst.circuit_breaker import CircuitBreaker
from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.collector.base import CollectedData
from agents.reporter.config import (
    LLM_MAX_TOKENS,
    LLM_TIMEOUT,
    MODEL_FREE,
    MODEL_FALLBACK,
    MODEL_PRIMARY,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    PROMPTS_DIR,
    CB_FAILURE_THRESHOLD,
    CB_COOLDOWN_SEC,
)
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)

_circuit_breaker = CircuitBreaker(
    failure_threshold=CB_FAILURE_THRESHOLD,
    cooldown_sec=CB_COOLDOWN_SEC,
)


async def _call_llm(
    messages: list[dict],
    model: str,
    max_tokens: int = LLM_MAX_TOKENS,
) -> dict[str, Any]:
    """Call OpenRouter via openai SDK. Returns {content, usage, model}."""
    import openai

    client = openai.AsyncOpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
    )
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.3,
        response_format={"type": "json_object"},
        timeout=LLM_TIMEOUT,
    )
    choice = response.choices[0]
    return {
        "content": choice.message.content or "",
        "usage": {
            "input_tokens": response.usage.prompt_tokens if response.usage else 0,
            "output_tokens": response.usage.completion_tokens if response.usage else 0,
        },
        "model": model,
    }


def _build_prompt(
    data: CollectedData,
    scope: ReportScope,
    playbook_rules: list[dict],
    retry_hint: list[str] | None = None,
) -> str:
    """Build the full prompt from template + data + rules."""
    # Load report-type-specific prompt
    prompt_file = PROMPTS_DIR / f"{scope.report_type.value}.md"
    if prompt_file.exists():
        template = prompt_file.read_text(encoding="utf-8")
    else:
        template = "Проанализируй данные и верни ReportInsights JSON."

    # Construct playbook section
    rules_text = ""
    if playbook_rules:
        rules_lines = [f"- {r.get('rule_text', '')}" for r in playbook_rules]
        rules_text = "\n## Правила анализа (Playbook)\n" + "\n".join(rules_lines)

    # Retry hint
    retry_text = ""
    if retry_hint:
        retry_text = (
            "\n## Замечания к предыдущей попытке\n"
            + "\n".join(f"- {h}" for h in retry_hint)
            + "\nИсправь указанные проблемы."
        )

    # JSON schema for structured output
    schema = json.dumps(ReportInsights.model_json_schema(), ensure_ascii=False, indent=2)

    prompt = f"""{template}

## Период
{scope.period_str}
Сравнение: {scope.comparison_from.isoformat()} — {scope.comparison_to.isoformat()}
Маркетплейс: {scope.marketplace}
{f'Модель: {scope.model}' if scope.model else ''}
{f'Артикул: {scope.article}' if scope.article else ''}

{rules_text}
{retry_text}

## Данные
```json
{data.model_dump_json(indent=2)}
```

## Формат ответа
Верни JSON, соответствующий этой схеме:
```json
{schema}
```

ВАЖНО:
- Все тексты на русском языке
- executive_summary: 3-5 предложений, ключевые выводы
- Заполни ВСЕ секции от 0 до 12 (для финансовых отчётов)
- Каждый root_cause должен содержать конкретные цифры в evidence
- discovered_patterns: только если нашёл неочевидную закономерность
"""
    return prompt


async def analyze(
    data: CollectedData,
    scope: ReportScope,
    playbook_rules: list[dict],
    retry_hint: list[str] | None = None,
) -> tuple[ReportInsights, dict]:
    """Run single LLM analysis. Returns (insights, meta).

    Meta: {model, input_tokens, output_tokens, cost_usd}
    Fallback chain: PRIMARY → retry → FALLBACK → FREE
    """
    prompt = _build_prompt(data, scope, playbook_rules, retry_hint)
    messages = [{"role": "user", "content": prompt}]

    models_to_try = [MODEL_PRIMARY, MODEL_PRIMARY, MODEL_FALLBACK, MODEL_FREE]
    last_error = None

    for model in models_to_try:
        if not _circuit_breaker.can_execute:
            logger.warning("Circuit breaker OPEN — skipping LLM call")
            raise RuntimeError("Circuit breaker is open — LLM calls suspended")

        try:
            result = await _call_llm(messages, model=model)
            content = result["content"]

            # Strip code fences if present
            if content.strip().startswith("```"):
                lines = content.strip().split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            insights = ReportInsights.model_validate_json(content)
            _circuit_breaker.record_success()

            meta = {
                "model": model,
                "input_tokens": result["usage"]["input_tokens"],
                "output_tokens": result["usage"]["output_tokens"],
            }
            logger.info(
                "Analysis complete: model=%s, confidence=%.2f, tokens_in=%d, tokens_out=%d",
                model, insights.overall_confidence,
                meta["input_tokens"], meta["output_tokens"],
            )
            return insights, meta

        except Exception as e:
            _circuit_breaker.record_failure()
            last_error = e
            logger.warning("LLM call failed (model=%s): %s", model, e)
            continue

    raise RuntimeError(f"All LLM models failed. Last error: {last_error}")
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/reporter/test_analyst.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add agents/reporter/analyst/analyst.py tests/reporter/test_analyst.py
git commit -m "feat(reporter): add LLM analyst with fallback chain and circuit breaker"
```

---

### Task 11: Prompt Files

**Files:**
- Create: `agents/reporter/analyst/prompts/financial_daily.md`
- Create: `agents/reporter/analyst/prompts/financial_weekly.md`
- Create: `agents/reporter/analyst/prompts/financial_monthly.md`
- Create: `agents/reporter/analyst/prompts/marketing_weekly.md`
- Create: `agents/reporter/analyst/prompts/marketing_monthly.md`
- Create: `agents/reporter/analyst/prompts/funnel_weekly.md`
- Create: `agents/reporter/analyst/prompts/funnel_monthly.md`

- [ ] **Step 1: Write financial_daily.md prompt**

```markdown
# Ты — финансовый аналитик бренда Wookiee

Wookiee — fashion-бренд, продающий через WB и OZON (кабинеты ИП и ООО).

## Задача
Проанализируй данные за один день и сформируй аналитические выводы для 13 секций отчёта.

## Секции отчёта

0. **Паспорт отчёта** — период, дата генерации, scope
1. **Executive Summary** — 3-5 ключевых выводов дня
2. **Доходы и выручка** — revenue breakdown по маркетплейсам, динамика
3. **Маржинальный каскад** — waterfall: выручка → себестоимость → логистика → реклама → маржа
4. **Рекламная эффективность** — ДРР (с разбивкой внутренняя/внешняя), ROMI, CTR, CPC
5. **Декомпозиция по моделям** — TOP моделей по выручке, худшие по марже
6. **Ценовая динамика** — изменения цен, СПП, скидки
7. **Складские остатки** — дни запаса, оборачиваемость
8. **Воронка продаж** — выкуп % (ЛАГОВЫЙ показатель, 3-21 день), конверсии
9. **Аномалии и алерты** — отклонения от нормы (>20%)
10. **Тренды** — 7d rolling, day-over-day
11. **Рекомендации** — action items с оценкой эффекта в рублях
12. **Техническая информация** — заполняется автоматически

## Правила анализа

- ДРР ВСЕГДА с разбивкой: внутренняя (МП) и внешняя (блогеры, ВК)
- Выкуп % — ЛАГОВЫЙ (3-21 день), только информационный, пометь "лаг 3-21 дн."
- Процентные метрики — ТОЛЬКО средневзвешенные
- Рекомендации содержат "что если" сценарии с расчётом эффекта в рублях
- Если реклама выросла — проверь выросли ли заказы (связка реклама→заказы)
```

- [ ] **Step 2: Write remaining prompt files**

Create similar prompts for each type, adjusting sections and focus:
- `financial_weekly.md` — same structure, weekly aggregation, WoW comparison
- `financial_monthly.md` — monthly aggregation, MoM comparison, quarterly trends
- `marketing_weekly.md` — focus on campaigns, DRR, organic vs paid, CTR/CPC
- `marketing_monthly.md` — campaign performance trends, budget efficiency
- `funnel_weekly.md` — conversion stages, SEO keywords, article-level funnel
- `funnel_monthly.md` — funnel trends, content performance

Each prompt follows the same pattern: role → task → sections → rules.

- [ ] **Step 3: Commit**

```bash
git add agents/reporter/analyst/prompts/
git commit -m "feat(reporter): add 7 LLM prompt files for each report type"
```

---

### Task 12: Playbook Loader & Updater

**Files:**
- Create: `agents/reporter/playbook/__init__.py`
- Create: `agents/reporter/playbook/loader.py`
- Create: `agents/reporter/playbook/updater.py`
- Create: `agents/reporter/playbook/base_rules.md`
- Test: `tests/reporter/test_playbook.py`

- [ ] **Step 1: Write loader and updater**

```python
# agents/reporter/playbook/__init__.py
```

```python
# agents/reporter/playbook/loader.py
"""Load playbook rules from Supabase, with fallback to base_rules.md."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_BASE_RULES_PATH = Path(__file__).parent / "base_rules.md"


def load_rules_from_state(state, report_type: Optional[str] = None) -> list[dict]:
    """Load active rules from Supabase. Fallback to base_rules.md on failure."""
    try:
        rules = state.get_active_rules(report_type)
        if rules:
            logger.info("Loaded %d playbook rules from Supabase", len(rules))
            return rules
    except Exception as e:
        logger.warning("Failed to load rules from Supabase: %s", e)

    # Fallback: parse base_rules.md
    return _parse_base_rules()


def _parse_base_rules() -> list[dict]:
    """Parse base_rules.md into rule dicts."""
    if not _BASE_RULES_PATH.exists():
        return []

    text = _BASE_RULES_PATH.read_text(encoding="utf-8")
    rules = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("- "):
            rules.append({
                "rule_text": line[2:],
                "category": "general",
                "source": "manual",
                "status": "active",
            })
    logger.info("Loaded %d fallback rules from base_rules.md", len(rules))
    return rules
```

```python
# agents/reporter/playbook/updater.py
"""Save LLM-discovered patterns to Supabase as pending_review."""
from __future__ import annotations

import logging
from typing import Any

from agents.reporter.analyst.schemas import DiscoveredPattern
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


def save_discovered_patterns(
    state: Any,
    patterns: list[DiscoveredPattern],
    scope: ReportScope,
) -> int:
    """Save discovered patterns to Supabase. Returns count saved."""
    saved = 0
    for p in patterns:
        if p.confidence < 0.6:
            continue  # Skip low-confidence patterns

        row = {
            "rule_text": p.pattern,
            "category": scope.report_type.collector_kind,
            "source": "llm_discovered",
            "status": "pending_review",
            "confidence": p.confidence,
            "evidence": p.evidence,
            "report_types": [scope.report_type.value],
        }
        try:
            state.save_pending_pattern(row)
            saved += 1
        except Exception as e:
            logger.warning("Failed to save pattern: %s", e)

    if saved:
        logger.info("Saved %d discovered patterns for review", saved)
    return saved
```

- [ ] **Step 2: Write base_rules.md**

Extract key rules from `agents/oleg/playbook.md`:

```markdown
# Base Playbook Rules (migrated from oleg/playbook.md)

- Если маржа % упала > 5 п.п. — проверить: цена, СПП, ДРР, логистика, себестоимость
- ДРР > 20% — проверить CTR и CPC, возможно неэффективная реклама
- Если реклама выросла, а заказы нет — реклама неэффективна, рекомендовать снижение ставок
- Если реклама выросла И заказы выросли — реклама работает, не снижать
- Логистика > 15% от выручки — "тихий убийца маржи", алерт
- Выкуп % < 20% (WB) или < 15% (OZON) — красная зона, расследовать причины
- ROMI < 100% — артикул убыточен по рекламе
- profit_per_sale < 0 — критический алерт, артикул генерирует убыток
- При росте СПП для A-группы: поднять базовую цену (захватить маржу)
- При росте СПП для растущих моделей: оставить цену (захватить рынок)
- Макс 1-2 изменения цены в неделю на SKU
- Себестоимость ~350 руб, резкое изменение = аномалия
```

- [ ] **Step 3: Write test**

```python
# tests/reporter/test_playbook.py
"""Tests for playbook loader and updater."""
from unittest.mock import MagicMock

from agents.reporter.analyst.schemas import DiscoveredPattern
from agents.reporter.playbook.loader import _parse_base_rules, load_rules_from_state
from agents.reporter.playbook.updater import save_discovered_patterns
from agents.reporter.types import ReportScope, ReportType
from datetime import date


def test_parse_base_rules():
    rules = _parse_base_rules()
    assert len(rules) > 0
    assert all(r["source"] == "manual" for r in rules)
    assert all(r["status"] == "active" for r in rules)


def test_load_rules_fallback():
    mock_state = MagicMock()
    mock_state.get_active_rules.side_effect = Exception("DB down")
    rules = load_rules_from_state(mock_state)
    assert len(rules) > 0  # Falls back to base_rules.md


def test_save_discovered_patterns():
    mock_state = MagicMock()
    patterns = [
        DiscoveredPattern(
            pattern="Test pattern",
            evidence="Test evidence",
            suggested_action="Test action",
            confidence=0.8,
        ),
        DiscoveredPattern(
            pattern="Low confidence",
            evidence="Weak",
            suggested_action="Skip",
            confidence=0.3,  # Below 0.6 threshold
        ),
    ]
    scope = ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )
    count = save_discovered_patterns(mock_state, patterns, scope)
    assert count == 1  # Only the high-confidence one
    assert mock_state.save_pending_pattern.call_count == 1
```

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/reporter/test_playbook.py -v`

```bash
git add agents/reporter/playbook/ tests/reporter/test_playbook.py
git commit -m "feat(reporter): add playbook loader, updater, and base rules"
```

---

## Wave 4: Formatting & Validation

### Task 13: Jinja2 Formatter (Notion)

**Files:**
- Create: `agents/reporter/formatter/__init__.py`
- Create: `agents/reporter/formatter/notion.py`
- Create: `agents/reporter/formatter/templates/financial_daily.md.j2`
- Test: `tests/reporter/test_formatter_notion.py`

- [ ] **Step 1: Write Notion formatter**

```python
# agents/reporter/formatter/__init__.py
```

```python
# agents/reporter/formatter/notion.py
"""Render ReportInsights + CollectedData → Notion markdown via Jinja2."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.collector.base import CollectedData
from agents.reporter.config import TEMPLATES_DIR
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _safe_div(a: float, b: float) -> float:
    return round(a / b * 100, 2) if b else 0.0


def _format_num(num: float, decimals: int = 0) -> str:
    """Format number with space thousands (Russian style)."""
    if decimals == 0:
        formatted = f"{int(round(num)):,}".replace(",", " ")
    else:
        formatted = f"{num:,.{decimals}f}".replace(",", " ")
    return formatted


def _arrow(current: float, previous: float) -> str:
    if previous == 0:
        return "→"
    change = (current - previous) / abs(previous) * 100
    if change > 1:
        return "▲"
    elif change < -1:
        return "▼"
    return "→"


def _change_pct(current: float, previous: float) -> str:
    if previous == 0:
        return "n/a"
    change = (current - previous) / abs(previous) * 100
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.1f}%"


def render_notion(
    insights: ReportInsights,
    data: CollectedData,
    scope: ReportScope,
) -> str:
    """Render full Notion markdown report."""
    template_name = f"{scope.report_type.value}.md.j2"
    try:
        template = _env.get_template(template_name)
    except Exception:
        logger.warning("Template %s not found, using fallback", template_name)
        template = _env.get_template("financial_daily.md.j2")

    return template.render(
        insights=insights,
        data=data,
        scope=scope,
        fmt=_format_num,
        arrow=_arrow,
        change_pct=_change_pct,
        safe_div=_safe_div,
    )
```

- [ ] **Step 2: Write financial_daily template**

```jinja2
{# agents/reporter/formatter/templates/financial_daily.md.j2 #}
{# Notion markdown report — based on March 20 gold standard #}

## ▶ 0. Паспорт отчёта

| Параметр | Значение |
|----------|----------|
| Период | {{ scope.period_str }} |
| Сравнение | {{ scope.comparison_from.isoformat() }} — {{ scope.comparison_to.isoformat() }} |
| Маркетплейс | {{ scope.marketplace }} |
| Тип | {{ scope.report_type.human_name }} |
| Confidence | {{ "%.0f"|format(insights.overall_confidence * 100) }}% |

## ▶ 1. Executive Summary

{{ insights.executive_summary }}

## ▶ 2. Доходы и выручка

| Метрика | Текущий | Предыдущий | Δ |
|---------|---------|------------|---|
| Выручка (до СПП) | {{ fmt(data.current.revenue_before_spp) }} ₽ | {{ fmt(data.previous.revenue_before_spp) }} ₽ | {{ arrow(data.current.revenue_before_spp, data.previous.revenue_before_spp) }} {{ change_pct(data.current.revenue_before_spp, data.previous.revenue_before_spp) }} |
| Заказы (шт) | {{ fmt(data.current.orders_count) }} | {{ fmt(data.previous.orders_count) }} | {{ arrow(data.current.orders_count, data.previous.orders_count) }} {{ change_pct(data.current.orders_count, data.previous.orders_count) }} |
| Заказы (руб) | {{ fmt(data.current.orders_rub) }} ₽ | {{ fmt(data.previous.orders_rub) }} ₽ | {{ arrow(data.current.orders_rub, data.previous.orders_rub) }} {{ change_pct(data.current.orders_rub, data.previous.orders_rub) }} |
| Продажи (шт) | {{ fmt(data.current.sales_count) }} | {{ fmt(data.previous.sales_count) }} | {{ arrow(data.current.sales_count, data.previous.sales_count) }} {{ change_pct(data.current.sales_count, data.previous.sales_count) }} |

{% for mp in data.marketplace_breakdown %}
**{{ mp.marketplace | upper }}:**
Выручка: {{ fmt(mp.metrics.revenue_before_spp) }} ₽ ({{ arrow(mp.metrics.revenue_before_spp, mp.prev_metrics.revenue_before_spp) }} {{ change_pct(mp.metrics.revenue_before_spp, mp.prev_metrics.revenue_before_spp) }})

{% endfor %}
{% for s in insights.sections if s.section_id == 2 %}
{{ s.summary }}
{% endfor %}

## ▶ 3. Маржинальный каскад

| Статья | Сумма | % от выручки | Δ |
|--------|-------|--------------|---|
| Выручка до СПП | {{ fmt(data.current.revenue_before_spp) }} ₽ | 100% | {{ change_pct(data.current.revenue_before_spp, data.previous.revenue_before_spp) }} |
| СПП | -{{ fmt(data.current.revenue_before_spp - data.current.revenue_after_spp) }} ₽ | {{ "%.1f"|format(data.current.spp_pct) }}% | |
| Себестоимость | -{{ fmt(data.current.cost_of_goods) }} ₽ | {{ "%.1f"|format(safe_div(data.current.cost_of_goods, data.current.revenue_before_spp)) }}% | {{ change_pct(data.current.cost_of_goods, data.previous.cost_of_goods) }} |
| Логистика | -{{ fmt(data.current.logistics) }} ₽ | {{ "%.1f"|format(safe_div(data.current.logistics, data.current.revenue_before_spp)) }}% | {{ change_pct(data.current.logistics, data.previous.logistics) }} |
| Хранение | -{{ fmt(data.current.storage) }} ₽ | {{ "%.1f"|format(safe_div(data.current.storage, data.current.revenue_before_spp)) }}% | |
| Реклама (внутр.) | -{{ fmt(data.current.adv_internal) }} ₽ | {{ "%.1f"|format(safe_div(data.current.adv_internal, data.current.revenue_before_spp)) }}% | |
| Реклама (внешн.) | -{{ fmt(data.current.adv_external) }} ₽ | {{ "%.1f"|format(safe_div(data.current.adv_external, data.current.revenue_before_spp)) }}% | |
| Комиссия | -{{ fmt(data.current.commission) }} ₽ | {{ "%.1f"|format(safe_div(data.current.commission, data.current.revenue_before_spp)) }}% | |
| **Маржа** | **{{ fmt(data.current.margin) }} ₽** | **{{ "%.1f"|format(data.current.margin_pct) }}%** | **{{ change_pct(data.current.margin, data.previous.margin) }}** |

{% for s in insights.sections if s.section_id == 3 %}
{{ s.summary }}
{% for rc in s.root_causes %}
> **{{ rc.description }}** (confidence: {{ "%.0f"|format(rc.confidence * 100) }}%)
> Доказательства: {{ rc.evidence | join(", ") }}
> Рекомендация: {{ rc.recommendation }}
{% endfor %}
{% endfor %}

## ▶ 4. Рекламная эффективность

| Метрика | Текущий | Предыдущий | Δ |
|---------|---------|------------|---|
| ДРР общий | {{ "%.1f"|format(data.current.drr_pct) }}% | {{ "%.1f"|format(data.previous.drr_pct) }}% | {{ arrow(data.current.drr_pct, data.previous.drr_pct) }} |
| Реклама (внутр.) | {{ fmt(data.current.adv_internal) }} ₽ | {{ fmt(data.previous.adv_internal) }} ₽ | {{ change_pct(data.current.adv_internal, data.previous.adv_internal) }} |
| Реклама (внешн.) | {{ fmt(data.current.adv_external) }} ₽ | {{ fmt(data.previous.adv_external) }} ₽ | {{ change_pct(data.current.adv_external, data.previous.adv_external) }} |

{% for s in insights.sections if s.section_id == 4 %}
{{ s.summary }}
{% endfor %}

## ▶ 5. Декомпозиция по моделям

| # | Модель | Выручка | Маржа | Маржа % | ДРР % | Δ выр. |
|---|--------|---------|-------|---------|-------|--------|
{% for m in data.model_breakdown[:10] %}
| {{ m.rank }} | {{ m.model }} | {{ fmt(m.metrics.revenue_before_spp) }} ₽ | {{ fmt(m.metrics.margin) }} ₽ | {{ "%.1f"|format(m.metrics.margin_pct) }}% | {{ "%.1f"|format(m.metrics.drr_pct) }}% | {{ change_pct(m.metrics.revenue_before_spp, m.prev_metrics.revenue_before_spp) }} |
{% endfor %}

{% for s in insights.sections if s.section_id == 5 %}
{{ s.summary }}
{% endfor %}

## ▶ 6. Ценовая динамика

{% for s in insights.sections if s.section_id == 6 %}
{{ s.summary }}
{% for a in s.anomalies %}
- ⚠️ {{ a }}
{% endfor %}
{% endfor %}

## ▶ 7. Складские остатки и оборачиваемость

{% for s in insights.sections if s.section_id == 7 %}
{{ s.summary }}
{% endfor %}

## ▶ 8. Воронка продаж

| Метрика | Значение |
|---------|----------|
| Выкуп % | {{ "%.1f"|format(data.current.buyout_pct) }}% *(лаг 3-21 дн.)* |

{% for s in insights.sections if s.section_id == 8 %}
{{ s.summary }}
{% endfor %}

## ▶ 9. Аномалии и алерты

{% for s in insights.sections if s.section_id == 9 %}
{% for a in s.anomalies %}
- 🔴 {{ a }}
{% endfor %}
{{ s.summary }}
{% endfor %}

## ▶ 10. Тренды

{% for s in insights.sections if s.section_id == 10 %}
{{ s.summary }}
{% endfor %}

## ▶ 11. Рекомендации

{% for s in insights.sections if s.section_id == 11 %}
{% for rc in s.root_causes %}
{{ loop.index }}. **{{ rc.recommendation }}**
   - {{ rc.description }}
   - Confidence: {{ "%.0f"|format(rc.confidence * 100) }}%
{% endfor %}
{% endfor %}

## ▶ 12. Техническая информация

| Параметр | Значение |
|----------|----------|
| Система | Reporter V4 |
| Confidence | {{ "%.0f"|format(insights.overall_confidence * 100) }}% |
| Предупреждения | {{ data.warnings | length }} |
{% for w in data.warnings %}
| ⚠️ | {{ w }} |
{% endfor %}
```

- [ ] **Step 3: Write test**

```python
# tests/reporter/test_formatter_notion.py
"""Tests for Notion markdown formatter."""
from datetime import date

from agents.reporter.analyst.schemas import ReportInsights, SectionInsight
from agents.reporter.collector.base import CollectedData, TopLevelMetrics, ModelMetrics
from agents.reporter.formatter.notion import render_notion
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )


def _data():
    return CollectedData(
        scope=_scope().to_dict(),
        collected_at="2026-03-28T10:00:00",
        current=TopLevelMetrics(
            revenue_before_spp=500000, margin=100000, margin_pct=20.0,
            orders_count=120, drr_pct=8.0,
        ),
        previous=TopLevelMetrics(
            revenue_before_spp=450000, margin=90000, margin_pct=20.0,
            orders_count=110, drr_pct=7.5,
        ),
        model_breakdown=[
            ModelMetrics(model="wendy", rank=1,
                        metrics=TopLevelMetrics(revenue_before_spp=250000, margin=50000, margin_pct=20.0),
                        prev_metrics=TopLevelMetrics(revenue_before_spp=220000, margin=44000, margin_pct=20.0)),
        ],
    )


def _insights():
    return ReportInsights(
        executive_summary="Выручка выросла на 11%",
        sections=[
            SectionInsight(section_id=i, title=f"Section {i}", summary=f"Summary {i}")
            for i in range(13)
        ],
        overall_confidence=0.85,
    )


def test_render_notion_contains_toggle_sections():
    md = render_notion(_insights(), _data(), _scope())
    assert "## ▶ 0. Паспорт отчёта" in md
    assert "## ▶ 1. Executive Summary" in md
    assert "## ▶ 12. Техническая информация" in md


def test_render_notion_contains_metrics():
    md = render_notion(_insights(), _data(), _scope())
    assert "500 000" in md or "500000" in md
    assert "wendy" in md


def test_render_notion_contains_executive_summary():
    md = render_notion(_insights(), _data(), _scope())
    assert "Выручка выросла на 11%" in md
```

- [ ] **Step 4: Create remaining templates (weekly, monthly, marketing, funnel)**

Create template files following the same pattern. Weekly/monthly templates have the same 13-section structure but with period-appropriate headers. Marketing and funnel templates focus on their respective sections.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/reporter/test_formatter_notion.py -v`

```bash
git add agents/reporter/formatter/ tests/reporter/test_formatter_notion.py
git commit -m "feat(reporter): add Jinja2 Notion formatter with 7 templates"
```

---

### Task 14: Telegram Formatter

**Files:**
- Create: `agents/reporter/formatter/telegram.py`
- Test: `tests/reporter/test_formatter_telegram.py`

- [ ] **Step 1: Write implementation**

```python
# agents/reporter/formatter/telegram.py
"""Render ReportInsights → Telegram HTML summary."""
from __future__ import annotations

from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.collector.base import CollectedData
from agents.reporter.types import ReportScope

MAX_TELEGRAM_MSG = 4000


def _fmt(num: float) -> str:
    return f"{int(round(num)):,}".replace(",", " ")


def _arrow(current: float, previous: float) -> str:
    if previous == 0:
        return "→"
    change = (current - previous) / abs(previous) * 100
    if change > 1:
        return "▲"
    elif change < -1:
        return "▼"
    return "→"


def _change(current: float, previous: float) -> str:
    if previous == 0:
        return ""
    change = (current - previous) / abs(previous) * 100
    sign = "+" if change > 0 else ""
    return f"({sign}{change:.1f}%)"


def _confidence_emoji(c: float) -> str:
    if c >= 0.8:
        return "🟢"
    elif c >= 0.5:
        return "🟡"
    return "🔴"


def render_telegram(
    insights: ReportInsights,
    data: CollectedData,
    scope: ReportScope,
    notion_url: str | None = None,
    meta: dict | None = None,
) -> str:
    """Render compact Telegram HTML message."""
    type_labels = {
        "financial_daily": "📊 Дневной фин. отчёт",
        "financial_weekly": "📈 Недельный фин. отчёт",
        "financial_monthly": "📅 Месячный фин. отчёт",
        "marketing_weekly": "📢 Маркетинг (неделя)",
        "marketing_monthly": "📢 Маркетинг (месяц)",
        "funnel_weekly": "🔄 Воронка (неделя)",
        "funnel_monthly": "🔄 Воронка (месяц)",
    }
    label = type_labels.get(scope.report_type.value, "📊 Отчёт")

    lines = [
        f"<b>{label}</b>",
        f"<i>{scope.period_str}</i>",
        "",
        insights.executive_summary,
        "",
        "<b>Ключевые метрики:</b>",
        f"  Выручка: {_fmt(data.current.revenue_before_spp)} ₽ "
        f"{_arrow(data.current.revenue_before_spp, data.previous.revenue_before_spp)} "
        f"{_change(data.current.revenue_before_spp, data.previous.revenue_before_spp)}",
        f"  Маржа: {_fmt(data.current.margin)} ₽ ({data.current.margin_pct:.1f}%) "
        f"{_arrow(data.current.margin, data.previous.margin)} "
        f"{_change(data.current.margin, data.previous.margin)}",
        f"  ДРР: {data.current.drr_pct:.1f}% "
        f"{_arrow(data.current.drr_pct, data.previous.drr_pct)}",
        f"  Заказы: {_fmt(data.current.orders_count)} шт "
        f"{_arrow(data.current.orders_count, data.previous.orders_count)} "
        f"{_change(data.current.orders_count, data.previous.orders_count)}",
    ]

    # TOP recommendations (up to 3)
    rec_sections = [s for s in insights.sections if s.section_id == 11]
    if rec_sections and rec_sections[0].root_causes:
        lines.append("")
        lines.append("<b>Рекомендации:</b>")
        for rc in rec_sections[0].root_causes[:3]:
            lines.append(f"  • {rc.recommendation}")

    # Footer
    lines.append("")
    conf = _confidence_emoji(insights.overall_confidence)
    footer = f"{conf} Confidence: {insights.overall_confidence:.0%}"
    if meta:
        tokens = meta.get("input_tokens", 0) + meta.get("output_tokens", 0)
        footer += f" | Tokens: {tokens:,}"
    lines.append(footer)

    if notion_url:
        lines.append(f'\n📄 <a href="{notion_url}">Полный отчёт в Notion</a>')

    text = "\n".join(lines)
    if len(text) > MAX_TELEGRAM_MSG:
        text = text[:MAX_TELEGRAM_MSG - 50] + "\n\n... <i>полный отчёт в Notion</i>"

    return text
```

- [ ] **Step 2: Write test**

```python
# tests/reporter/test_formatter_telegram.py
"""Tests for Telegram HTML formatter."""
from datetime import date

from agents.reporter.analyst.schemas import ReportInsights, SectionInsight
from agents.reporter.collector.base import CollectedData, TopLevelMetrics
from agents.reporter.formatter.telegram import render_telegram
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )


def test_render_telegram_basic():
    html = render_telegram(
        insights=ReportInsights(
            executive_summary="Выручка выросла на 11%",
            sections=[],
            overall_confidence=0.85,
        ),
        data=CollectedData(
            scope=_scope().to_dict(),
            collected_at="2026-03-28T10:00:00",
            current=TopLevelMetrics(revenue_before_spp=500000, margin=100000, margin_pct=20.0, orders_count=120),
            previous=TopLevelMetrics(revenue_before_spp=450000, margin=90000, margin_pct=20.0, orders_count=110),
        ),
        scope=_scope(),
    )
    assert "Дневной фин. отчёт" in html
    assert "500 000" in html
    assert "🟢" in html  # confidence 0.85 >= 0.8


def test_render_telegram_with_notion_url():
    html = render_telegram(
        insights=ReportInsights(executive_summary="Test", sections=[], overall_confidence=0.5),
        data=CollectedData(
            scope=_scope().to_dict(), collected_at="",
            current=TopLevelMetrics(), previous=TopLevelMetrics(),
        ),
        scope=_scope(),
        notion_url="https://notion.so/page123",
    )
    assert "notion.so/page123" in html
    assert "🟡" in html  # confidence 0.5


def test_render_telegram_max_length():
    long_summary = "A" * 5000
    html = render_telegram(
        insights=ReportInsights(executive_summary=long_summary, sections=[], overall_confidence=0.9),
        data=CollectedData(
            scope=_scope().to_dict(), collected_at="",
            current=TopLevelMetrics(), previous=TopLevelMetrics(),
        ),
        scope=_scope(),
    )
    assert len(html) <= 4000
```

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/reporter/test_formatter_telegram.py -v`

```bash
git add agents/reporter/formatter/telegram.py tests/reporter/test_formatter_telegram.py
git commit -m "feat(reporter): add Telegram HTML formatter"
```

---

### Task 15: Validator

**Files:**
- Create: `agents/reporter/validator.py`
- Test: `tests/reporter/test_validator.py`

- [ ] **Step 1: Write test**

```python
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
```

- [ ] **Step 2: Write implementation**

```python
# agents/reporter/validator.py
"""Deterministic report validator — no LLM, just checks."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.config import (
    MIN_CONFIDENCE,
    MIN_REPORT_LENGTH,
    MIN_TOGGLE_SECTIONS,
    MAX_PLACEHOLDERS,
)


@dataclass
class ValidationResult:
    verdict: Literal["PASS", "RETRY", "FAIL"]
    issues: list[str] = field(default_factory=list)


def validate(report_md: str, insights: ReportInsights) -> ValidationResult:
    """Validate report quality. Returns PASS/RETRY/FAIL."""
    issues: list[str] = []

    # 1. Minimum sections
    toggle_count = report_md.count("## ▶")
    if toggle_count < MIN_TOGGLE_SECTIONS:
        issues.append(f"Only {toggle_count} sections, need ≥{MIN_TOGGLE_SECTIONS}")

    # 2. Russian text present
    russian_chars = len(re.findall(r"[а-яА-ЯёЁ]", report_md))
    total_chars = max(len(report_md), 1)
    if russian_chars / total_chars < 0.1:
        issues.append("Low Russian text ratio")

    # 3. No raw JSON leak
    stripped = report_md.strip()
    if stripped.startswith("{") or stripped.startswith("```json") or stripped.startswith('"detailed'):
        issues.append("Raw JSON detected in report")

    # 4. Confidence threshold
    if insights.overall_confidence < MIN_CONFIDENCE:
        issues.append(f"Low confidence: {insights.overall_confidence:.2f}")

    # 5. Placeholder check
    placeholders = ["Н/Д", "Данные отсутствуют", "TODO", "TBD", "N/A"]
    placeholder_count = sum(report_md.count(p) for p in placeholders)
    if placeholder_count > MAX_PLACEHOLDERS:
        issues.append(f"Too many placeholders: {placeholder_count}")

    # 6. Minimum length
    if len(report_md) < MIN_REPORT_LENGTH:
        issues.append(f"Report too short: {len(report_md)} chars")

    # Determine verdict
    has_critical = any(
        "Raw JSON" in i or "sections" in i.lower() or "too short" in i.lower()
        for i in issues
    )
    if has_critical:
        return ValidationResult(verdict="RETRY", issues=issues)
    if len(issues) > 3:
        return ValidationResult(verdict="FAIL", issues=issues)
    return ValidationResult(verdict="PASS", issues=issues)
```

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/reporter/test_validator.py -v`

```bash
git add agents/reporter/validator.py tests/reporter/test_validator.py
git commit -m "feat(reporter): add deterministic report validator"
```

---

## Wave 5: Delivery

### Task 16: Notion Delivery

**Files:**
- Create: `agents/reporter/delivery/__init__.py`
- Create: `agents/reporter/delivery/notion.py`
- Test: `tests/reporter/test_delivery.py`

- [ ] **Step 1: Write implementation**

```python
# agents/reporter/delivery/__init__.py
```

```python
# agents/reporter/delivery/notion.py
"""Notion delivery — upsert report page."""
from __future__ import annotations

import logging

from shared.notion_client import NotionClient

from agents.reporter.config import NOTION_DATABASE_ID, NOTION_TOKEN
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


def _get_notion_client() -> NotionClient:
    return NotionClient(token=NOTION_TOKEN, database_id=NOTION_DATABASE_ID)


async def upsert_notion(report_md: str, scope: ReportScope) -> str | None:
    """Upsert report to Notion. Returns page URL or None on failure."""
    client = _get_notion_client()
    if not client.enabled:
        logger.warning("Notion not configured, skipping delivery")
        return None

    try:
        url = await client.sync_report(
            start_date=scope.period_from.isoformat(),
            end_date=scope.period_to.isoformat(),
            report_md=report_md,
            report_type=scope.report_type.value.replace("_", " "),
            source="Reporter V4 (auto)",
        )
        logger.info("Notion upsert OK: %s", url)
        return url
    except Exception as e:
        logger.error("Notion delivery failed: %s", e)
        return None
```

- [ ] **Step 2: Commit**

```bash
git add agents/reporter/delivery/
git commit -m "feat(reporter): add Notion upsert delivery"
```

---

### Task 17: Telegram Delivery

**Files:**
- Create: `agents/reporter/delivery/telegram.py`

- [ ] **Step 1: Write implementation**

```python
# agents/reporter/delivery/telegram.py
"""Telegram delivery — send or edit message."""
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot

from agents.reporter.config import ADMIN_CHAT_ID, TELEGRAM_BOT_TOKEN
from agents.reporter.state import ReporterState
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


async def send_or_edit_telegram(
    html: str,
    scope: ReportScope,
    state: ReporterState,
    notion_url: str | None = None,
) -> int | None:
    """Send new message or edit existing for this scope. Returns message_id."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token not configured")
        return None

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    try:
        existing_msg_id = state.get_telegram_message_id(scope)

        if existing_msg_id:
            try:
                await bot.edit_message_text(
                    chat_id=ADMIN_CHAT_ID,
                    message_id=existing_msg_id,
                    text=html,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                logger.info("Telegram message edited: %d", existing_msg_id)
                return existing_msg_id
            except Exception as e:
                logger.warning("Edit failed, sending new: %s", e)

        msg = await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=html,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        logger.info("Telegram message sent: %d", msg.message_id)
        return msg.message_id

    except Exception as e:
        logger.error("Telegram delivery failed: %s", e)
        return None
    finally:
        await bot.session.close()


async def send_error_notification(
    scope: ReportScope,
    issues: list[str],
    state: ReporterState,
) -> None:
    """Send error notification — max 1 per report type per day."""
    from datetime import date

    key = f"error:{scope.report_type.value}:{date.today().isoformat()}"
    if state.was_notified(key):
        return  # Already notified today

    if not TELEGRAM_BOT_TOKEN:
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        text = (
            f"⚠️ <b>Ошибка: {scope.report_type.human_name}</b>\n"
            f"Период: {scope.period_str}\n\n"
            + "\n".join(f"• {i}" for i in issues[:5])
        )
        msg = await bot.send_message(
            chat_id=ADMIN_CHAT_ID, text=text, parse_mode="HTML"
        )
        state.mark_notified(key, telegram_message_id=msg.message_id)
    except Exception as e:
        logger.error("Error notification failed: %s", e)
    finally:
        await bot.session.close()


async def send_data_ready_notification(
    marketplace: str,
    state: ReporterState,
) -> None:
    """Send data-ready notification — max 1 per marketplace per day."""
    from datetime import date

    key = f"data_ready:{marketplace}:{date.today().isoformat()}"
    if state.was_notified(key):
        return

    if not TELEGRAM_BOT_TOKEN:
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"✅ Данные {marketplace.upper()} готовы, начинаю генерацию отчётов",
        )
        state.mark_notified(key)
    except Exception as e:
        logger.error("Data-ready notification failed: %s", e)
    finally:
        await bot.session.close()
```

- [ ] **Step 2: Commit**

```bash
git add agents/reporter/delivery/telegram.py
git commit -m "feat(reporter): add Telegram delivery with anti-spam (edit, dedup, 1/day errors)"
```

---

## Wave 6: Pipeline & Conductor

### Task 18: Pipeline

**Files:**
- Create: `agents/reporter/pipeline.py`
- Test: `tests/reporter/test_pipeline.py`

- [ ] **Step 1: Write implementation**

```python
# agents/reporter/pipeline.py
"""Main pipeline: Collect → Analyze → Format → Validate → Deliver."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from agents.reporter.analyst.analyst import analyze
from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.collector.base import BaseCollector, CollectedData
from agents.reporter.collector.financial import FinancialCollector
from agents.reporter.collector.funnel import FunnelCollector
from agents.reporter.collector.marketing import MarketingCollector
from agents.reporter.config import MAX_ATTEMPTS
from agents.reporter.delivery.notion import upsert_notion
from agents.reporter.delivery.telegram import send_or_edit_telegram, send_error_notification
from agents.reporter.formatter.notion import render_notion
from agents.reporter.formatter.telegram import render_telegram
from agents.reporter.playbook.loader import load_rules_from_state
from agents.reporter.playbook.updater import save_discovered_patterns
from agents.reporter.state import ReporterState
from agents.reporter.types import ReportScope
from agents.reporter.validator import validate

logger = logging.getLogger(__name__)

_COLLECTORS: dict[str, type[BaseCollector]] = {
    "financial": FinancialCollector,
    "marketing": MarketingCollector,
    "funnel": FunnelCollector,
}


@dataclass
class PipelineResult:
    success: bool
    notion_url: Optional[str] = None
    telegram_message_id: Optional[int] = None
    confidence: float = 0.0
    issues: list[str] | None = None
    error: Optional[str] = None


async def run_pipeline(scope: ReportScope, state: ReporterState) -> PipelineResult:
    """Execute full pipeline for one report."""
    start = time.monotonic()

    # 1. Create run in Supabase
    state.create_run(scope)
    state.update_run(scope, status="collecting")

    try:
        # 2. Collect data
        collector_cls = _COLLECTORS.get(scope.report_type.collector_kind)
        if not collector_cls:
            raise ValueError(f"No collector for {scope.report_type.collector_kind}")

        collector = collector_cls()
        data = await collector.collect(scope)

        # 3. Load playbook rules
        state.update_run(scope, status="analyzing")
        rules = load_rules_from_state(state, scope.report_type.value)

        # 4. LLM Analysis
        insights, meta = await analyze(data, scope, rules)

        # 5. Format
        state.update_run(scope, status="formatting")
        notion_md = render_notion(insights, data, scope)
        telegram_html = render_telegram(insights, data, scope, meta=meta)

        # 6. Validate
        result = validate(notion_md, insights)

        if result.verdict == "RETRY":
            logger.warning("Validation RETRY: %s", result.issues)
            # Retry with hints
            insights, meta = await analyze(data, scope, rules, retry_hint=result.issues)
            notion_md = render_notion(insights, data, scope)
            telegram_html = render_telegram(insights, data, scope, meta=meta)
            result = validate(notion_md, insights)

        if result.verdict == "FAIL":
            duration = time.monotonic() - start
            state.update_run(scope, status="failed", issues=result.issues, duration_sec=duration)
            await send_error_notification(scope, result.issues, state)
            return PipelineResult(success=False, issues=result.issues)

        # 7. Deliver
        state.update_run(scope, status="delivering")
        notion_url = await upsert_notion(notion_md, scope)
        telegram_html_with_url = render_telegram(insights, data, scope, notion_url=notion_url, meta=meta)
        tg_msg_id = await send_or_edit_telegram(telegram_html_with_url, scope, state)

        # 8. Log success
        duration = time.monotonic() - start
        state.update_run(
            scope,
            status="success",
            notion_url=notion_url,
            telegram_message_id=tg_msg_id,
            confidence=insights.overall_confidence,
            duration_sec=duration,
            llm_model=meta.get("model"),
            llm_tokens_in=meta.get("input_tokens"),
            llm_tokens_out=meta.get("output_tokens"),
        )

        # 9. Save discovered patterns
        if insights.discovered_patterns:
            save_discovered_patterns(state, insights.discovered_patterns, scope)

        logger.info(
            "Pipeline complete: %s, confidence=%.2f, duration=%.1fs",
            scope.report_type.value, insights.overall_confidence, duration,
        )

        return PipelineResult(
            success=True,
            notion_url=notion_url,
            telegram_message_id=tg_msg_id,
            confidence=insights.overall_confidence,
        )

    except Exception as e:
        duration = time.monotonic() - start
        logger.error("Pipeline failed: %s", e, exc_info=True)
        state.update_run(scope, status="error", error=str(e), duration_sec=duration)
        await send_error_notification(scope, [str(e)], state)
        return PipelineResult(success=False, error=str(e))
```

- [ ] **Step 2: Write test**

```python
# tests/reporter/test_pipeline.py
"""Tests for the full pipeline (all components mocked)."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.reporter.pipeline import run_pipeline
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )


def _mock_state():
    state = MagicMock()
    state.create_run = MagicMock()
    state.update_run = MagicMock()
    state.get_active_rules = MagicMock(return_value=[])
    state.get_telegram_message_id = MagicMock(return_value=None)
    state.was_notified = MagicMock(return_value=False)
    state.mark_notified = MagicMock()
    state.save_pending_pattern = MagicMock()
    return state


@pytest.mark.asyncio
@patch("agents.reporter.pipeline.FinancialCollector")
@patch("agents.reporter.pipeline.analyze")
@patch("agents.reporter.pipeline.upsert_notion", new_callable=AsyncMock)
@patch("agents.reporter.pipeline.send_or_edit_telegram", new_callable=AsyncMock)
@patch("agents.reporter.pipeline.send_error_notification", new_callable=AsyncMock)
async def test_pipeline_success(mock_err, mock_tg, mock_notion, mock_analyze, mock_collector_cls):
    from agents.reporter.analyst.schemas import ReportInsights, SectionInsight
    from agents.reporter.collector.base import CollectedData, TopLevelMetrics

    # Setup mocks
    mock_collector = MagicMock()
    mock_collector.collect = AsyncMock(return_value=CollectedData(
        scope=_scope().to_dict(), collected_at="",
        current=TopLevelMetrics(revenue_before_spp=500000),
        previous=TopLevelMetrics(revenue_before_spp=450000),
    ))
    mock_collector_cls.return_value = mock_collector

    mock_analyze.return_value = (
        ReportInsights(
            executive_summary="Test",
            sections=[SectionInsight(section_id=i, title=f"S{i}", summary=f"Sum{i}") for i in range(13)],
            overall_confidence=0.85,
        ),
        {"model": "test", "input_tokens": 100, "output_tokens": 50},
    )
    mock_notion.return_value = "https://notion.so/page123"
    mock_tg.return_value = 42

    state = _mock_state()
    result = await run_pipeline(_scope(), state)

    assert result.success is True
    assert result.notion_url == "https://notion.so/page123"
    assert result.telegram_message_id == 42
    state.update_run.assert_called()
```

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/reporter/test_pipeline.py -v`

```bash
git add agents/reporter/pipeline.py tests/reporter/test_pipeline.py
git commit -m "feat(reporter): add main pipeline (Collect→Analyze→Format→Validate→Deliver)"
```

---

### Task 19: Conductor

**Files:**
- Create: `agents/reporter/conductor.py`
- Test: `tests/reporter/test_conductor.py`

- [ ] **Step 1: Write implementation**

```python
# agents/reporter/conductor.py
"""Conductor — gate checks, scheduling, pipeline execution."""
from __future__ import annotations

import logging
from datetime import date

from agents.reporter.config import MAX_ATTEMPTS
from agents.reporter.delivery.telegram import send_data_ready_notification, send_error_notification
from agents.reporter.gates import GateChecker
from agents.reporter.pipeline import run_pipeline
from agents.reporter.state import ReporterState
from agents.reporter.types import ReportScope, ReportType, compute_scope, get_today_reports

logger = logging.getLogger(__name__)


async def data_ready_check(
    gate_checker: GateChecker,
    state: ReporterState,
    today: date | None = None,
) -> None:
    """Hourly check: gates pass → generate pending reports."""
    today = today or date.today()

    # Check gates
    gate_result = gate_checker.check_both()
    if not gate_result.can_generate:
        logger.info(
            "Gates not passed: %s",
            [g.name for g in gate_result.gates if not g.passed],
        )
        return

    # Notify data ready (once per day)
    await send_data_ready_notification("WB+OZON", state)

    # Determine which reports need to run
    scheduled = get_today_reports(today)
    already_done = state.get_successful_today(today)

    pending = [
        rt for rt in scheduled
        if rt.value not in already_done
    ]

    if not pending:
        logger.info("All %d reports already done for %s", len(scheduled), today)
        return

    logger.info("Generating %d reports: %s", len(pending), [r.value for r in pending])

    for rt in pending:
        scope = compute_scope(rt, today)

        # Check attempt count
        attempts = state.get_attempt_count(scope)
        if attempts >= MAX_ATTEMPTS:
            logger.warning("Max attempts (%d) reached for %s", MAX_ATTEMPTS, rt.value)
            continue

        if attempts > 0:
            state.increment_attempt(scope)

        # Add caveats to scope context
        result = await run_pipeline(scope, state)

        if result.success:
            logger.info("Report %s generated successfully", rt.value)
        else:
            logger.warning("Report %s failed: %s", rt.value, result.error or result.issues)


async def deadline_check(state: ReporterState, today: date | None = None) -> None:
    """13:00 check: alert if daily report not ready."""
    today = today or date.today()
    done = state.get_successful_today(today)

    if ReportType.FINANCIAL_DAILY.value not in done:
        scope = compute_scope(ReportType.FINANCIAL_DAILY, today)
        await send_error_notification(
            scope,
            ["Дневной отчёт не сгенерирован к дедлайну (13:00)"],
            state,
        )


async def heartbeat(state: ReporterState) -> None:
    """Periodic health status to Telegram."""
    from datetime import date as date_cls

    from aiogram import Bot

    from agents.reporter.config import ADMIN_CHAT_ID, TELEGRAM_BOT_TOKEN

    today = date_cls.today()
    runs = state.get_today_status(today)

    success = sum(1 for r in runs if r["status"] == "success")
    failed = sum(1 for r in runs if r["status"] in ("failed", "error"))
    pending = sum(1 for r in runs if r["status"] not in ("success", "failed", "error"))

    text = (
        f"💓 Reporter V4 — heartbeat\n"
        f"📅 {today.isoformat()}\n"
        f"✅ Готово: {success} | ❌ Ошибки: {failed} | ⏳ Ожидает: {pending}"
    )

    if TELEGRAM_BOT_TOKEN:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        try:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)
        finally:
            await bot.session.close()
```

- [ ] **Step 2: Write test**

```python
# tests/reporter/test_conductor.py
"""Tests for conductor orchestration."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.reporter.conductor import data_ready_check, deadline_check


@pytest.mark.asyncio
@patch("agents.reporter.conductor.run_pipeline", new_callable=AsyncMock)
@patch("agents.reporter.conductor.send_data_ready_notification", new_callable=AsyncMock)
async def test_data_ready_generates_pending_reports(mock_notify, mock_pipeline):
    from agents.reporter.pipeline import PipelineResult

    mock_pipeline.return_value = PipelineResult(success=True)

    gate_checker = MagicMock()
    gate_result = MagicMock()
    gate_result.can_generate = True
    gate_result.gates = []
    gate_checker.check_both.return_value = gate_result

    state = MagicMock()
    state.get_successful_today.return_value = set()
    state.get_attempt_count.return_value = 0

    await data_ready_check(gate_checker, state, today=date(2026, 3, 24))  # Tuesday
    mock_pipeline.assert_called_once()  # Only FINANCIAL_DAILY on Tuesday


@pytest.mark.asyncio
@patch("agents.reporter.conductor.run_pipeline", new_callable=AsyncMock)
@patch("agents.reporter.conductor.send_data_ready_notification", new_callable=AsyncMock)
async def test_data_ready_skips_done_reports(mock_notify, mock_pipeline):
    gate_checker = MagicMock()
    gate_result = MagicMock()
    gate_result.can_generate = True
    gate_result.gates = []
    gate_checker.check_both.return_value = gate_result

    state = MagicMock()
    state.get_successful_today.return_value = {"financial_daily"}  # Already done
    state.get_attempt_count.return_value = 0

    await data_ready_check(gate_checker, state, today=date(2026, 3, 24))
    mock_pipeline.assert_not_called()


@pytest.mark.asyncio
@patch("agents.reporter.conductor.send_error_notification", new_callable=AsyncMock)
async def test_deadline_alerts_missing_daily(mock_notify):
    state = MagicMock()
    state.get_successful_today.return_value = set()  # Nothing done

    await deadline_check(state, today=date(2026, 3, 28))
    mock_notify.assert_called_once()
```

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/reporter/test_conductor.py -v`

```bash
git add agents/reporter/conductor.py tests/reporter/test_conductor.py
git commit -m "feat(reporter): add conductor (gate check → schedule → pipeline → alert)"
```

---

### Task 20: Scheduler

**Files:**
- Create: `agents/reporter/scheduler.py`

- [ ] **Step 1: Write implementation**

```python
# agents/reporter/scheduler.py
"""APScheduler setup — 3 cron jobs replacing 15 in V3."""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from agents.reporter.config import (
    DATA_READY_CHECK_HOURS,
    DEADLINE_HOUR,
    HEARTBEAT_INTERVAL_HOURS,
    TIMEZONE,
)

logger = logging.getLogger(__name__)


def create_scheduler(gate_checker, state) -> AsyncIOScheduler:
    """Create scheduler with 3 jobs."""
    from agents.reporter.conductor import data_ready_check, deadline_check, heartbeat

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Job 1: data_ready_check — hourly 06:00-12:00
    scheduler.add_job(
        data_ready_check,
        trigger=CronTrigger(
            hour=f"{min(DATA_READY_CHECK_HOURS)}-{max(DATA_READY_CHECK_HOURS)}",
            minute=0,
            timezone=TIMEZONE,
        ),
        kwargs={"gate_checker": gate_checker, "state": state},
        id="data_ready_check",
        name="Check data readiness and generate reports",
        replace_existing=True,
    )

    # Job 2: deadline_check — 13:00
    scheduler.add_job(
        deadline_check,
        trigger=CronTrigger(
            hour=DEADLINE_HOUR,
            minute=0,
            timezone=TIMEZONE,
        ),
        kwargs={"state": state},
        id="deadline_check",
        name="Alert if daily report missing",
        replace_existing=True,
    )

    # Job 3: heartbeat — every 6 hours
    scheduler.add_job(
        heartbeat,
        trigger=IntervalTrigger(hours=HEARTBEAT_INTERVAL_HOURS),
        kwargs={"state": state},
        id="heartbeat",
        name="Health status heartbeat",
        replace_existing=True,
    )

    logger.info("Scheduler created with 3 jobs")
    return scheduler
```

- [ ] **Step 2: Commit**

```bash
git add agents/reporter/scheduler.py
git commit -m "feat(reporter): add scheduler with 3 cron jobs"
```

---

## Wave 7: Bot & Entry Point

### Task 21: Telegram Bot

**Files:**
- Create: `agents/reporter/bot/__init__.py`
- Create: `agents/reporter/bot/bot.py`
- Create: `agents/reporter/bot/handlers.py`
- Create: `agents/reporter/bot/keyboards.py`

- [ ] **Step 1: Write bot.py**

```python
# agents/reporter/bot/__init__.py
```

```python
# agents/reporter/bot/bot.py
"""Telegram bot setup — aiogram 3.x polling."""
from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher

from agents.reporter.bot.handlers import register_handlers
from agents.reporter.config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)


async def start_bot(state, gate_checker) -> None:
    """Start bot polling. Blocks until stopped."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("REPORTER_V4_BOT_TOKEN not set, bot disabled")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    register_handlers(dp, state, gate_checker)

    logger.info("Starting Reporter V4 Telegram bot")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
```

- [ ] **Step 2: Write handlers.py**

```python
# agents/reporter/bot/handlers.py
"""Telegram command handlers."""
from __future__ import annotations

import logging
from datetime import date

from aiogram import Dispatcher, types
from aiogram.filters import Command

from agents.reporter.bot.keyboards import playbook_review_keyboard
from agents.reporter.types import ReportType, compute_scope

logger = logging.getLogger(__name__)


def register_handlers(dp: Dispatcher, state, gate_checker) -> None:
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer(
            "Reporter V4 Bot\n\n"
            "/status — статус отчётов\n"
            "/run <type> — запустить отчёт\n"
            "/rules — активные правила\n"
            "/pending — паттерны на ревью\n"
            "/health — состояние системы\n"
            "/logs <type> — последние runs"
        )

    @dp.message(Command("status"))
    async def cmd_status(message: types.Message):
        today = date.today()
        runs = state.get_today_status(today)
        if not runs:
            await message.answer(f"📅 {today}: нет запусков")
            return

        lines = [f"📅 <b>Статус отчётов {today}</b>\n"]
        for r in runs:
            status_emoji = {"success": "✅", "failed": "❌", "error": "💥", "pending": "⏳"}.get(r["status"], "🔄")
            lines.append(f"{status_emoji} {r['report_type']}: {r['status']} (attempt {r.get('attempt', 1)})")

        await message.answer("\n".join(lines), parse_mode="HTML")

    @dp.message(Command("run"))
    async def cmd_run(message: types.Message):
        from agents.reporter.pipeline import run_pipeline

        args = message.text.split()[1:] if message.text else []
        if not args:
            types_list = "\n".join(f"  {rt.value}" for rt in ReportType)
            await message.answer(f"Usage: /run <type> [date]\n\nTypes:\n{types_list}")
            return

        try:
            rt = ReportType(args[0])
        except ValueError:
            await message.answer(f"Unknown type: {args[0]}")
            return

        target_date = date.today()
        if len(args) > 1:
            try:
                target_date = date.fromisoformat(args[1])
            except ValueError:
                await message.answer(f"Invalid date: {args[1]}")
                return

        await message.answer(f"⏳ Генерирую {rt.human_name} за {target_date}...")
        scope = compute_scope(rt, target_date)
        result = await run_pipeline(scope, state)

        if result.success:
            await message.answer(
                f"✅ {rt.human_name} готов!\n"
                f"Confidence: {result.confidence:.0%}\n"
                f"Notion: {result.notion_url or 'N/A'}"
            )
        else:
            await message.answer(f"❌ Ошибка: {result.error or result.issues}")

    @dp.message(Command("rules"))
    async def cmd_rules(message: types.Message):
        rules = state.get_active_rules()
        if not rules:
            await message.answer("Нет активных правил")
            return
        lines = [f"📋 <b>Активные правила ({len(rules)})</b>\n"]
        for r in rules[:15]:
            source = "🤖" if r.get("source") == "llm_discovered" else "✍️"
            lines.append(f"{source} {r['rule_text'][:100]}")
        await message.answer("\n".join(lines), parse_mode="HTML")

    @dp.message(Command("pending"))
    async def cmd_pending(message: types.Message):
        pending = state._sb.table("analytics_rules").select("*").eq(
            "status", "pending_review"
        ).execute().data

        if not pending:
            await message.answer("Нет паттернов на ревью")
            return

        for p in pending[:5]:
            text = (
                f"🔍 <b>Новый паттерн</b>\n\n"
                f"{p['rule_text']}\n\n"
                f"Confidence: {p.get('confidence', 0):.0%}\n"
                f"Доказательства: {p.get('evidence', 'N/A')}"
            )
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=playbook_review_keyboard(p["id"]),
            )

    @dp.message(Command("health"))
    async def cmd_health(message: types.Message):
        from agents.reporter.analyst.circuit_breaker import CircuitBreaker, _circuit_breaker
        from agents.reporter.analyst import analyst

        cb = analyst._circuit_breaker
        gate_result = gate_checker.check_both()

        lines = [
            "<b>🏥 Health Check</b>\n",
            f"Circuit Breaker: {cb.state.value} (failures: {cb.failure_count})",
            f"Gates: {'✅ PASS' if gate_result.can_generate else '❌ BLOCKED'}",
        ]
        for g in gate_result.gates:
            emoji = "✅" if g.passed else "❌"
            lines.append(f"  {emoji} {g.name}: {g.detail}")

        await message.answer("\n".join(lines), parse_mode="HTML")

    @dp.message(Command("logs"))
    async def cmd_logs(message: types.Message):
        args = message.text.split()[1:] if message.text else []
        report_type = args[0] if args else "financial_daily"

        runs = state._sb.table("report_runs").select(
            "report_date,status,attempt,confidence,duration_sec,error"
        ).eq("report_type", report_type).order(
            "created_at", desc=True
        ).limit(5).execute().data

        if not runs:
            await message.answer(f"Нет запусков для {report_type}")
            return

        lines = [f"📋 <b>Последние runs: {report_type}</b>\n"]
        for r in runs:
            status_emoji = {"success": "✅", "failed": "❌", "error": "💥"}.get(r["status"], "🔄")
            dur = f"{r.get('duration_sec', 0):.0f}s" if r.get("duration_sec") else "?"
            conf = f"{r.get('confidence', 0):.0%}" if r.get("confidence") else "?"
            lines.append(f"{status_emoji} {r['report_date']} | {r['status']} | {dur} | conf={conf}")

        await message.answer("\n".join(lines), parse_mode="HTML")

    # Callback for playbook review
    @dp.callback_query(lambda c: c.data and c.data.startswith("rule:"))
    async def on_rule_review(callback: types.CallbackQuery):
        _, action, rule_id = callback.data.split(":")
        if action == "approve":
            state.update_rule_status(rule_id, "active")
            await callback.answer("✅ Правило активировано")
        elif action == "reject":
            state.update_rule_status(rule_id, "rejected")
            await callback.answer("❌ Правило отклонено")
        await callback.message.edit_reply_markup(reply_markup=None)
```

- [ ] **Step 3: Write keyboards.py**

```python
# agents/reporter/bot/keyboards.py
"""Inline keyboards for Telegram bot."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def playbook_review_keyboard(rule_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"rule:approve:{rule_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"rule:reject:{rule_id}"),
        ],
    ])
```

- [ ] **Step 4: Commit**

```bash
git add agents/reporter/bot/
git commit -m "feat(reporter): add Telegram bot with commands and playbook review keyboards"
```

---

### Task 22: Entry Point

**Files:**
- Create: `agents/reporter/__main__.py`

- [ ] **Step 1: Write entry point**

```python
# agents/reporter/__main__.py
"""Reporter V4 entry point: scheduler + bot."""
import argparse
import asyncio
import logging
import signal

from agents.reporter.config import LOG_LEVEL, SUPABASE_SERVICE_KEY, SUPABASE_URL


def _configure_logging():
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _create_state():
    from supabase import create_client

    from agents.reporter.state import ReporterState

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return ReporterState(client=client)


async def run(dry_run: bool = False):
    _configure_logging()
    logger = logging.getLogger("agents.reporter")
    logger.info("Reporter V4 starting...")

    state = _create_state()

    from agents.reporter.gates import GateChecker

    gate_checker = GateChecker()

    from agents.reporter.scheduler import create_scheduler

    scheduler = create_scheduler(gate_checker, state)

    if dry_run:
        logger.info("DRY RUN — printing jobs:")
        for job in scheduler.get_jobs():
            logger.info("  %s: %s", job.id, job.trigger)
        return

    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))

    stop_event = asyncio.Event()

    def _shutdown(*_):
        logger.info("Shutdown requested")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_event_loop().add_signal_handler(sig, _shutdown)

    # Start bot (runs in background)
    from agents.reporter.bot.bot import start_bot

    bot_task = asyncio.create_task(start_bot(state, gate_checker))

    try:
        await stop_event.wait()
    finally:
        bot_task.cancel()
        scheduler.shutdown(wait=False)
        logger.info("Reporter V4 stopped")


def main():
    parser = argparse.ArgumentParser(description="Reporter V4")
    parser.add_argument("--dry-run", action="store_true", help="Print jobs and exit")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import chain works**

Run: `python -c "from agents.reporter.__main__ import main; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add agents/reporter/__main__.py
git commit -m "feat(reporter): add __main__.py entry point (scheduler + bot)"
```

---

## Wave 8: Supabase Tables & Migration

### Task 23: SQL Migration Script

**Files:**
- Create: `agents/reporter/migrations/001_create_tables.sql`

- [ ] **Step 1: Write SQL migration**

```sql
-- agents/reporter/migrations/001_create_tables.sql
-- Reporter V4 Supabase tables

-- ── Report Runs ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS report_runs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    report_date DATE NOT NULL,
    report_type TEXT NOT NULL,
    scope_hash TEXT NOT NULL,
    scope_json JSONB NOT NULL,
    status TEXT DEFAULT 'pending',
    attempt INT DEFAULT 1,
    notion_url TEXT,
    telegram_message_id BIGINT,
    telegram_chat_id BIGINT,
    confidence FLOAT,
    cost_usd FLOAT,
    duration_sec FLOAT,
    issues JSONB,
    error TEXT,
    llm_model TEXT,
    llm_tokens_in INT,
    llm_tokens_out INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(report_date, report_type, scope_hash)
);

ALTER TABLE report_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON report_runs FOR ALL TO postgres USING (true);
CREATE POLICY "authenticated_read" ON report_runs FOR SELECT TO authenticated USING (true);

-- ── Analytics Rules (Playbook) ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics_rules (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    rule_text TEXT NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    confidence FLOAT,
    evidence TEXT,
    report_types TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT
);

ALTER TABLE analytics_rules ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON analytics_rules FOR ALL TO postgres USING (true);
CREATE POLICY "authenticated_read" ON analytics_rules FOR SELECT TO authenticated USING (true);

-- ── Notification Log ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notification_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    notification_key TEXT NOT NULL UNIQUE,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    telegram_message_id BIGINT
);

ALTER TABLE notification_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON notification_log FOR ALL TO postgres USING (true);
```

- [ ] **Step 2: Commit**

```bash
git add agents/reporter/migrations/
git commit -m "feat(reporter): add Supabase migration SQL (3 tables with RLS)"
```

---

### Task 24: Migration Checklist & Docker

**Files:**
- Create: `agents/reporter/MIGRATION.md`
- Modify: `deploy/docker-compose.local.yml` (add wookiee_reporter service)

- [ ] **Step 1: Write MIGRATION.md**

```markdown
# V4 Reporter — Migration Checklist

## Phase 1: BUILD
- [ ] Supabase tables created (run migrations/001_create_tables.sql)
- [ ] .env updated: REPORTER_V4_BOT_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY
- [ ] Base playbook rules loaded into analytics_rules table
- [ ] Dependencies installed: jinja2, supabase, aiogram>=3.0, pydantic>=2.0, openai

## Phase 2: TEST (shadow mode)
- [ ] V4 generates financial_daily to shadow Notion DB
- [ ] V4 generates financial_weekly correctly
- [ ] V4 generates marketing_weekly correctly
- [ ] V4 generates funnel_weekly correctly
- [ ] Anti-spam: max 1 error notification per type per day
- [ ] Circuit breaker tested (3 failures → stops)
- [ ] Telegram edit works on retry (no duplicate messages)
- [ ] Bot commands work: /status, /run, /health

## Phase 3: SWITCH
- [ ] V4 Notion database = production NOTION_DATABASE_ID
- [ ] V4 Telegram chat = production ADMIN_CHAT_ID
- [ ] V3 scheduler disabled (V3_REPORTS_ENABLED=false or stop container)
- [ ] Monitor 24 hours — no errors, all reports generated

## Phase 4: CLEANUP
- [ ] Delete agents/v3/ (except gates.py already copied)
- [ ] Delete dead V2 code:
  - agents/oleg/orchestrator/ (830 lines)
  - agents/oleg/agents/reporter/
  - agents/oleg/agents/advisor/
  - agents/oleg/agents/validator/
  - agents/oleg/agents/marketer/
  - agents/oleg/executor/
  - agents/oleg/watchdog/
- [ ] Delete 12 unused .md agents from agents/v3/agents/
- [ ] Remove SQLite state from deploy volumes
- [ ] Update docs/architecture.md
- [ ] Update docs/development-history.md

## Rollback to V2
If V4 fails:
1. Stop wookiee_reporter container
2. Re-enable V2 orchestrator in wookiee_oleg
3. V2 playbook.md and tools still in agents/oleg/
```

- [ ] **Step 2: Add Docker service**

Add to `deploy/docker-compose.local.yml`:

```yaml
wookiee_reporter:
  build:
    context: ..
    dockerfile: deploy/Dockerfile.reporter
  container_name: wookiee_reporter
  env_file: ../.env
  restart: unless-stopped
```

- [ ] **Step 3: Create Dockerfile**

```dockerfile
# deploy/Dockerfile.reporter
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "agents.reporter"]
```

- [ ] **Step 4: Commit**

```bash
git add agents/reporter/MIGRATION.md deploy/Dockerfile.reporter
git commit -m "feat(reporter): add migration checklist and Docker setup"
```

---

## Summary

| Wave | Tasks | Components |
|------|-------|-----------|
| 1. Foundation | 1-5 | config, types, schemas, circuit breaker, state, gates |
| 2. Collection | 6-9 | base collector, financial, marketing, funnel |
| 3. Analysis | 10-12 | LLM analyst, prompt files, playbook |
| 4. Formatting | 13-15 | Notion formatter, Telegram formatter, validator |
| 5. Delivery | 16-17 | Notion upsert, Telegram send/edit |
| 6. Pipeline | 18-20 | pipeline, conductor, scheduler |
| 7. Bot & Entry | 21-22 | Telegram bot, __main__.py |
| 8. Migration | 23-24 | SQL tables, Docker, checklist |

**Total: 24 tasks, ~35 files, ~2500 lines of code**

**Dependencies preserved:**
- `shared/data_layer/*` — all SQL queries reused unchanged
- `shared/notion_client.py` — sync_report() for Notion upsert
- `shared/clients/openrouter_client.py` — reference for LLM call pattern
- `agents/v3/gates.py` — copied to agents/reporter/gates.py
- `agents/oleg/playbook.md` — migrated to Supabase analytics_rules
