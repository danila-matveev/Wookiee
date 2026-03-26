# Этап 1: Чистка и консолидация единой системы отчётности

**Дата:** 2026-03-26
**Контекст:** Спецификация [2026-03-26-unified-reporting-system.md](./2026-03-26-unified-reporting-system.md)
**Цель:** Убрать мёртвый код, устранить дублирование, обеспечить чистый запуск `python -m agents.v3` как единой точки входа.

---

## Предпосылки

Система Wookiee имеет две папки:
- `agents/v3/` — обёртка (scheduler, conductor, delivery, Telegram bot)
- `agents/oleg/` — движок генерации (OlegOrchestrator, ReAct loop, агенты с промптами, SQL tools)

V3 вызывает V2 движок через bridge (`_run_v2_engine()`). Отчёты генерируются V2 промптами и агентами. V3 отвечает за расписание, проверку данных (gates) и доставку (Notion + Telegram).

**Проблема:** мёртвый код, дублирование файлов, два NotionService, два config.py, неработающий V2 контейнер на сервере конфликтует с V3 Telegram ботом.

---

## Секция 1: Удаление мёртвого кода

### Файлы к удалению

| Файл / директория | Причина удаления |
|---|---|
| `scripts/manual_report.py` | Заменён `scripts/test_v2_bridge.py`. Пользователь подтвердил — не нужен |
| `scripts/rebuild_reports.py` | Не используется. Пользователь подтвердил — не нужен |
| `agents/oleg/bot/` (вся папка) | V2 Telegram бот. Заменён V3 `app.py` хендлерами. После удаления `manual_report.py` нет внешних импортёров |
| `agents/oleg/pipeline/` (вся папка) | V2 gate checker + report pipeline. Заменён `agents/v3/gates.py` + `conductor/`. После удаления скриптов нет внешних импортёров |
| `agents/oleg/check_scheduler.py` | V2 утилита диагностики. Не нужна |
| `agents/oleg/mcp_server.py` | V2 MCP сервер. Не запущен, не используется |
| `agents/oleg/app.py` | Уже удалён (коммит ef79ba5) |
| `agents/oleg/__main__.py` | Уже удалён (коммит ef79ba5) |

### Промпты к удалению (агенты, которые не вызываются при `max_chain_steps=1`)

| Файл | Причина |
|---|---|
| `agents/oleg/agents/researcher/` (вся папка) | Не вызывается. Researcher вызывался только при chain_steps > 1 |
| `agents/oleg/agents/quality/` (вся папка) | Не вызывается. Quality agent не в цепочке |
| `agents/oleg/agents/christina/` (вся папка) | Не вызывается. KB management agent не в цепочке |
| `agents/oleg/agents/seo/` (вся папка) | Не вызывается. Funnel agent отключён (в `_DISABLED_TYPES`) |
| `agents/oleg/christina_playbook.md` | Playbook для удалённого агента |
| `agents/oleg/seo_playbook.md` | Playbook для удалённого SEO/funnel агента (если существует) |

### Тесты к удалению (тесты удалённого кода)

| Файл | Причина |
|---|---|
| `tests/oleg/test_formatter.py` | Тестирует `oleg/bot/formatter.py` (удаляется) |
| `tests/oleg/test_gate_checker.py` | Тестирует `oleg/pipeline/gate_checker.py` (удаляется) |
| `tests/oleg/test_report_pipeline.py` | Тестирует `oleg/pipeline/report_pipeline.py` (удаляется) |

---

## Секция 2: Консолидация NotionService

### Текущее состояние

Два дубля:
- `agents/oleg/services/notion_service.py` (V2) — используется `finolog_categorizer`
- `agents/v3/delivery/notion.py` (V3) — используется V3 delivery router

### Решение

Создать `shared/notion_client.py` — единый NotionClient, объединяющий лучшее из обоих:

**Из V3 берём:**
- Per-report-type concurrency locks (предотвращает race conditions)
- Полный report type map (29 записей)
- Структуру класса

**Из V2 берём:**
- Публичный `get_comments(page_id)` (нужен `finolog_categorizer/feedback_reader.py`)

**API:**
```python
class NotionClient:
    def __init__(self, token: str, database_id: str):
        ...

    async def sync_report(
        self, start_date, end_date, report_md, *,
        report_type="daily", source="Oleg v3 (auto)", chain_steps=1,
    ) -> Optional[str]:
        ...

    async def get_recent_feedback(self, days=7) -> list[dict]:
        ...

    async def get_comments(self, page_id: str) -> list[dict]:  # публичный
        ...

    async def add_comment(self, page_id: str, text: str) -> None:
        ...
```

### Миграция импортов

| Файл | Было | Станет |
|---|---|---|
| `agents/v3/delivery/router.py` | `from agents.v3.delivery.notion import NotionDelivery` | `from shared.notion_client import NotionClient` |
| `agents/v3/delivery/__init__.py` | `from .notion import NotionDelivery` | `from shared.notion_client import NotionClient as NotionDelivery` |
| `agents/v3/prompt_tuner.py` | `from agents.v3.delivery.notion import NotionDelivery` | `from shared.notion_client import NotionClient` |
| `agents/finolog_categorizer/app.py` | `from agents.oleg.services.notion_service import NotionService` | `from shared.notion_client import NotionClient` |
| `agents/finolog_categorizer/notion_publisher.py` | `from agents.oleg.services.notion_service import NotionService` | `from shared.notion_client import NotionClient` |
| `agents/finolog_categorizer/feedback_reader.py` | `from agents.oleg.services.notion_service import NotionService` | `from shared.notion_client import NotionClient` |
| `scripts/run_price_analysis.py` | `from agents.v3.delivery.notion import NotionDelivery as NotionService` | `from shared.notion_client import NotionClient` |

