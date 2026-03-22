# Telegram UX Cleanup — Design Spec

**Цель:** Устранить спам, дубликаты, ошибки и английский язык в Telegram-сообщениях бота и Notion-отчётах.

**Контекст:** Бот за утро отправляет ~10 сообщений: повторные "Данные готовы" (каждый час 06-12), ошибки `NoneType.get()` с retry storm, Watchdog-алерты на несуществующую функцию. Отчёты генерируются на английском ("Passport", "Top Conclusions").

---

## Часть 1: Централизованный модуль сообщений

### Проблема
User-facing тексты разбросаны по 5+ файлам — `scheduler.py`, `conductor.py`, `monitor.py`, `delivery/telegram.py`, `conductor/messages.py`. Половина на русском, половина на английском. Изменить формат одного сообщения = искать по всему проекту.

### Решение
Новый файл `agents/v3/delivery/messages.py` — единый источник всех user-facing текстов.

```python
"""Централизованные шаблоны сообщений для Telegram (русский язык)."""

def data_ready(date: str, reports: list[str]) -> str:
    """Короткое уведомление о старте генерации.

    Заменяет format_data_ready() из conductor/messages.py.
    Gate-детали (wb_info, ozon_info) убраны намеренно —
    они нужны для отладки и остаются в логах, но не в Telegram.
    """
    reports_str = ", ".join(reports)
    return f"Данные готовы за {date}, запускаю: {reports_str}"

def report_error(date: str, report_type: str, error: str, attempt: int, max_attempts: int) -> str:
    """Заменяет format_alert() из conductor/messages.py."""
    return f"Ошибка отчёта «{report_type}» за {date} (попытка {attempt}/{max_attempts}):\n{error[:200]}"

def report_retries_exhausted(date: str, report_type: str) -> str:
    return f"Не удалось сгенерировать «{report_type}» за {date} после всех попыток. Требуется ручной запуск."

def watchdog_alert(status: str, failed: list[str], passed: list[str]) -> str:
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

def anomaly_alert(metric: str, channel: str, value: float, avg: float, pct_change: float) -> str:
    direction = "↓" if pct_change < 0 else "↑"
    return (
        f"Аномалия: {channel} {metric}\n"
        f"Значение: {value:,.0f} vs среднее {avg:,.0f} ({direction}{abs(pct_change):.1f}%)"
    )

def watchdog_repeated_failures(report_type: str, count: int) -> str:
    return (
        f"Повторные сбои отчёта «{report_type}»\n"
        f"Подряд неудач: {count}\n"
        "Требуется ручная проверка."
    )
```

### Маппинг существующих функций → новые

| Старая функция | Файл | Новая функция |
|---------------|------|--------------|
| `format_data_ready(wb_info, ozon_info, pending, report_date)` | `conductor/messages.py` | `data_ready(date, reports)` |
| `format_alert(report_type, reason, attempt, max_attempts)` | `conductor/messages.py` | `report_error(date, report_type, error, attempt, max_attempts)` |
| Inline f-strings в `_job_watchdog` | `monitor.py:343-357` | `watchdog_alert(status, failed, passed)` |
| Inline f-strings в `on_report_failure` | `monitor.py:384-388` | `watchdog_repeated_failures(report_type, count)` |

**Примечание:** Gate-детали (количество заказов по каналам, timestamps ETL и т.д.) намеренно убраны из Telegram-сообщения. Они остаются в логах (`logger.info`) для отладки, но пользователю показывается только краткое сообщение.

### Затрагиваемые файлы
- `agents/v3/scheduler.py` — все `_send_admin(f"...")` → `_send_admin(messages.xxx(...))`
- `agents/v3/conductor/conductor.py` — `format_data_ready()` / `format_alert()` → `messages.data_ready()` / `messages.report_error()`
- `agents/v3/conductor/messages.py` — удалить (заменяется новым модулем)
- `agents/v3/monitor.py` — watchdog alert formatting → `messages.watchdog_alert()`

