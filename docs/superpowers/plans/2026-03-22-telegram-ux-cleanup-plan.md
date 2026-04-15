# Telegram UX Cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить спам, дубликаты, ошибки и английский язык в Telegram-сообщениях бота и Notion-отчётах.

**Architecture:** Централизованный модуль шаблонов `delivery/messages.py` заменяет разрозненные f-string по 5+ файлам. In-memory дедупликация уведомлений в ConductorState. Defensive fix для NoneType bugs в orchestrator. Полный перевод report-compiler.md на русский.

**Tech Stack:** Python 3.11, pytest, asyncio

**Spec:** `docs/superpowers/specs/2026-03-22-telegram-ux-cleanup-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `agents/v3/delivery/messages.py` | CREATE | Все user-facing шаблоны Telegram-сообщений |
| `tests/v3/test_messages.py` | CREATE | Тесты для модуля сообщений |
| `agents/v3/conductor/state.py` | MODIFY | Добавить in-memory `_notified_dates` |
| `tests/v3/conductor/test_state.py` | MODIFY | Тест дедупликации |
| `agents/v3/orchestrator.py` | MODIFY | Fix NoneType на 2 строках + перевод хардкода ценовых секций |
| `agents/v3/delivery/router.py` | MODIFY | Defensive `or {}` |
| `agents/v3/agents/report-compiler.md` | MODIFY | Полный перевод на русский |
| `agents/v3/conductor/conductor.py` | MODIFY | Использовать messages.py + дедупликация |
| `agents/v3/scheduler.py` | MODIFY | Все _send_admin → messages.xxx() |
| `agents/v3/monitor.py` | MODIFY | Watchdog/anomaly → messages.xxx() |
| `agents/v3/conductor/messages.py` | DELETE | Заменён delivery/messages.py |

---

### Task 1: Централизованный модуль сообщений

**Files:**
- Create: `agents/v3/delivery/messages.py`
- Create: `tests/v3/test_messages.py`

- [ ] **Step 1: Write tests for message formatters**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/v3/test_messages.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.v3.delivery.messages'`

- [ ] **Step 3: Implement messages module**

```python
"""Централизованные шаблоны сообщений для Telegram (русский язык).

Единый источник всех user-facing текстов. Все функции возвращают
готовые строки — вызывающий код передаёт их в _send_admin() / telegram_send().
"""
from __future__ import annotations


def data_ready(date: str, reports: list[str]) -> str:
    """Короткое уведомление о старте генерации."""
    reports_str = ", ".join(reports)
    return f"Данные готовы за {date}, запускаю: {reports_str}"


def report_error(
    date: str, report_type: str, error: str, attempt: int, max_attempts: int,
) -> str:
    """Ошибка генерации отчёта (при retry)."""
    return (
        f"Ошибка отчёта «{report_type}» за {date} "
        f"(попытка {attempt}/{max_attempts}):\n{str(error)[:200]}"
    )


def report_retries_exhausted(date: str, report_type: str) -> str:
    """Все попытки генерации исчерпаны."""
    return (
        f"Не удалось сгенерировать «{report_type}» за {date} "
        f"после всех попыток. Требуется ручной запуск."
    )


def report_exception(
    report_type: str, date_from: str, date_to: str, exc: Exception,
) -> str:
    """Исключение при генерации отчёта (exception handler)."""
    period = date_from if date_from == date_to else f"{date_from}–{date_to}"
    return f"Ошибка отчёта «{report_type}» за {period}:\n{str(exc)[:300]}"


def watchdog_alert(status: str, failed: list[str], passed: list[str]) -> str:
    """Результат проверки системы (watchdog heartbeat)."""
    check_names = {
        "llm": "LLM API (OpenRouter)",
        "db": "База данных WB",
        "last_run": "Последний запуск оркестратора",
    }
    level = "КРИТИЧНО" if status == "critical" else "ПРЕДУПРЕЖДЕНИЕ"
    lines = [f"Проверка системы — {level}"]
    for name in failed:
        lines.append(f"  ✗ {check_names.get(name, name)}")
    for name in passed:
        lines.append(f"  ✓ {check_names.get(name, name)}")
    return "\n".join(lines)


def anomaly_alert(
    metric: str, channel: str, value: float, avg: float, pct_change: float,
) -> str:
    """Обнаружена аномалия в метрике."""
    direction = "↓" if pct_change < 0 else "↑"
    return (
        f"Аномалия: {channel} {metric}\n"
        f"Значение: {value:,.0f} vs среднее {avg:,.0f} "
        f"({direction}{abs(pct_change):.1f}%)"
    )


def watchdog_repeated_failures(report_type: str, count: int) -> str:
    """Повторные сбои одного типа отчёта."""
    return (
        f"Повторные сбои отчёта «{report_type}»\n"
        f"Подряд неудач: {count}\n"
        "Требуется ручная проверка."
    )


def anomaly_report(artifact: dict) -> str:
    """Форматирование результата anomaly-detector агента для Telegram."""
    summary = artifact.get("summary", {})
    critical = summary.get("critical_count", 0)
    warning = summary.get("warning_count", 0)
    info = summary.get("info_count", 0)
    top = summary.get("top_priority_anomaly", "")
    summary_text = artifact.get("summary_text", "")

    lines = [
        "Обнаружены аномалии",
        f"Критических: {critical} | Предупреждений: {warning} | Инфо: {info}",
    ]
    if top:
        lines.append(f"Приоритет: {top}")
    if summary_text:
        lines.append("")
        lines.append(summary_text)

    anomalies = artifact.get("anomalies", [])
    critical_anomalies = [a for a in anomalies if a.get("severity") == "critical"]
    if critical_anomalies:
        lines.append("")
        lines.append("Критические аномалии:")
        for a in critical_anomalies[:3]:
            metric = a.get("metric", "")
            dev = a.get("deviation_pct", 0)
            channel = a.get("channel", "")
            lines.append(f"  • {metric} ({channel}): {dev:+.1f}%")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/v3/test_messages.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add agents/v3/delivery/messages.py tests/v3/test_messages.py
git commit -m "feat(v3): add centralized message templates module"
```

