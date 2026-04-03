# Phase 4: Запуск и доставка - Research

**Researched:** 2026-03-31
**Domain:** Python cron scheduling, Docker entrypoint, lock-file idioms, asyncio runner
**Confidence:** HIGH — all findings based on direct inspection of existing codebase

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Runner-скрипт**
- D-01: Один новый скрипт `scripts/run_report.py` с двумя режимами: `--type daily|weekly|...` (ручной) и `--schedule` (авто: определяет типы по дню, запускает последовательно через pipeline)
- D-02: Runner инициализирует все клиенты (LLM, Notion, Alerter, GateChecker) и вызывает `report_pipeline.run_report()` для каждого типа
- D-03: Старые `run_oleg_v2_reports.py` и `run_oleg_v2_single.py` удаляются
- D-04: Inline delivery (генерация → Notion → Telegram) уже реализован в report_pipeline — runner просто вызывает pipeline

**Cron + polling**
- D-05: Cron запускает `run_report.py --schedule` каждые 30 минут в окне 07:00–18:00 МСК
- D-06: Lock-файл предотвращает повтор уже опубликованных отчётов за день
- D-07: Уведомление-заглушка в Telegram: в 09:00 если данных нет ("Данные пока не готовы, отслеживаем"), далее каждые 2 часа (11:00, 13:00, 15:00, 17:00)
- D-08: Если к 18:00 данных нет — финальное уведомление "Данные не появились за день"
- D-09: После готовности данных — отчёты запускаются последовательно: финансовый → маркетинговый → воронка → логистика/локализация → ДДС (последний)
- D-10: Какие типы запускаются зависит от дня: daily каждый день, weekly в понедельник, monthly в понедельник 1–7 числа

**Docker интеграция**
- D-11: Cron добавляется внутрь контейнера wookiee-oleg (entrypoint: install cron + crontab + cron -f)
- D-12: finolog-cron контейнер полностью удаляется из docker-compose.yml
- D-13: run_finolog_weekly.py удаляется

**Telegram-уведомления**
- D-14: Формат: краткая сводка (название типа + 3–5 ключевых метрик + ссылка на Notion)
- D-15: Каждый отчёт — отдельное сообщение в Telegram
- D-16: Только уведомления, без бота с командами

**Русские названия типов**
- D-17: Русские названия уже реализованы в `report_types.py` через `display_name_ru` — SCHED-04 уже выполнен

### Claude's Discretion
- Конкретная реализация crontab-файла (интервалы, формат строк)
- Формат и детали уведомлений-заглушек
- Структура runner-скрипта (классы, функции, error handling)
- Как извлекать ключевые метрики для краткой сводки в Telegram
- Реализация lock-файла для предотвращения повторных запусков
- Порядок и логика retry при неудачной публикации в Notion

### Deferred Ideas (OUT OF SCOPE)
- Алерты при резких изменениях метрик — v3.0 (ALERT-01)
- Telegram бот с командами — v3.0 (BOT-01)
- Watchdog мониторинг — v3.0 (ALERT-02)
- БД для workflow логов (retry, ошибки, время генерации) — отдельная задача
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCHED-01 | Простые cron-задачи для запуска всех 8 типов отчётов | D-05/D-10/D-11: crontab в Docker-контейнере wookiee-oleg, паттерн из finolog-cron уже известен |
| SCHED-02 | Отчёт публикуется в Notion с правильными properties (период, тип, статус) | Полностью реализовано в Phase 3 через `NotionClient.sync_report()` — runner просто вызывает pipeline |
| SCHED-03 | Telegram-уведомление отправляется после публикации (без бота) | Полностью реализовано в Phase 3 через `Alerter.send_alert()` — runner управляет только заглушками |
| SCHED-04 | Русские названия типов отчётов в Notion и Telegram | Уже реализовано в `REPORT_CONFIGS[type].display_name_ru` — Phase 4 не требует изменений |
</phase_requirements>

---

## Summary

Phase 4 — самая операционная из всех: Pipeline полностью реализован в Phase 3, и задача Phase 4 — обернуть его в runner-скрипт, добавить cron-расписание внутрь Docker-контейнера, и реализовать polling-логику с уведомлениями-заглушками.