---

## Часть 2: Дедупликация "Данные готовы"

### Проблема
`data_ready_check` запускается каждый час (06-12 MSK, 7 раз). Если гейты прошли в 07:00 — отчёт запускается. В 08:00 — гейты снова проходят, снова сообщение, снова запуск. При retry — ещё сообщения. Итого ~10 за утро.

### Решение
In-memory флаг `_notified_dates: set[str]` в `ConductorState`. Не SQLite — при рестарте приложения сброс допустим (утреннее окно 06-12, за один рабочий цикл хватит).

```python
# В ConductorState:
def __init__(self, ...):
    ...
    self._notified_dates: set[str] = set()

def already_notified(self, report_date: str) -> bool:
    return report_date in self._notified_dates

def mark_notified(self, report_date: str) -> None:
    self._notified_dates.add(report_date)
```

**Важно:** `already_notified` — это отдельный флаг от статуса отчёта. Отчёт может быть "notified, but not yet succeeded" — мы всё равно запускаем генерацию, но НЕ повторяем сообщение.

```python
# В conductor.py, перед отправкой data_ready:
if state.already_notified(report_date):
    logger.debug("data_ready: already notified for %s, skipping message", report_date)
    # Всё равно запускаем отчёты если нужно, но НЕ шлём сообщение
else:
    await telegram_send(messages.data_ready(report_date, pending_types))
    state.mark_notified(report_date)
```

**Результат:** Одно сообщение за день: `"Данные готовы за 22 марта, запускаю: дневной фин, маркетинговый, воронка"`

### Retry-сообщения
При retry НЕ повторять "Данные готовы". Отправлять сообщение только при ошибке (через `messages.report_error()`), и только на финальной попытке — промежуточные ретраи молчат.

---

## Часть 3: Баг NoneType.get()

### Проблема
**Два места** с одинаковым багом:

1. `orchestrator.py:335` — `_run_report_pipeline()`:
```python
"report": compiler_result.get("artifact") if compiler_result else None,
```

2. `orchestrator.py:703` — `run_price_analysis()`:
```python
"report": compiler_result.get("artifact"),
```
(без guard вообще)

Когда `compiler_result` = None (или `report` = None), далее в `delivery/router.py:59`:
```python
inner = report.get("report", {})  # inner = None (ключ есть, значение None)
detailed_md = inner.get("detailed_report", "")  # AttributeError: 'NoneType'
```

Это вызывает retry storm: conductor видит ошибку → ретрай → снова ошибка → снова ретрай (до 3 раз) → 6+ сообщений в Telegram.

### Решение
Три defensive fix:

1. `orchestrator.py:335` (`_run_report_pipeline`):
```python
"report": (compiler_result.get("artifact") or {}) if compiler_result else {},
```

2. `orchestrator.py:703` (`run_price_analysis`):
```python
"report": (compiler_result.get("artifact") or {}) if compiler_result else {},
```

3. `delivery/router.py:59`:
```python
# Используем `or {}` вместо default parameter, потому что ключ "report"
# может присутствовать со значением None — default parameter не поможет.
inner = report.get("report") or {}
```

---

## Часть 4: Русский язык отчётов

### Проблема
`report-compiler.md` содержит английские названия секций и инструкции. LLM копирует их дословно → отчёт в Notion на английском.

Также `orchestrator.py:621-624` содержит хардкод английских названий секций для ценового отчёта.

### Решение

#### 4a. report-compiler.md — полный перевод

Весь промпт переписывается на русском. Заголовки разделов (`## Role` → `## Роль`, `## Rules` → `## Правила` и т.д.), инструкции, примеры. Технические термины (MTD, SPP, DRR, ROMI) остаются латиницей.

**Секции финансового отчёта (11 секций, 0-10):**