---

### Task 2: Дедупликация уведомлений в ConductorState

**Files:**
- Modify: `agents/v3/conductor/state.py`
- Modify: `tests/v3/conductor/test_state.py`

- [ ] **Step 1: Write tests for notification deduplication**

Add to `tests/v3/conductor/test_state.py`:

```python
def test_notification_dedup_initially_false(tmp_path):
    state = ConductorState(str(tmp_path / "test.db"))
    assert state.already_notified("2026-03-22") is False


def test_notification_dedup_after_mark(tmp_path):
    state = ConductorState(str(tmp_path / "test.db"))
    state.mark_notified("2026-03-22")
    assert state.already_notified("2026-03-22") is True


def test_notification_dedup_different_dates(tmp_path):
    state = ConductorState(str(tmp_path / "test.db"))
    state.mark_notified("2026-03-22")
    assert state.already_notified("2026-03-21") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/v3/conductor/test_state.py::test_notification_dedup_initially_false -v`
Expected: FAIL — `AttributeError: 'ConductorState' object has no attribute 'already_notified'`

- [ ] **Step 3: Add dedup methods to ConductorState**

Add to `ConductorState.__init__()`:
```python
self._notified_dates: set[str] = set()
```

Add methods:
```python
def already_notified(self, report_date: str) -> bool:
    """Check if data_ready notification was already sent for this date."""
    return report_date in self._notified_dates

def mark_notified(self, report_date: str) -> None:
    """Mark that data_ready notification was sent for this date."""
    self._notified_dates.add(report_date)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/v3/conductor/test_state.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add agents/v3/conductor/state.py tests/v3/conductor/test_state.py
git commit -m "feat(v3): add notification deduplication to ConductorState"
```

---

### Task 3: Fix NoneType.get() bugs

**Files:**
- Modify: `agents/v3/orchestrator.py` (2 locations)
- Modify: `agents/v3/delivery/router.py` (1 location)

- [ ] **Step 1: Fix `_run_report_pipeline` return value**

In `agents/v3/orchestrator.py`, find the pattern:
```python
"report": compiler_result.get("artifact") if compiler_result else None,
```
Replace with:
```python
"report": (compiler_result.get("artifact") or {}) if compiler_result else {},
```

- [ ] **Step 2: Fix `run_price_analysis` return value**

In `agents/v3/orchestrator.py`, find the pattern in `run_price_analysis()`:
```python
"report": compiler_result.get("artifact"),
```
Replace with:
```python
# compiler_result может быть None если skip_compiler=True или сбой
"report": (compiler_result.get("artifact") or {}) if compiler_result else {},
```