Ключевое открытие: SCHED-02, SCHED-03 и SCHED-04 уже выполнены в Phase 3. `report_pipeline.run_report()` публикует в Notion с полными properties, отправляет Telegram-уведомление с Notion-ссылкой, и использует `display_name_ru` для русских названий. Phase 4 добавляет исключительно infrastructure-уровень: runner + cron + lock-файл + удаление мёртвого кода.

Паттерн Docker-cron уже существует в codebase: отключённый `finolog-cron` контейнер использует `apt-get install cron && echo "..." | crontab - && cron -f`. Тот же паттерн применяется в wookiee-oleg с изменением entrypoint.

**Первичная рекомендация:** Разбить на 2 плана: (1) runner-скрипт + lock-файл + polling-логика, (2) Docker entrypoint + crontab + удаление мёртвого кода. Оба плана малые по объёму.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib: `asyncio` | built-in | Async event loop для runner | Весь pipeline async |
| Python stdlib: `argparse` | built-in | CLI-аргументы `--type`, `--schedule` | Стандарт для скриптов |
| Python stdlib: `pathlib`, `os` | built-in | Lock-файлы, пути | Стандарт проекта |
| Python stdlib: `datetime` | built-in | Определение дня недели, окна polling | Логика расписания |
| `aiogram==3.15.0` | 3.15.0 | Telegram уведомления (уже используется) | В agents/oleg/requirements.txt |

### Не требуют установки

Всё что нужно — уже в проекте:
- `report_pipeline.run_report()` — Phase 3
- `ReportType`, `REPORT_CONFIGS` — Phase 3
- `GateChecker` — Phase 3
- `Alerter.send_alert()` — существующий
- `NotionClient.sync_report()` — существующий
- `OpenRouterClient`, `OlegOrchestrator` — существующие

**Installation:** Никаких новых зависимостей. Все библиотеки уже в `agents/oleg/requirements.txt`.

---

## Architecture Patterns

### Recommended Project Structure

```
scripts/
└── run_report.py              # NEW — главный runner (заменяет run_oleg_v2_*.py)

agents/oleg/
└── pipeline/
    └── report_types.py        # EXISTING — ReportType, REPORT_CONFIGS, display_name_ru

deploy/
├── docker-compose.yml         # MODIFY — удалить finolog-cron, изменить entrypoint wookiee-oleg
├── Dockerfile                 # MODIFY — убрать agents/v3 refs, добавить cron в apt-get install
└── crontab                    # NEW (optional) — crontab-файл для COPY в Dockerfile

/tmp/ или /app/locks/          # Runtime lock-файлы
```

### Pattern 1: Runner Script Structure

**What:** Единый скрипт `scripts/run_report.py` с двумя режимами
**When to use:** Всегда — ручной запуск и cron используют один и тот же скрипт

```python
# Source: инспекция scripts/run_oleg_v2_reports.py (паттерн инициализации)
import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

async def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--type", choices=[t.value for t in ReportType])
    group.add_argument("--schedule", action="store_true")
    args = parser.parse_args()

    # Инициализация клиентов (паттерн из run_oleg_v2_reports.py)
    llm = OpenRouterClient(api_key=OPENROUTER_API_KEY, model=MODEL_MAIN)
    notion = NotionClient(token=NOTION_TOKEN, database_id=NOTION_DATABASE_ID)
    # bot = Bot(token=TELEGRAM_BOT_TOKEN) — для Alerter
    alerter = Alerter(bot=bot, admin_chat_id=int(ADMIN_CHAT_ID))
    gate_checker = GateChecker()
    orchestrator = _build_orchestrator(llm)

    if args.type:
        await run_single(ReportType(args.type), ...)
    else:
        await run_schedule(...)

if __name__ == "__main__":
    asyncio.run(main())
```

### Pattern 2: Schedule Logic (какие типы запускать по дню)

**What:** Определение типов отчётов на основе дня недели и числа месяца
**When to use:** В `--schedule` режиме

