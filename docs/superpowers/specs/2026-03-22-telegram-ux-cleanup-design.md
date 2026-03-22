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
    """Короткое уведомление о старте генерации."""
    reports_str = ", ".join(reports)
    return f"Данные готовы за {date}, запускаю: {reports_str}"

def report_error(date: str, report_type: str, error: str, attempt: int, max_attempts: int) -> str:
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

### Затрагиваемые файлы
- `agents/v3/scheduler.py` — все `_send_admin(f"...")` → `_send_admin(messages.xxx(...))`
- `agents/v3/conductor/conductor.py` — `format_data_ready()` → `messages.data_ready()`
- `agents/v3/conductor/messages.py` — удалить (заменяется новым модулем)
- `agents/v3/monitor.py` — watchdog alert formatting → `messages.watchdog_alert()`

---

## Часть 2: Дедупликация "Данные готовы"

### Проблема
`data_ready_check` запускается каждый час (06-12 MSK, 7 раз). Если гейты прошли в 07:00 — отчёт запускается. В 08:00 — гейты снова проходят, снова сообщение, снова запуск. При retry — ещё сообщения. Итого ~10 за утро.

### Решение
В `ConductorState` добавить флаг `notified_date` — дата, за которую уже отправлено уведомление.

```python
# В conductor.py, перед отправкой data_ready:
if state.already_notified(report_date):
    logger.debug("data_ready: already notified for %s, skipping", report_date)
    # Всё равно запускаем отчёты если нужно, но НЕ шлём сообщение
else:
    await telegram_send(messages.data_ready(report_date, pending_types))
    state.mark_notified(report_date)
```

**Результат:** Одно сообщение за день: `"Данные готовы за 22 марта, запускаю: дневной фин, маркетинговый, воронка"`

### Retry-сообщения
При retry НЕ повторять "Данные готовы". Отправлять сообщение только при ошибке (через `messages.report_error()`), и только если ошибка на финальной попытке (не на каждой).

---

## Часть 3: Баг NoneType.get()

### Проблема
`orchestrator.py:335`:
```python
"report": compiler_result.get("artifact") if compiler_result else None,
```

Когда `compiler_result` = None (например, `skip_compiler=True` для price_analysis), `report` = None. Далее в `delivery/router.py:59`:
```python
inner = report.get("report", {})  # inner = None
detailed_md = inner.get("detailed_report", "")  # AttributeError: 'NoneType'
```

Это вызывает retry storm: conductor видит ошибку → ретрай → снова ошибка → снова ретрай (до 3 раз) → 6+ сообщений в Telegram.

### Решение
Два defensive fix:

1. `orchestrator.py:335`:
```python
"report": (compiler_result.get("artifact") or {}) if compiler_result else {},
```

2. `delivery/router.py:59`:
```python
inner = report.get("report") or {}
```

---

## Часть 4: Русский язык отчётов

### Проблема
`report-compiler.md` содержит английские названия секций. LLM копирует их дословно → отчёт в Notion на английском.

### Решение
Перевести `report-compiler.md` полностью на русский:

**Секции финансового отчёта (11 секций, 0-10):**

| # | Название |
|---|----------|
| 0 | Паспорт |
| 1 | Ключевые выводы |
| 2 | План-Факт (MTD) |
| 3 | Ключевые изменения |
| 4 | Ценовая стратегия и СПП |
| 5 | Каскад маржинальности |
| 6 | Площадки (WB + OZON) |
| 7 | Драйверы и антидрайверы |
| 8 | Гипотезы → Действия |
| 9 | Рекомендации Advisor |
| 10 | Сводка |

**Секции ценового отчёта (8 секций, 0-7):**

| # | Название |
|---|----------|
| 0 | Паспорт |
| 1 | Итоги |
| 2 | Ценовая матрица |
| 3 | Тренды продаж |
| 4 | Матрица остатки-цена |
| 5 | Влияние на маркетинг |
| 6 | Проверка гипотез |
| 7 | План действий |

**Весь промпт report-compiler.md** переписывается на русском — инструкции, правила, примеры. Технические термины (MTD, SPP, DRR, ROMI) остаются латиницей.

**Trust Envelope Rendering** — тоже на русском (уже частично на русском, довести до 100%).

---

## Часть 5: Watchdog fix (уже сделано)

Исправлено в текущей сессии:
- `_check_last_run` — убран `ImportError` (несуществующий `get_last_run_status`), заменён прямым запросом к `orchestrator_runs`
- `_check_db` — обёрнут в `asyncio.to_thread` (не блокирует event loop)

---

## Файлы для изменения (сводка)

| Файл | Изменение |
|------|-----------|
| `agents/v3/delivery/messages.py` | **НОВЫЙ** — централизованные шаблоны сообщений |
| `agents/v3/agents/report-compiler.md` | Перевод на русский (секции, инструкции) |
| `agents/v3/orchestrator.py` | Fix None.get() на строке 335 |
| `agents/v3/delivery/router.py` | Defensive `or {}` на строке 59 |
| `agents/v3/conductor/conductor.py` | Дедупликация уведомлений, использование messages.py |
| `agents/v3/conductor/state.py` | Добавить `already_notified()` / `mark_notified()` |
| `agents/v3/conductor/messages.py` | Удалить (заменяется delivery/messages.py) |
| `agents/v3/scheduler.py` | Все `_send_admin(f"...")` → messages.xxx() |
| `agents/v3/monitor.py` | Watchdog/anomaly → messages.xxx() (+ уже fix check_db/last_run) |

## Не затрагивается

- Oleg v2 pipeline (`agents/oleg/`) — не трогаем, отдельная система
- `delivery/telegram.py` — формат отчёта для TG уже ок (confidence footer и т.д.)
- `delivery/notion.py` — работает корректно, язык определяется содержимым detailed_report