| # | Сейчас (EN) | Станет (RU) |
|---|------------|-------------|
| 0 | Passport | Паспорт |
| 1 | Top Conclusions | Ключевые выводы |
| 2 | Plan-Fact (MTD) | План-Факт (MTD) |
| 3 | Key Changes | Ключевые изменения |
| 4 | Price Strategy and SPP | Ценовая стратегия и СПП |
| 5 | Margin Reconciliation Waterfall | Каскад маржинальности |
| 6 | Marketplace Breakdown | Площадки (WB + OZON) |
| 7 | Model Drivers/Anti-Drivers | Драйверы и антидрайверы |
| 8 | Hypotheses → Actions | Гипотезы → Действия |
| 9 | Рекомендации Advisor | Рекомендации Advisor |
| 10 | Summary | Сводка |

**Секции ценового отчёта (8 секций, 0-7):**

| # | Сейчас (EN) | Станет (RU) |
|---|------------|-------------|
| 0 | Passport | Паспорт |
| 1 | Executive Summary | Итоги |
| 2 | Pricing Matrix | Ценовая матрица |
| 3 | Sales Trends | Тренды продаж |
| 4 | Stock-Price Matrix | Матрица остатки-цена |
| 5 | Marketing Impact | Влияние на маркетинг |
| 6 | Hypothesis Validation | Проверка гипотез |
| 7 | Action Plan | План действий |

**Trust Envelope Rendering** — секция уже частично на русском, довести до 100%.

#### 4b. orchestrator.py:621-624 — хардкод секций ценового отчёта

Текущий хардкод:
```python
"0) Паспорт  1) Executive summary  2) Ценовая матрица  "
"3) Тренды продаж  4) Сток-ценовая матрица  "
"5) Маркетинговый импакт  6) Валидация гипотез  7) План действий\n\n"
```

Заменить на:
```python
"0) Паспорт  1) Итоги  2) Ценовая матрица  "
"3) Тренды продаж  4) Матрица остатки-цена  "
"5) Влияние на маркетинг  6) Проверка гипотез  7) План действий\n\n"
```

---

## Часть 5: Watchdog fix (уже сделано)

Исправлено в текущей сессии (перед этим спеком):
- `_check_last_run` — убран `ImportError` (несуществующий `get_last_run_status`), заменён прямым запросом к `orchestrator_runs`
- `_check_db` — обёрнут в `asyncio.to_thread` (не блокирует event loop)

Верификация: изменения в `agents/v3/monitor.py`, тесты `tests/v3/` — 50/50 passed.

---

## Файлы для изменения (сводка)

| Файл | Часть | Изменение |
|------|-------|-----------|
| `agents/v3/delivery/messages.py` | 1 | **НОВЫЙ** — централизованные шаблоны сообщений |
| `agents/v3/agents/report-compiler.md` | 4 | Полный перевод на русский (секции, заголовки, инструкции) |
| `agents/v3/orchestrator.py` | 3, 4 | Fix None.get() на строках 335 и 703 + перевод хардкода секций (621-624) |
| `agents/v3/delivery/router.py` | 3 | Defensive `or {}` на строке 59 |
| `agents/v3/conductor/conductor.py` | 1, 2 | Дедупликация уведомлений, замена format_data_ready/format_alert → messages.py |
| `agents/v3/conductor/state.py` | 2 | Добавить in-memory `_notified_dates` + `already_notified()` / `mark_notified()` |
| `agents/v3/conductor/messages.py` | 1 | Удалить (заменяется delivery/messages.py) |
| `agents/v3/scheduler.py` | 1 | Все `_send_admin(f"...")` → messages.xxx() |
| `agents/v3/monitor.py` | 1, 5 | Watchdog/anomaly → messages.xxx() (+ уже fix check_db/last_run) |

## Не затрагивается

- Oleg v2 pipeline (`agents/oleg/`) — не трогаем, отдельная система
- `delivery/telegram.py` — формат отчёта для TG уже ок (confidence footer)
- `delivery/notion.py` — язык определяется содержимым detailed_report
- LLM task prompts (внутренние промпты агентов) — могут быть на английском, они не user-facing