```python
# Source: логика из D-10 (CONTEXT.md)
from datetime import date
from agents.oleg.pipeline.report_types import ReportType, REPORT_CONFIGS

REPORT_ORDER = [
    ReportType.DAILY,
    ReportType.WEEKLY,
    ReportType.MONTHLY,
    ReportType.MARKETING_WEEKLY,
    ReportType.MARKETING_MONTHLY,
    ReportType.FUNNEL_WEEKLY,
    ReportType.LOCALIZATION_WEEKLY,
    ReportType.FINOLOG_WEEKLY,  # всегда последний (D-09)
]

def get_types_for_today(today: date = None) -> list[ReportType]:
    """D-10: daily каждый день, weekly в понедельник (weekday==0),
    monthly в понедельник 1-7 числа."""
    if today is None:
        today = date.today()

    types = []
    for rt in REPORT_ORDER:
        config = REPORT_CONFIGS[rt]
        if config.period == "daily":
            types.append(rt)
        elif config.period == "weekly" and today.weekday() == 0:
            types.append(rt)
        elif config.period == "monthly" and today.weekday() == 0 and 1 <= today.day <= 7:
            types.append(rt)
    return types
```

### Pattern 3: Lock-файл per report_type per date

**What:** Файл `/app/locks/{report_type}_{date}.lock` как сигнал "уже опубликован"
**When to use:** Перед каждым запуском отчёта в `--schedule` режиме

```python
# Source: стандартный Unix-паттерн lock-файлов
import os
from pathlib import Path

LOCKS_DIR = Path("/app/locks")

def is_locked(report_type: str, target_date: date) -> bool:
    lock_path = LOCKS_DIR / f"{report_type}_{target_date.isoformat()}.lock"
    return lock_path.exists()

def acquire_lock(report_type: str, target_date: date) -> None:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCKS_DIR / f"{report_type}_{target_date.isoformat()}.lock"
    lock_path.touch()
```

**Питфол lock-файлов в Docker:** `/app/locks/` должен быть смонтирован как volume или создан при старте — при пересборке образа lock-файлы теряются. Это **желаемое поведение** (новый день = нет lock-файлов = свежий старт). Но если контейнер перезапускается внутри одного дня — файлы в `/app/locks/` внутри контейнера сохраняются (если volume не используется).

### Pattern 4: Docker Cron Entrypoint

**What:** Запуск cron внутри контейнера wookiee-oleg
**When to use:** Entrypoint в docker-compose.yml

```yaml
# Source: инспекция finolog-cron в deploy/docker-compose.yml
entrypoint: ["/bin/bash", "-c"]
command:
  - |
    apt-get update -qq && apt-get install -y -qq cron > /dev/null 2>&1
    # Установка crontab — каждые 30 минут с 07:00 до 18:00 МСК
    (
      echo "*/30 7-17 * * * cd /app && python scripts/run_report.py --schedule >> /proc/1/fd/1 2>&1"
      # Заглушка в 09:00 каждый день (если данных нет — pipeline сам пошлёт уведомление)
    ) | crontab -
    echo "Cron installed for wookiee-oleg"
    cron -f
```

**Важно:** `TZ=Europe/Moscow` уже установлен в environment wookiee-oleg — cron будет работать в МСК.

### Pattern 5: Polling/заглушки

**What:** Уведомления о статусе данных в часы ожидания (D-07/D-08)
**When to use:** В `--schedule` режиме перед запуском отчётов

Логика:
1. Runner проверяет gates через pipeline (в `--schedule` режиме)
2. Если данные не готовы — посылает заглушку через Alerter, если это "плановое" время (09:00, 11:00, 13:00, 15:00, 17:00)
3. В 17:30 (последний запуск в окне) — если ни один отчёт не был опубликован сегодня — финальное сообщение

```python
# Определение "плановых" времён для заглушек
from datetime import datetime

STUB_HOURS = {9, 11, 13, 15, 17}

def should_send_stub(now: datetime = None) -> bool:
    if now is None:
        now = datetime.now()
    return now.hour in STUB_HOURS and now.minute < 35  # попали в 30-минутное окно
```

### Anti-Patterns to Avoid