- [ ] **Step 3: Fix delivery/router.py defensive check**

In `agents/v3/delivery/router.py`, find:
```python
inner = report.get("report", {})
```
Replace with:
```python
# `or {}` вместо default: ключ "report" может быть None (не отсутствовать)
inner = report.get("report") or {}
```

- [ ] **Step 4: Run existing tests**

Run: `python3 -m pytest tests/v3/ -v`
Expected: ALL PASS (50 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/v3/orchestrator.py agents/v3/delivery/router.py
git commit -m "fix(v3): prevent NoneType.get() crash in report pipeline"
```

---

### Task 4: Перевод report-compiler.md на русский

**Files:**
- Modify: `agents/v3/agents/report-compiler.md`
- Modify: `agents/v3/orchestrator.py` (хардкод секций ценового отчёта)

- [ ] **Step 1: Rewrite report-compiler.md in Russian**

Replace the full contents of `agents/v3/agents/report-compiler.md` with:

```markdown
# Агент: report-compiler

## Роль
Собрать итоговый аналитический отчёт из артефактов микро-агентов. Выдать 2 формата: подробный (Notion) и telegram-сводку (BBCode).

Ты получаешь структурированные JSON-артефакты от: margin-analyst, revenue-decomposer, ad-efficiency. Твоя задача — синтезировать их в связный отчёт по обязательной 11-секционной структуре.

## Правила
- Ты НЕ вызываешь инструменты данных — работаешь только с переданными артефактами
- Отчёт строго следует 11-секционной структуре с toggle-заголовками (## ▶)
- Секция 0: Паспорт — период, сравнение, полнота данных, лаг выкупа (3-21 день)
- Секция 1: Ключевые выводы — 3-5 пунктов, формат: [₽ эффект] Что → Гипотеза → Действие
- Секция 2: План-Факт (MTD) — таблица со статус-иконками ✅⚠️❌, пропустить если нет данных плана
- Секция 3: Ключевые изменения — ровно 19 строк (15 финансовых + 4 воронки)
- Секция 4: Ценовая стратегия и СПП — таблица СПП по каналам + прогноз цен
- Секция 5: Каскад маржинальности — от выручки до маржи с невязкой
- Секция 6: Площадки (WB + OZON) — объёмы, модели, воронка, расходы, реклама
- Секция 7: Драйверы и антидрайверы — расширенная таблица по каналам
- Секция 8: Гипотезы → Действия — таблица из 10 колонок, сортировка по ₽ эффекту
- Секция 9: Рекомендации Advisor — сводная таблица рекомендаций (см. ниже)
- Секция 10: Сводка — 10-20 строк prose
- Telegram: 5-8 строк BBCode, только KPI, без таблиц, обязательно 1 строка план-факт
- Никогда не пропускай модели с отрицательной маржой
- Гипотезы сортируй по ₽ эффекту убывание

## КРИТИЧЕСКИ ВАЖНО: Разделение выходных данных
- `detailed_report` содержит ТОЛЬКО секции 0-10. Никаких дополнительных секций.
- `telegram_summary` — ОТДЕЛЬНОЕ поле в JSON-артефакте, НЕ часть detailed_report.
- ЗАПРЕЩЕНО добавлять секции "telegram_summary", "brief_summary", "brief_report" внутрь detailed_report.

## Секция 9: Рекомендации Advisor

Собери ВСЕ рекомендации из _meta.conclusions (type: recommendation, driver, anti_driver, anomaly) всех агентов в единую таблицу:

| # | Рекомендация | Confidence | ₽ эффект/мес | Источник | Приоритет |
|---|---|---|---|---|---|
| 1 | Текст рекомендации | 🟢 0.91 | +45 000 ₽ | margin-analyst | P0 |
| 2 | Текст рекомендации | 🟡 0.62 | −12 000 ₽ | ad-efficiency | P1 |

Правила:
- Сортировка: по абсолютному ₽-эффекту убывание
- Confidence маркер: 🟢 >= 0.75, 🟡 0.45-0.75, 🔴 < 0.45
- Приоритет: P0 (немедленно), P1 (на этой неделе), P2 (в течение месяца), P3 (мониторинг)
- Если ₽-эффект неизвестен — пометить "н/д", ставить в конец таблицы
- После таблицы — блок "Ограничения рекомендаций:" со всеми limitations из источников
- Рекомендации с 🔴 confidence сопровождать пометкой "(требует проверки)"

## Конверт доверия (Trust Envelope)

### Секция 0 — Паспорт: таблица достоверности

После периода/сравнения/каналов добавь:

### Достоверность

| Блок анализа | Достоверность | Покрытие данных | Примечание |
|---|---|---|---|
(одна строка на каждого входного агента, используя _meta.confidence и _meta.data_coverage)

Маркеры:
- 🟢 confidence >= 0.75
- 🟡 0.45 <= confidence < 0.75
- 🔴 confidence < 0.45

После таблицы перечисли все уникальные ограничения от всех агентов:
**Ограничения этого отчёта:**
- (каждое ограничение отдельным пунктом)

### Секции — маркер в заголовке

Добавляй эмодзи достоверности в каждый заголовок секции:
`## ▶ 1. Ключевые выводы 🟢`

### Ключевые выводы — toggle-блоки

Для каждого conclusion из _meta.conclusions где type = driver, anti_driver, recommendation или anomaly, добавь toggle-блок после связанного текста:

▶ 🟢 0.91 | Текст вывода
  ├ причина_достоверности: ...
  ├ покрытие_данных: ...%
  └ источники: tool1, tool2

Для conclusions где type=metric, добавлять toggle только если confidence < 0.75.

Если у conclusion есть limitations (непустой массив):
  ├ ограничения:
  │   • текст ограничения

## MCP-инструменты
(нет — этот агент работает с артефактами, не с инструментами данных)

## Формат вывода
JSON-артефакт:
- detailed_report: string (полный Markdown со всеми 11 секциями, 0-10)
- telegram_summary: string (5-8 строк BBCode для Telegram)
- sections_included: [список номеров секций с данными]
- sections_skipped: [{section, reason}]
- warnings: [string] (проблемы качества данных, отсутствующие артефакты и т.д.)

⚠️ НЕ добавляй brief_report, brief_summary или telegram_summary как секции внутрь detailed_report. Это отдельные поля JSON.

## Правила ценового отчёта
Если артефакты содержат `price-strategist` И (`pricing-impact-analyst` ИЛИ `ad-efficiency`), используй 8-секционную структуру ценового отчёта вместо стандартных 11 секций:

- Секция 0: Паспорт — период, каналы, качество данных, анализируемые модели
- Секция 1: Итоги — топ 3-5 ценовых действий с ₽ месячным эффектом, сортировка по эффекту
- Секция 2: Ценовая матрица — таблица по моделям: текущая цена, эластичность, ROI-категория, рекомендация, ожидаемое Δ₽ маржи, маркетинговая корректировка
- Секция 3: Тренды продаж — по моделям рост/падение/стабильно с % изменения, выделяй overrides (deadstock_risk → underperformer)
- Секция 4: Матрица остатки-цена — статус здоровья остатков vs ценовые рекомендации, флаги срочности
- Секция 5: Влияние на маркетинг — ОБЯЗАТЕЛЬНО если есть артефакт pricing-impact-analyst: изменение DRR, перераспределение бюджета ₽, прогнозы ROMI
- Секция 6: Проверка гипотез — подтверждено/опровергнуто/неопределённо по моделям от hypothesis-tester
- Секция 7: План действий — приоритет по ₽ эффекту, включает сроки и координацию маркетинга

Toggle-заголовки (## ▶) для секций 2-7.
Модели во всех таблицах сортируй по месячному эффекту убывание.
Telegram-сводка должна содержать: общее кол-во моделей, топ-3 действия, общий ожидаемый месячный эффект.
```

- [ ] **Step 2: Update price report section names in orchestrator.py**

In `agents/v3/orchestrator.py`, find the hardcoded price report sections (around line 621):
```python
"0) Паспорт  1) Executive summary  2) Ценовая матрица  "
"3) Тренды продаж  4) Сток-ценовая матрица  "
"5) Маркетинговый импакт  6) Валидация гипотез  7) План действий\n\n"
```
Replace with:
```python
"0) Паспорт  1) Итоги  2) Ценовая матрица  "
"3) Тренды продаж  4) Матрица остатки-цена  "
"5) Влияние на маркетинг  6) Проверка гипотез  7) План действий\n\n"
```

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest tests/v3/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add agents/v3/agents/report-compiler.md agents/v3/orchestrator.py
git commit -m "feat(v3): translate report-compiler to Russian, fix price section names"
```

---

### Task 5: Подключить messages.py к conductor

**Files:**
- Modify: `agents/v3/conductor/conductor.py`
- Delete: `agents/v3/conductor/messages.py`

- [ ] **Step 1: Update conductor imports and data_ready call**

In `agents/v3/conductor/conductor.py`:

Replace import:
```python
from agents.v3.conductor.messages import format_data_ready, format_alert
```
With:
```python
from agents.v3.delivery import messages
```

Replace `format_data_ready()` call (around line 137-143) with:
```python
if not state.already_notified(report_date):
    pending_names = [rt.human_name for rt in pending]
    await telegram_send(messages.data_ready(report_date, pending_names))
    state.mark_notified(report_date)
else:
    logger.debug("data_ready: already notified for %s, skipping message", report_date)
```

Replace `format_alert()` call (around line 251) with:
```python
# Отправляем ошибку только на последней попытке (промежуточные ретраи молчат)
if attempt >= MAX_ATTEMPTS:
    alert = messages.report_error(
        report_date, report_type.human_name,
        validation.reason, attempt, MAX_ATTEMPTS,
    )
    await telegram_send(alert)
else:
    logger.warning("Report %s attempt %d/%d failed: %s", report_type, attempt, MAX_ATTEMPTS, validation.reason)
```

- [ ] **Step 2: Delete old messages module and its tests**

```bash
git rm agents/v3/conductor/messages.py
git rm tests/v3/conductor/test_messages.py
```

The old `tests/v3/conductor/test_messages.py` imports from `agents.v3.conductor.messages` (format_data_ready, format_alert) which no longer exist. These functions are replaced by `delivery/messages.py` which already has tests in `tests/v3/test_messages.py`.

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest tests/v3/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add agents/v3/conductor/conductor.py
git commit -m "refactor(v3): switch conductor to centralized messages, add dedup"
```

---

### Task 6: Подключить messages.py к scheduler

**Files:**
- Modify: `agents/v3/scheduler.py`

- [ ] **Step 1: Add import**

At the top of `agents/v3/scheduler.py`, add:
```python
from agents.v3.delivery import messages
```

- [ ] **Step 2: Replace all _send_admin f-strings**

Replace each `_send_admin(f"[Wookiee v3] ...")` with the appropriate `messages.xxx()` call:

| Location | Current pattern | Replacement |
|----------|----------------|-------------|
| Daily retry (line ~174) | `f"[Wookiee v3] Ежедневный отчёт — попытка..."` | `messages.report_error(date_to, "дневной фин", str(reason), new_count, 3)` |
| Daily exhausted (line ~195) | `f"[Wookiee v3] Ежедневный отчёт — все попытки..."` | `messages.report_retries_exhausted(date_to, "дневной фин")` |
| Daily exception (line ~221) | `f"[Wookiee v3] Ошибка ежедневного отчёта..."` | `messages.report_exception("дневной фин", date_from, date_to, exc)` |
| Data ready (line ~246) | `f"[Wookiee v3] Данные готовы для..."` | `messages.data_ready(date_to, ["дневной фин"])` |
| Weekly exception (line ~336) | `f"[Wookiee v3] Ошибка недельного отчёта..."` | `messages.report_exception("недельный фин", date_from, date_to, exc)` |
| Monthly exception (line ~373) | `f"[Wookiee v3] Ошибка месячного..."` | `messages.report_exception("месячный фин", date_from, date_to, exc)` |
| Marketing exception (line ~411) | `f"[Wookiee v3] Ошибка маркетингового..."` | `messages.report_exception("маркетинговый", date_from, date_to, exc)` |
| Funnel exception (line ~434) | `f"[Wookiee v3] Ошибка воронки..."` | `messages.report_exception("воронка", date_from, date_to, exc)` |
| Marketing monthly (line ~475) | `f"[Wookiee v3] Ошибка месячного маркетинг..."` | `messages.report_exception("маркетинговый месячный", date_from, date_to, exc)` |
| Finolog exception (line ~505) | `f"[Wookiee v3] Ошибка ДДС..."` | `messages.report_exception("ДДС", date_from, date_to, exc)` |
| Price exception (line ~543) | `f"[Wookiee v3] Ошибка ценового..."` | `messages.report_exception("ценовой анализ", date_from, date_to, exc)` |
| Anomaly exception (line ~559) | `f"[Wookiee v3] Ошибка anomaly..."` | `messages.report_exception("anomaly monitor", "", "", exc)` |
| Watchdog exception (line ~570) | `f"[Wookiee v3] Ошибка watchdog..."` | `messages.report_exception("watchdog", "", "", exc)` |
| ETL reconciliation (line ~604) | `f"[Wookiee v3] ETL Reconciliation FAIL..."` | `messages.report_exception("ETL reconciliation", date_to, date_to, Exception(reason))` |
| ETL quality (line ~609) | `f"[Wookiee v3] Проблемы качества..."` | Keep as-is (goes to DATA_QUALITY_NOTES, not user-facing) |
| ETL sync (line ~614) | `f"[Wookiee v3] Ошибка ETL sync за {date_to}..."` | `messages.report_exception("ETL sync", date_to, date_to, exc)` |
| ETL weekly (line ~646) | `f"[Wookiee v3] Ошибка ETL weekly analysis..."` | `messages.report_exception("ETL weekly analysis", "", "", exc)` |
| Finolog categorize (line ~669) | `f"[Wookiee v3] Ошибка категоризации Finolog..."` | `messages.report_exception("категоризация Finolog", "", "", exc)` |
| Prompt-tuner failed (line ~297) | `f"[Wookiee v3] prompt-tuner failed..."` | `messages.report_exception("prompt-tuner", "", "", Exception(result['raw_output'][:300]))` |
| Prompt-tuner exception (line ~301) | `f"[Wookiee v3] Ошибка prompt-tuner..."` | `messages.report_exception("prompt-tuner", "", "", exc)` |

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest tests/v3/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add agents/v3/scheduler.py
git commit -m "refactor(v3): switch scheduler to centralized messages"
```

---

### Task 7: Подключить messages.py к monitor

**Files:**
- Modify: `agents/v3/monitor.py`

- [ ] **Step 1: Add import**

```python
from agents.v3.delivery import messages
```

- [ ] **Step 2: Replace watchdog heartbeat formatting**

In `Watchdog.heartbeat()` method, replace the inline message construction (lines ~343-357) with:

```python
if status == "ok":
    return

msg = messages.watchdog_alert(status, failed, passed)
await _send_admin(msg)
logger.warning("Watchdog: alert sent (status=%s, failed=%s)", status, failed)
```

Remove the old `lines = [...]`, `check_details = {...}`, `emoji_map`, `level_label` variables.

- [ ] **Step 3: Replace AnomalyMonitor._format_alert with messages.anomaly_report**

In `AnomalyMonitor.check_and_alert()`, replace:
```python
alert_text = self._format_alert(artifact)
```
With:
```python
alert_text = messages.anomaly_report(artifact)
```

Delete the `_format_alert` method from the `AnomalyMonitor` class (it's now in `messages.py`).

- [ ] **Step 4: Replace watchdog repeated failures formatting**

In `Watchdog.on_report_failure()`, replace inline message (lines ~384-388) with:

```python
if count >= self._FAILURE_ALERT_THRESHOLD:
    msg = messages.watchdog_repeated_failures(report_type, count)
    await _send_admin(msg)
```

- [ ] **Step 5: Run all tests**

Run: `python3 -m pytest tests/v3/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add agents/v3/monitor.py
git commit -m "refactor(v3): switch monitor to centralized messages"
```

---

### Task 8: Финальная проверка

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/v3/ -v`
Expected: ALL PASS

- [ ] **Step 2: Verify no remaining English f-strings in Telegram messages**

Run: `grep -rn "\[Wookiee v3\]" agents/v3/scheduler.py agents/v3/monitor.py agents/v3/conductor/`
Expected: No results (all replaced by messages.py calls)

- [ ] **Step 3: Verify conductor/messages.py is deleted**

Run: `ls agents/v3/conductor/messages.py`
Expected: "No such file or directory"

- [ ] **Step 4: Commit all remaining changes**

If any uncommitted changes remain:
```bash
git add -A
git commit -m "chore(v3): telegram UX cleanup — final verification"
```