### Удаление старых файлов

- `agents/oleg/services/notion_service.py` — удалить
- `agents/v3/delivery/notion.py` — удалить

---

## Секция 3: Серверная чистка

| Действие | Зачем |
|---|---|
| Остановить контейнер `wookiee_oleg` на сервере | Убрать `TelegramConflictError` — два процесса используют один Telegram токен |
| Пересобрать/обновить контейнер как `wookiee_v3` | Единый процесс: `python -m agents.v3` |
| Проверить что только один процесс использует Telegram токен | Нет конфликтов при polling |

**Примечание:** это серверная операция, выполняется пользователем или через SSH.

---

## Секция 4: Миграция finolog_categorizer

Переключить `agents/finolog_categorizer/` на новый `shared/notion_client.py`.

| Файл | Изменение |
|---|---|
| `agents/finolog_categorizer/app.py` | Import: `NotionService` → `NotionClient` |
| `agents/finolog_categorizer/notion_publisher.py` | Import: `NotionService` → `NotionClient`. Метод `sync_report()` — API совместим |
| `agents/finolog_categorizer/feedback_reader.py` | Import + метод `get_comments()` — публичный в новом клиенте, API совместим |
| `agents/finolog_categorizer/scanner.py` | Проверить импорты, обновить если нужно |

---

## Секция 5: Удаление oleg/config.py

### Предпосылки

После удаления `manual_report.py`, `rebuild_reports.py`, `mcp_server.py`, `check_scheduler.py`, `bot/` — остаются 2 файла, импортирующих `agents/oleg/config.py`:
- `agents/oleg/services/price_tools.py`
- `agents/oleg/agents/researcher/tools.py` (удаляется в Секции 1)

### Решение

1. `price_tools.py`: заменить `from agents.oleg import config` → `from agents.v3 import config`
2. Проверить что все нужные переменные есть в `agents/v3/config.py` (OPENROUTER_API_KEY, модели, DB credentials — все уже там)
3. Удалить `agents/oleg/config.py`

---

## Секция 6: Верификация

После всей чистки выполнить:

```bash
# 1. Import check — ничего не сломалось
python -c "
from agents.v3 import orchestrator, config, scheduler
from agents.v3.delivery.router import deliver
from agents.v3.conductor.conductor import ConductorOrchestrator
from shared.notion_client import NotionClient
from agents.oleg.orchestrator.orchestrator import OlegOrchestrator
from agents.oleg.services.agent_tools import TOOL_DEFINITIONS
from agents.finolog_categorizer.app import main as finolog_main
print('=== ALL IMPORTS OK ===')
"

# 2. Dry run — все jobs видны
python -m agents.v3 --dry-run

# 3. Тестовый отчёт
python -m scripts.test_v2_bridge --deliver daily 2026-03-25
```

**Критерии успеха:**
- [ ] Все imports без ошибок
- [ ] `--dry-run` показывает 10+ jobs
- [ ] Daily отчёт: STATUS != failed, LENGTH > 5000 chars
- [ ] Notion: страница создана, toggles работают
- [ ] Telegram: сообщение доставлено

---

## Секция 7: Сохранение промптов

### НЕ ТРОГАЕМ (ядро генерации — V2 промпты лучше V3)

| Файл | Зачем |
|---|---|
| `agents/oleg/agents/reporter/prompts.py` | Промпт финансового аналитика (~190 строк) |
| `agents/oleg/playbook.md` | Playbook финансового анализа (119 КБ) |
| `agents/oleg/agents/marketer/prompts.py` | Промпт маркетолога (~160 строк) |
| `agents/oleg/marketing_playbook.md` | Playbook маркетингового анализа (18 КБ) |
| `agents/oleg/agents/advisor/prompts.py` | Промпт рекомендаций (~70 строк) |
| `agents/oleg/agents/validator/prompts.py` | Промпт валидатора (~40 строк) |
| `agents/oleg/orchestrator/prompts.py` | Промпты оркестратора (decide, review, synthesize) |

### Удаляем (агенты не в цепочке, промпты не используются)

| Файл | Причина |
|---|---|
| `agents/oleg/agents/researcher/prompts.py` | Researcher не вызывается |
| `agents/oleg/agents/quality/prompts.py` | Quality не вызывается |
| `agents/oleg/agents/christina/prompts.py` | Christina не вызывается |
| `agents/oleg/agents/seo/prompts.py` | SEO/Funnel отключён |

### Этап 2 (будущий)

При переходе на новую архитектуру — промпты V2 (reporter, marketer, advisor, validator) станут основой для новых агентов. V3 micro-agent `.md` файлы будут переработаны или заменены.

---

## Порядок выполнения

1. **Удаление мёртвого кода** (Секция 1) — безопасно, нет зависимостей
2. **Создание shared/notion_client.py** (Секция 2) — новый файл
3. **Миграция импортов** (Секции 2 + 4) — переключить все файлы на shared/
4. **Удаление старых NotionService файлов** (Секция 2)
5. **Удаление oleg/config.py** (Секция 5) — после миграции price_tools
6. **Верификация** (Секция 6) — imports + dry-run + тестовый отчёт
7. **Серверная чистка** (Секция 3) — остановить wookiee_oleg, запустить wookiee_v3

---

## Что НЕ входит в Этап 1

- Изменение архитектуры (слои, оркестрация) → Этап 2
- Переписывание промптов → Этап 2
- Перенос tools в shared/ → Этап 2
- Переименование oleg/ → engine/ → Этап 2
- Новые типы отчётов → Этап 2