- **Не создавать новый orchestrator в каждом вызове run_report:** orchestrator дорогостоящий (инициализирует агентов) — создать один раз, передавать в pipeline для всех типов.
- **Не вызывать GateChecker.check_all() напрямую в runner:** pipeline сам вызывает gate_checker — передать экземпляр, не дублировать логику.
- **Не хардкодить пути к lock-файлам:** использовать константу или конфиг, чтобы в тестах можно было переопределить.
- **Не удалять lock-файлы при ошибке:** если pipeline вернул `failed=True` — lock НЕ выставляется (отчёт не был успешно опубликован, разрешаем повторный запуск).
- **Не игнорировать `skipped=True` результат:** pipeline вернул `skipped` (данные не готовы) ≠ успех, lock не выставлять.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Публикация в Notion с properties | Свою Notion-интеграцию | `NotionClient.sync_report()` | Уже реализован upsert, dedup, properties |
| Telegram-уведомление | Прямые HTTP-запросы к Bot API | `Alerter.send_alert()` | Dedup (5 мин), multi-recipient, aiogram |
| Pre-flight проверка данных | Свои SQL-запросы freshness | `GateChecker.check_all()` | 3 hard + 3 soft gates, готовый structured result |
| Весь pipeline | Свою логику retry/validation | `report_pipeline.run_report()` | Полный reliability flow Phase 3 |
| Инициализация агентов | Собственный wiring | Паттерн из `run_oleg_v2_reports.py` | Правильный порядок, task_type-specific agents |
| Русские названия | Свой dict маппинг | `REPORT_CONFIGS[rt].display_name_ru` | Уже определены для всех 8 типов |

**Key insight:** Phase 4 — почти чистая infrastructure-задача. Вся бизнес-логика (генерация, валидация, доставка) уже в pipeline. Runner — тонкий слой оркестрации.

---

## Common Pitfalls

### Pitfall 1: Dockerfile ссылается на удалённый agents/v3/
**What goes wrong:** Текущий `deploy/Dockerfile` содержит `COPY agents/v3/requirements.txt` и `RUN pip install -r agents/v3/requirements.txt`, а также `RUN mkdir -p /app/agents/v3/data` и `CMD ["python", "-m", "agents.v3"]`. V3 удалён в Phase 1 — Docker build упадёт.
**Why it happens:** Dockerfile не обновлялся при удалении V3 (Phase 1 делала только удаление файлов, не трогала Dockerfile).
**How to avoid:** В плане Phase 4 — явный таск "Update Dockerfile: remove v3 references, update CMD to cron entrypoint".
**Warning signs:** `docker build` завершается с `COPY failed: file not found`.

### Pitfall 2: Cron не пишет stdout/stderr в Docker logs
**What goes wrong:** Вывод скрипта пропадает — ни ошибок, ни логов в `docker logs wookiee_oleg`.
**Why it happens:** Cron запускает процессы без tty, stdout/stderr перенаправляется в /dev/null по умолчанию.
**How to avoid:** Явное перенаправление в crontab: `>> /proc/1/fd/1 2>&1` (пишет в PID 1 stdout = Docker logs). Паттерн уже используется в finolog-cron.
**Warning signs:** Cron установлен (`crontab -l` показывает задачи), но `docker logs` пуст.

### Pitfall 3: Timezone в cron vs. TZ env var
**What goes wrong:** Cron запускается по UTC, несмотря на `TZ=Europe/Moscow` в docker-compose.
**Why it happens:** Некоторые версии cron читают системный timezone, а не переменную окружения.
**How to avoid:** `TZ=Europe/Moscow` уже установлен в environment wookiee-oleg. Для надёжности — проверить что cron видит MSK при первом запуске (через `date` в cron-задаче). Альтернатива: прописать UCT+3 часы в crontab (07:00 MSK = 04:00 UTC).
**Warning signs:** Отчёты генерируются в 04:00, 05:00 по факту вместо 07:00.

### Pitfall 4: Lock-файл не создаётся при skipped pipeline
**What goes wrong:** При каждом cron-запуске pipeline запускается заново для типов с `skipped=True` (данные не готовы). Это ожидаемо — но если данные готовятся медленно, можно получить множество Telegram-уведомлений о pre-flight failures.
**Why it happens:** `skipped` означает "данных нет, подождём" — это нормально.
**How to avoid:** Lock выставлять только при `success=True`. При `skipped` — не lock, не ошибка. Уведомления-заглушки отправлять только в плановые часы (D-07), а не каждые 30 минут.
**Warning signs:** Telegram завален сообщениями "данные не готовы" каждые 30 минут.

### Pitfall 5: Неправильная инициализация aiogram Bot для Alerter
**What goes wrong:** `Alerter.send_alert()` падает с "bot is None" или "no recipients".
**Why it happens:** `Alerter.__init__` принимает `bot` (aiogram Bot instance) и `admin_chat_id`. В runner нужно создать `Bot(token=TELEGRAM_BOT_TOKEN)` и передать в Alerter. `TELEGRAM_BOT_TOKEN` и `ADMIN_CHAT_ID` не экспортируются из `shared/config.py` — берутся напрямую из `os.getenv()`.
**How to avoid:** В runner явно читать `TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")` и `ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))`. Проверить non-empty перед созданием Bot.
**Warning signs:** `Alert not sent (no bot/recipients)` в логах.

### Pitfall 6: orchestrator создаётся один раз для всех типов
**What goes wrong:** ReporterAgent и MarketerAgent должны быть созданы с правильным `task_type` для каждого типа отчёта. При повторном использовании одного orchestrator — загружается неправильный playbook.
**Why it happens:** `run_oleg_v2_reports.py` создаёт отдельный `reporter = ReporterAgent(..., task_type=task_type)` для каждого chain. Это не очевидно при первом взгляде.
**How to avoid:** В runner создавать orchestrator (с правильными task_type-specific агентами) для каждого типа отчёта. LLM-клиент и Notion/Alerter — shared (создаются один раз).
**Warning signs:** Все отчёты генерируются по шаблону `daily`, независимо от типа.

---

## Code Examples

### Инициализация клиентов (проверенный паттерн)

```python
# Source: scripts/run_oleg_v2_reports.py (lines 72-104)
from shared.config import OPENROUTER_API_KEY, MODEL_MAIN, PRICING, NOTION_TOKEN, NOTION_DATABASE_ID
from shared.clients.openrouter_client import OpenRouterClient
from shared.notion_client import NotionClient
from agents.oleg.orchestrator.orchestrator import OlegOrchestrator
from agents.oleg.agents.reporter.agent import ReporterAgent
from agents.oleg.agents.marketer.agent import MarketerAgent
from agents.oleg.agents.funnel.agent import FunnelAgent
from agents.oleg.agents.advisor.agent import AdvisorAgent
from agents.oleg.agents.validator.agent import ValidatorAgent
from agents.oleg.pipeline.gate_checker import GateChecker
from agents.oleg.watchdog.alerter import Alerter
from aiogram import Bot

# Shared (once)
llm = OpenRouterClient(api_key=OPENROUTER_API_KEY, model=MODEL_MAIN)
notion = NotionClient(token=NOTION_TOKEN, database_id=NOTION_DATABASE_ID)
gate_checker = GateChecker()
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
alerter = Alerter(bot=bot, admin_chat_id=int(os.getenv("ADMIN_CHAT_ID", "0")))

# Per report_type (task_type-specific agents)
def build_orchestrator(task_type: str) -> OlegOrchestrator:
    reporter = ReporterAgent(llm, MODEL_MAIN, pricing=PRICING, task_type=task_type)
    marketer = MarketerAgent(llm, MODEL_MAIN, pricing=PRICING, task_type=task_type)
    funnel = FunnelAgent(llm, MODEL_MAIN, pricing=PRICING)
    advisor = AdvisorAgent(llm, MODEL_MAIN, pricing=PRICING)
    validator = ValidatorAgent(llm, MODEL_MAIN, pricing=PRICING)
    return OlegOrchestrator(
        llm_client=llm,
        model=MODEL_MAIN,
        agents={"reporter": reporter, "marketer": marketer,
                "funnel": funnel, "advisor": advisor, "validator": validator},
        pricing=PRICING,
    )
```

### Вызов pipeline (полный flow)

```python
# Source: agents/oleg/pipeline/report_pipeline.py (run_report signature)
from agents.oleg.pipeline.report_pipeline import run_report, ReportPipelineResult
from agents.oleg.pipeline.report_types import ReportType
from datetime import date

async def run_single_report(
    report_type: ReportType,
    target_date: date,
    notion, alerter, gate_checker,
) -> ReportPipelineResult:
    orchestrator = build_orchestrator(report_type.value)

    # Вычислить date_from / date_to по типу периода
    config = REPORT_CONFIGS[report_type]
    date_from, date_to = compute_date_range(config.period, target_date)

    result = await run_report(
        report_type=report_type,
        target_date=target_date,
        orchestrator=orchestrator,
        notion_client=notion,
        alerter=alerter,
        gate_checker=gate_checker,
        date_from=date_from,
        date_to=date_to,
    )
    return result
```

### Crontab для Docker (МСК-ориентированный)

```bash
# Source: deploy/docker-compose.yml finolog-cron pattern (line 48)
# TZ=Europe/Moscow установлен в environment — cron работает в МСК

# Каждые 30 минут в окне 07:00-17:30 МСК (включительно)
*/30 7-17 * * * cd /app && python scripts/run_report.py --schedule >> /proc/1/fd/1 2>&1
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `run_oleg_v2_reports.py` (hard-coded weekly chains) | `run_report.py --schedule` (все 8 типов, data-driven) | Phase 4 | Единый runner для всех типов и режимов |
| `finolog-cron` отдельный контейнер | Cron внутри `wookiee-oleg` | Phase 4 | Один контейнер, меньше координации |
| APScheduler (Python) | Системный cron | Pre-planning | Проще, надёжнее, без Python-зависимости |
| Telegram бот с командами | Только уведомления | Pre-planning | Меньше поверхности, проще деплой |

**Deprecated/outdated:**
- `scripts/run_oleg_v2_reports.py` — заменяется `scripts/run_report.py`
- `scripts/run_oleg_v2_single.py` — заменяется `run_report.py --type`
- `scripts/run_finolog_weekly.py` — broken V3 import, заменяется pipeline
- `deploy/docker-compose.yml finolog-cron service` — удаляется
- `deploy/Dockerfile` ссылки на `agents/v3/` — удаляются

---

## Open Questions

1. **Date range для monthly отчётов**
   - What we know: `run_report()` принимает `date_from` и `date_to`; для monthly это весь предыдущий месяц
   - What's unclear: Точная логика `compute_date_range` для `monthly` — первый день предыдущего месяца до последнего?
   - Recommendation: В runner реализовать `compute_date_range(period, target_date)` — для daily: target_date..target_date, для weekly: прошлый пн..прошлое вс, для monthly: 1-е прошлого месяца..последний день прошлого месяца

2. **Volumes для lock-файлов**
   - What we know: Lock-файлы в `/app/locks/` внутри контейнера; при пересборке теряются
   - What's unclear: Нужен ли volume для `/app/locks/` в docker-compose чтобы lock-файлы переживали `docker restart`?
   - Recommendation: Не добавлять volume — при `docker restart` в тот же день cron-запуски начнут заново, что безопасно (pipeline idempotent через Notion upsert). Если будет rerun — Notion просто обновит существующую страницу.

3. **Как определить "финальное" уведомление в 18:00**
   - What we know: D-08 говорит "если к 18:00 данных нет — финальное уведомление"
   - What's unclear: Cron не знает что это "последний" запуск за день
   - Recommendation: В runner проверять `current_hour >= 17 and not any_lock_today()` — если ни один отчёт не был опубликован сегодня и время ≥ 17:30, отправить финальное уведомление.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Runner script | ✓ | 3.11 (Dockerfile base image) | — |
| cron (system) | Docker entrypoint | ✗ (не в base image) | — | `apt-get install cron` в entrypoint (паттерн из finolog-cron) |
| aiogram | Alerter.send_alert() | ✓ | 3.15.0 (в requirements.txt) | — |
| TELEGRAM_BOT_TOKEN | Alerter | ✓ | — (в .env) | — |
| ADMIN_CHAT_ID | Alerter | ✓ | — (в .env) | — |
| NOTION_TOKEN / NOTION_DATABASE_ID | NotionClient | ✓ | — (в .env) | — |
| OPENROUTER_API_KEY | LLM calls | ✓ | — (в .env) | — |

**Missing dependencies with no fallback:** Нет.

**Missing dependencies with fallback:**
- `cron` не в python:3.11-slim — устанавливается через `apt-get install cron` в entrypoint (готовый паттерн).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (pyproject.toml: asyncio_mode = "auto") |
| Config file | `/Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/pyproject.toml` |
| Quick run command | `pytest tests/agents/oleg/ -x -q` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCHED-01 | `get_types_for_today()` возвращает правильные типы по дню | unit | `pytest tests/agents/oleg/runner/ -x -q` | ❌ Wave 0 |
| SCHED-01 | Lock-файл предотвращает повторный запуск | unit | `pytest tests/agents/oleg/runner/ -x -q` | ❌ Wave 0 |
| SCHED-02 | Notion properties корректны | integration (covered Phase 3) | `pytest tests/agents/oleg/pipeline/ -x -q` | ✅ |
| SCHED-03 | Telegram после Notion (covered Phase 3) | integration (covered Phase 3) | `pytest tests/agents/oleg/pipeline/ -x -q` | ✅ |
| SCHED-04 | display_name_ru присутствует для всех 8 типов | unit | `pytest tests/agents/oleg/runner/ -x -q` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/agents/oleg/ -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/agents/oleg/runner/__init__.py` — пустой init
- [ ] `tests/agents/oleg/runner/test_schedule_logic.py` — покрывает SCHED-01: `get_types_for_today()`, lock-файлы, date range computation

*(SCHED-02, SCHED-03, SCHED-04 покрыты существующими тестами pipeline из Phase 3)*

---

## Project Constraints (from CLAUDE.md)

Директивы из `CLAUDE.md` и `.claude/rules/`, применимые к Phase 4:

| Директива | Источник | Применимость |
|-----------|----------|-------------|
| DB-запросы только через `shared/data_layer.py` | CLAUDE.md + data-quality.md | Runner не делает DB-запросов напрямую — всё через pipeline/gate_checker ✓ |
| Конфигурация только через `shared/config.py` | CLAUDE.md + infrastructure.md | Runner импортирует из `shared.config`; `TELEGRAM_BOT_TOKEN` / `ADMIN_CHAT_ID` не в shared/config — читать через `os.getenv()` напрямую |
| Секреты только в `.env`, никогда хардкодить | infrastructure.md | Все токены из `.env` ✓ |
| Деплой только на App Server (77.233.212.61, `ssh timeweb`) | infrastructure.md | docker-compose изменения деплоятся через ssh timeweb |
| DB Server (89.23.119.253) — только чтение | infrastructure.md | GateChecker использует read-only запросы ✓ |
| LLM: единый провайдер OpenRouter | economics.md | `OpenRouterClient` используется ✓ |
| MAIN модель для аналитики | economics.md | `MODEL_MAIN` (z-ai/glm-4.7) передаётся в orchestrator ✓ |
| Supabase: RLS включён | infrastructure.md | Phase 4 не затрагивает Supabase |

**Специфичное для Phase 4:** `TELEGRAM_BOT_TOKEN` и `ADMIN_CHAT_ID` не экспортируются из `shared/config.py` (проверено). В runner читать через `os.getenv()` с явной проверкой на пустоту.

---

## Sources

### Primary (HIGH confidence)
- Прямая инспекция `agents/oleg/pipeline/report_pipeline.py` — интерфейс `run_report()`, ReportPipelineResult
- Прямая инспекция `agents/oleg/pipeline/report_types.py` — все 8 типов, display_name_ru, period
- Прямая инспекция `agents/oleg/pipeline/gate_checker.py` — GateChecker.check_all() интерфейс
- Прямая инспекция `agents/oleg/watchdog/alerter.py` — Alerter.send_alert() интерфейс
- Прямая инспекция `deploy/docker-compose.yml` — finolog-cron cron-паттерн, wookiee-oleg config
- Прямая инспекция `deploy/Dockerfile` — stale v3 references
- Прямая инспекция `scripts/run_oleg_v2_reports.py` — паттерн инициализации клиентов
- Прямая инспекция `.env.example` — TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
- Прямая инспекция `shared/config.py` — подтверждено отсутствие TELEGRAM_BOT_TOKEN

### Secondary (MEDIUM confidence)
- Анализ `pyproject.toml` — pytest asyncio_mode=auto, testpaths
- Анализ структуры `tests/agents/oleg/` — существующее тестовое покрытие

### Tertiary (LOW confidence)
- Нет LOW-confidence находок

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — прямая инспекция requirements.txt и существующих файлов
- Architecture: HIGH — паттерны верифицированы по существующему коду (finolog-cron, run_oleg_v2_reports.py)
- Pitfalls: HIGH — Dockerfile stale refs подтверждены инспекцией; остальные — хорошо известные Unix/Docker паттерны

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (стабильная кодовая база, зависимости не меняются)
