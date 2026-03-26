# Задача: Единая система отчётности Wookiee

## Контекст

Сейчас в Wookiee существуют **две параллельные системы** генерации отчётов (V2 и V3), причём ни одна не работает автоматически. Процесс `python -m agents.v3` **не запущен** — нет ни контейнера, ни фонового процесса. База conductor.db не существует. Все отчёты за последние недели генерировались вручную через `scripts/test_v2_bridge.py`.

Нужно: **оставить одну рабочую систему, удалить дублирование, запустить автоматику**.

---

## Текущее состояние: что работает

### Проверенные отчёты (генерация + доставка в Notion + Telegram)

| Тип | Последний тест | Как генерируется | Время |
|---|---|---|---|
| **Daily финансовый** | 24.03 ✅ | V2 bridge: ReAct loop (DeepSeek V3.2) → review (Kimi K2.5) | ~15 мин |
| **Weekly финансовый** | 16-22.03 ✅ | V2 bridge: то же | ~15 мин |
| **Marketing weekly** | 16-22.03 ✅ | V2 bridge: то же | ~15 мин |
| **Price analysis weekly** | 16-22.03 ✅ | **Детерминистический** скрипт (без LLM) | ~14 мин |
| **Localization weekly** | 18-24.03 ✅ | **Детерминистический** скрипт: WB API tariffs + logistics cost audit (без LLM) | ~2 мин |

### Что НЕ работает / НЕ проверено

| Тип | Проблема |
|---|---|
| **Monthly финансовый** | Не тестировался, но код идентичен weekly |
| **Marketing monthly** | Не тестировался |
| **Price monthly** | Не тестировался, но код тот же что weekly |
| **Funnel weekly** | ОТКЛЮЧЁН: tool name mismatch (`get_wb_funnel` vs `get_funnel_analysis`) |
| **Finolog weekly** | ОТКЛЮЧЁН: MCP-сервер не развёрнут |
| ~~**Localization weekly**~~ | ~~Config есть, реализации нет~~ — **РЕАЛИЗОВАН** (см. выше) |
| **Promotion scan** | Stub, отключён |

---

## Проблема: две системы

### V2 (agents/oleg/) — Legacy

**OlegOrchestrator** — цепочка агентов с ReAct loop:
- Reporter → Researcher → Advisor → Validator → Review
- Модели: DeepSeek V3.2 (main) + Kimi K2.5 (review)
- `max_chain_steps=1` (фактически single-pass reporter)
- Каждый агент — класс с ReAct loop и tool calls к `shared/data_layer.py`

**Файлы:**
- `agents/oleg/orchestrator/orchestrator.py` — OlegOrchestrator
- `agents/oleg/orchestrator/chain.py` — ChainResult, AgentStep
- `agents/oleg/orchestrator/prompts.py` — системные промпты
- `agents/oleg/agents/reporter/` — ReporterAgent (основной)
- `agents/oleg/agents/researcher/` — ResearcherAgent
- `agents/oleg/agents/marketer/` — MarketerAgent
- `agents/oleg/agents/advisor/` — AdvisorAgent
- `agents/oleg/agents/validator/` — ValidatorAgent
- `agents/oleg/agents/quality/` — QualityAgent
- `agents/oleg/agents/christina/` — ChristinaAgent
- `agents/oleg/executor/react_loop.py` — ReAct execution engine
- `agents/oleg/app.py` — V2 entry point (APScheduler + bot)
- `agents/oleg/bot/` — Telegram bot handlers
- `agents/oleg/config.py` — V2 конфигурация

### V3 (agents/v3/) — Текущая обёртка

**НЕ самостоятельная система**, а обёртка над V2:
- `agents/v3/orchestrator.py` — оркестратор, 4 из 7 типов отчётов вызывают `_run_v2_engine()`
- `agents/v3/scheduler.py` — расписание (16 jobs), но НЕ ЗАПУЩЕН
- `agents/v3/conductor/` — умный оркестратор (gates → generate → validate → deliver), НЕ ЗАПУЩЕН
- `agents/v3/delivery/` — доставка (Notion + Telegram), дублирует `agents/oleg/services/notion_service.py`
- `agents/v3/gates.py` — проверки данных перед генерацией
- `agents/v3/app.py` — entry point (`python -m agents.v3`)
- `agents/v3/config.py` — конфигурация (дублирует oleg/config.py)

### V2 Bridge — мост между ними

```
V3 scheduler → V3 orchestrator.run_daily_report()
  → _run_v2_engine()
    → _init_v2_orchestrator() — lazy singleton
      → OlegOrchestrator(agents={reporter, researcher, ...})
    → orchestrator.run_chain(task=..., task_type="daily")
      → reporter.execute() — ReAct loop с SQL tools
    → convert ChainResult → V3 dict
  → _ensure_report_fields() + _fill_telegram_summary()
  → deliver(notion + telegram)
```

### Что уже V3-native (без V2)

1. **Price analysis** — `run_price_analysis()` → детерминистический `scripts/run_price_analysis.py` (без LLM)
2. **Localization weekly** — `_job_localization_weekly()` в scheduler → `services/wb_localization/` + `scripts/run_localization_report.py` (без LLM, WB API + tariffs)
3. **Funnel** — `run_funnel_report()` → V3 micro-agents (отключён)
4. **Finolog** — `run_finolog_report()` → V3 micro-agents (отключён)

---

## Дублирование конкретно

| Компонент | V2 (legacy) | V3 (current) |
|---|---|---|
| **Config** | `agents/oleg/config.py` | `agents/v3/config.py` |
| **Notion delivery** | `agents/oleg/services/notion_service.py` | `agents/v3/delivery/notion.py` |
| **Telegram formatting** | `agents/oleg/bot/formatter.py` | `agents/v3/delivery/telegram.py` |
| **Telegram bot** | `agents/oleg/bot/telegram_bot.py` | `agents/v3/app.py` (минимальный) |
| **Scheduler** | `agents/oleg/app.py` (APScheduler) | `agents/v3/scheduler.py` |
| **Report formatting** | LLM-generated (в orchestrator) | `agents/v3/report_formatter.py` (детерминистический) |
| **Gate checks** | `agents/oleg/pipeline/gate_checker.py` | `agents/v3/gates.py` |

---

## Что нужно сделать

### Цель

Одна система, которая:
1. Запускается одной командой (`python -m agents.v3`)
2. Генерирует все отчёты по расписанию
3. Доставляет в Notion + Telegram
4. Мониторит себя (watchdog, alerts)
5. Не содержит мёртвый/дублированный код

### Расписание (целевое)

**Ежедневно:**
- 05:00 — ETL sync
- 05:30 — Finolog categorization
- 06:00-12:00 — Gate check (каждый час, при ready → генерация)
- ~07:00-09:00 — **Daily финансовый отчёт** (когда данные готовы)
- 12:00 — Deadline alert (если отчёт не создан)
- 15:00 — Catchup (повтор если пропущен)

**Понедельник (дополнительно):**
- ~09:30 — **Weekly финансовый**
- ~10:00 — **Marketing weekly**
- ~10:30 — **Price analysis weekly** (детерминистический)
- ~13:00 — **Localization weekly** (аудит логистических расходов, детерминистический, WB API)

**1-й понедельник месяца (дополнительно):**
- ~11:00 — **Monthly финансовый**
- ~11:30 — **Marketing monthly**
- ~12:00 — **Price analysis monthly** (детерминистический)

**Мониторинг:**
- Каждые 4ч — Anomaly monitor
- Каждые 6ч — Watchdog heartbeat
- Каждые 60 мин — Notion feedback (prompt tuner)

### Фазы реализации

#### Фаза 1: Запуск (приоритет — отчёты должны приходить)

1. **Убедиться, что `python -m agents.v3` стартует без ошибок** на текущей машине
2. **Проверить, что conductor правильно вызывает** все 4 типа отчётов через V2 bridge
3. **Проверить доставку** — Notion + Telegram для всех типов
4. **Запустить как фоновый процесс** (launchd на Mac, или systemd на сервере, или Docker)
5. **Подождать 1 рабочий день** — проверить что daily пришёл автоматически

#### Фаза 2: Консолидация (удаление V2 обёртки)

**Ключевое решение:** V2 bridge (`_run_v2_engine`) — это единственный способ генерации daily/weekly/monthly/marketing отчётов. Есть два пути:

**Вариант A: Оставить V2 engine, убрать дублирование вокруг него**
- Удалить `agents/oleg/app.py` (V2 entry point, scheduler)
- Удалить `agents/oleg/bot/` (V2 telegram bot)
- Удалить `agents/oleg/config.py` (перенести нужное в v3/config)
- Удалить `agents/v3/delivery/notion.py` — использовать `agents/oleg/services/notion_service.py` (он уже работает, проверен, с fix payload batching)
- ИЛИ наоборот: перенести NotionService в shared/ и удалить оба дубля
- Результат: V3 scheduler + conductor + delivery обёртка, V2 engine для генерации

**Вариант B: Переписать генерацию на V3-native (без V2)**
- Создать V3 micro-agents для daily/weekly/monthly/marketing
- Каждый micro-agent = LangGraph ReAct с tools из `shared/data_layer.py`
- Промпты из текущих V2 agents перенести в MD-файлы `agents/v3/agents/`
- Удалить `agents/oleg/orchestrator/` полностью
- Удалить `agents/oleg/agents/` полностью
- Удалить V2 bridge код из `agents/v3/orchestrator.py`
- Результат: чистая V3 система, ~50% кода удалено

**Рекомендация: Вариант A сейчас, Вариант B потом.** V2 engine работает и проверен. Переписывать генерацию рискованно без regression testing.

#### Фаза 3: Чистка

- Удалить мёртвый код: V2 playbooks, legacy prompts
- Удалить файлы-дубли ("* 2.py", "* 2.md" — их >80 в git status)
- Консолидировать config в один файл
- Консолидировать NotionService в одно место
- Удалить неиспользуемые agents (christina, quality — не вызываются при `max_chain_steps=1`)

---

## Критически важные файлы

### Оставить (рабочий код)

| Файл | Зачем |
|---|---|
| `agents/v3/orchestrator.py` | Оркестратор всех отчётов |
| `agents/v3/scheduler.py` | Расписание (16 jobs) |
| `agents/v3/conductor/` | Gate check → generate → validate → deliver |
| `agents/v3/app.py` | Entry point |
| `agents/v3/config.py` | Конфигурация |
| `agents/v3/gates.py` | Проверки данных |
| `agents/v3/report_formatter.py` | Детерминистическое форматирование |
| `agents/v3/delivery/` | Доставка (Notion + TG) |
| `agents/oleg/orchestrator/orchestrator.py` | V2 engine (пока нужен) |
| `agents/oleg/executor/react_loop.py` | ReAct execution (пока нужен) |
| `agents/oleg/agents/reporter/` | ReporterAgent (пока нужен) |
| `agents/oleg/agents/advisor/` | AdvisorAgent (пока нужен) |
| `agents/oleg/agents/validator/` | ValidatorAgent (пока нужен) |
| `agents/oleg/services/notion_service.py` | NotionService (рабочий, с fix batching) |
| `agents/oleg/services/price_analysis/` | Детерминистический ценовой анализ |
| `agents/oleg/services/*_tools.py` | SQL tools для agents |
| `shared/data_layer.py` | Единственный data access layer |
| `shared/notion_blocks.py` | MD → Notion blocks converter |
| `shared/config.py` | Shared config |
| `scripts/run_price_analysis.py` | Ценовой анализ (вызывается из V3) |
| `scripts/run_localization_report.py` | Ручной запуск логистического аудита |
| `services/wb_localization/` | Логистический аудит: tariffs ETL, cost analysis, report_md, history |

### Удалить (мёртвый код)

| Файл/директория | Почему |
|---|---|
| `agents/oleg/app.py` | V2 entry point, заменён на `agents/v3/app.py` |
| `agents/oleg/bot/` | V2 telegram bot, заменён на V3 app.py handlers |
| `agents/oleg/config.py` | Дублирует `agents/v3/config.py` |
| `agents/oleg/pipeline/` | V2 gate checker, заменён на `agents/v3/gates.py` |
| `agents/oleg/agents/researcher/` | Не вызывается при `max_chain_steps=1` |
| `agents/oleg/agents/marketer/` | Не вызывается при `max_chain_steps=1` |
| `agents/oleg/agents/quality/` | Не вызывается при `max_chain_steps=1` |
| `agents/oleg/agents/christina/` | Не вызывается при `max_chain_steps=1` |
| `agents/oleg/playbook.md` | V2 playbook, промпты теперь в orchestrator.py |
| `agents/oleg/marketing_playbook.md` | То же |
| `agents/oleg/christina_playbook.md` | То же |
| `agents/oleg/bot/formatter.py` | Дублирует `agents/v3/delivery/telegram.py` |
| Все файлы `"* 2.py"`, `"* 2.md"` | Дубли от Cursor/merge конфликтов |

### Консолидировать

| Что | Откуда → Куда |
|---|---|
| NotionService | `oleg/services/notion_service.py` + `v3/delivery/notion.py` → `shared/notion_service.py` |
| Config | `oleg/config.py` + `v3/config.py` → `shared/config.py` (расширить) |
| Telegram formatter | `oleg/bot/formatter.py` + `v3/delivery/telegram.py` → оставить только V3 |

---

## Полная проверка системы

### Этап 0: Запуск без ошибок

```bash
# 1. Dry run — проверить что все jobs видны
python -m agents.v3 --dry-run

# Ожидание: список всех scheduled jobs, без ImportError/tracebacks
# Если ошибка — починить до перехода дальше
```

- [ ] `--dry-run` выводит список jobs без ошибок
- [ ] Все env-переменные на месте (OPENROUTER_API_KEY, TELEGRAM_BOT_TOKEN, NOTION_TOKEN, NOTION_DATABASE_ID, ADMIN_CHAT_ID, DB_HOST/PORT/USER/PASSWORD)

### Этап 1: Ручная генерация каждого типа отчёта

Запустить каждый тип вручную через `scripts/test_v2_bridge.py` и убедиться что генерация + доставка работают.

**1.1 Daily финансовый (за вчера)**
```bash
python -m scripts.test_v2_bridge --deliver daily 2026-03-25
```
- [ ] STATUS: success или partial (не failed)
- [ ] DETAILED REPORT LENGTH: > 5000 chars
- [ ] SECTIONS (## ▶): >= 8
- [ ] Notion: страница создана, toggle-секции раскрываются, таблицы рендерятся
- [ ] Telegram: сообщение пришло, ссылка на Notion кликабельна
- [ ] Время генерации: < 20 мин

**1.2 Weekly финансовый (прошлая неделя: пн-вс)**
```bash
python -m scripts.test_v2_bridge --deliver weekly 2026-03-16 2026-03-22
```
- [ ] STATUS: success или partial
- [ ] DETAILED REPORT LENGTH: > 10000 chars
- [ ] SECTIONS: >= 10
- [ ] Содержит гипотезы с Confidence 🟢🟡🔴
- [ ] Содержит секцию Advisor рекомендаций
- [ ] Notion: toggle-секции, таблицы
- [ ] Telegram: сообщение пришло

**1.3 Monthly финансовый (прошлый месяц)**
```bash
python -m scripts.test_v2_bridge --deliver monthly 2026-03-01 2026-03-25
```
- [ ] STATUS: success или partial
- [ ] DETAILED REPORT LENGTH: > 10000 chars
- [ ] Notion + Telegram доставка

**1.4 Marketing weekly**
```bash
python -m scripts.test_v2_bridge --deliver marketing_weekly 2026-03-16 2026-03-22
```
- [ ] STATUS: success или partial
- [ ] DETAILED REPORT LENGTH: > 8000 chars
- [ ] Содержит воронки по каналам (WB, OZON)
- [ ] Содержит модельную матрицу (Growth/Harvest/Optimize/Cut)
- [ ] Notion: toggle-секции
- [ ] Telegram: сообщение

**1.5 Marketing monthly**
```bash
python -m scripts.test_v2_bridge --deliver marketing_monthly 2026-03-01 2026-03-25
```
- [ ] STATUS: success или partial
- [ ] Notion + Telegram доставка

**1.6 Price analysis weekly (детерминистический)**
```bash
python -m scripts.test_v2_bridge --deliver price_analysis 2026-03-16 2026-03-22
```
- [ ] STATUS: success
- [ ] DETAILED REPORT LENGTH: > 30000 chars (58K было в последнем тесте)
- [ ] Содержит ВСЕ модели из БД (проверить по `shared/data_layer.py`)
- [ ] Каждая модель: toggle `## ▶ ModelName`, внутри toggle `### ▶ Wildberries/Ozon`
- [ ] Каждая модель: Сейчас, Рекомендация, Ожидаемый результат, Как проверить, Маркетинг, Сценарии «что если» (6 вариантов), Обоснование
- [ ] Hold-модели: сводная таблица внизу
- [ ] Notion: все toggles раскрываются, нет ошибок 400
- [ ] Telegram: сообщение
- [ ] Время: < 15 мин (без LLM, чисто БД + расчёты)
- [ ] Стоимость: $0.00 (нет LLM-вызовов)

**1.7 Localization weekly (аудит логистических расходов, детерминистический)**
```bash
python scripts/run_localization_report.py --date-from 2026-03-18 --date-to 2026-03-24
```
- [ ] Отчёт сгенерирован без ошибок
- [ ] Содержит данные по обоим кабинетам (ИП + ООО)
- [ ] Top-проблемные артикулы с индексом локализации
- [ ] Сводка: overall_index, суммарные расходы
- [ ] Notion: страница создана, тип = "Анализ логистических расходов"
- [ ] Telegram: сообщение пришло (если не `--no-telegram`)
- [ ] Время: < 5 мин (без LLM, WB API + расчёты)
- [ ] Стоимость: $0.00 (нет LLM-вызовов)

### Этап 2: Проверка Notion качества

Для каждого доставленного отчёта открыть Notion и проверить:

- [ ] **Заголовок** страницы корректный (тип + период на русском)
- [ ] **Тип анализа** property заполнен правильно
- [ ] **Период начала/конца** properties заполнены
- [ ] **Статус** = "Актуальный"
- [ ] **Toggle-секции** (▶) раскрываются по клику
- [ ] **Таблицы** рендерятся корректно (колонки выровнены, числа читаемы)
- [ ] **Bold/italic** форматирование работает
- [ ] **Нет артефактов**: raw markdown `**text**`, BBCode `[b]text[/b]`, HTML-теги
- [ ] **Нет пустых секций** (заголовок без контента)
- [ ] **Нет обрезанного текста** (2000 char limit не обрубает данные)

### Этап 3: Проверка Telegram качества

Для каждого доставленного отчёта проверить Telegram:

- [ ] Сообщение пришло в правильный чат (ADMIN_CHAT_ID)
- [ ] Ссылка на Notion кликабельна (`<a href="...">📊 Подробный отчёт</a>`)
- [ ] Основные метрики присутствуют (выручка, маржа, заказы)
- [ ] Драйверы/Антидрайверы извлечены (для daily/weekly)
- [ ] Нет raw HTML-тегов в тексте
- [ ] Сообщение не обрезано (< 4000 chars, split если длиннее)
- [ ] `parse_mode="HTML"` применён (жирный текст рендерится)

### Этап 4: Проверка автоматического запуска

```bash
# Запустить систему
python -m agents.v3 &

# Подождать ~1 мин, проверить что процесс жив
ps aux | grep "agents.v3" | grep -v grep

# Проверить логи
tail -f agents/v3/data/v3.log  # или stdout
```

- [ ] Процесс стартовал без ошибок
- [ ] Scheduler зарегистрировал все jobs (лог: "Scheduled job: ...")
- [ ] Telegram bot polling запущен (лог: "Bot polling started")
- [ ] Conductor state DB создана (`agents/v3/data/conductor.db`)

**Проверка gate check (можно не ждать утра):**
```bash
# Вызвать вручную
python -c "
import asyncio
from agents.v3.gates import check_all
result = asyncio.run(check_all('wb'))
print(f'can_generate: {result.can_generate}')
print(f'caveats: {result.caveats}')
for g in result.gates:
    print(f'  {g.name}: {g.passed} — {g.message}')
"
```
- [ ] Gate check отрабатывает без ошибок
- [ ] Для WB: ETL gate = True (данные загружены), Source data gate = True, Logistics gate = True

**Проверка Telegram бота:**
- [ ] Отправить `/ping` → получить ответ
- [ ] Отправить `/health` → получить статус (LLM ✅, DB ✅, Last run: ...)
- [ ] Отправить `/report_daily` → запуск генерации, через ~15 мин отчёт в Notion + TG

### Этап 5: Проверка расписания (ждём 1 рабочий день)

**День 1 (будний):**
- [ ] Gate check запускался с 06:00 (лог)
- [ ] При ready: Telegram уведомление "Данные готовы"
- [ ] Daily отчёт сгенерирован автоматически
- [ ] Daily отчёт доставлен в Notion
- [ ] Daily отчёт доставлен в Telegram
- [ ] conductor.db содержит запись: date=today, report_type=DAILY, status=success

**Понедельник (если попал):**
- [ ] Weekly финансовый сгенерирован
- [ ] Marketing weekly сгенерирован
- [ ] Price weekly сгенерирован
- [ ] Localization weekly сгенерирован (13:00)
- [ ] Все четыре доставлены в Notion + Telegram
- [ ] conductor.db: 5 записей (daily + 4 weekly)

**Deadline check (12:00):**
- [ ] Если отчёт не создан к 12:00 → Telegram алерт пришёл
- [ ] Алерт содержит: какие отчёты пропущены, причину (gate failed / timeout / error)

### Этап 6: Проверка отказоустойчивости

**6.1 LLM недоступен:**
```bash
# Временно поставить невалидный ключ
export OPENROUTER_API_KEY="invalid"
# Запустить daily
python -m scripts.test_v2_bridge daily 2026-03-25
```
- [ ] STATUS: failed (не зависает бесконечно)
- [ ] Ошибка залогирована
- [ ] Telegram алерт отправлен (если запущен через conductor)

**6.2 БД недоступна:**
- [ ] Gate check возвращает can_generate=False
- [ ] Отчёт не запускается
- [ ] Watchdog алерт приходит в Telegram

**6.3 Notion недоступен:**
- [ ] Отчёт генерируется (не зависит от Notion)
- [ ] Ошибка доставки залогирована
- [ ] Telegram сообщение всё равно отправляется (без ссылки на Notion)

**6.4 Процесс убит и перезапущен:**
```bash
kill $(pgrep -f "agents.v3")
python -m agents.v3 &
```
- [ ] Процесс перезапускается без потери состояния
- [ ] conductor.db не повреждена
- [ ] Уже сгенерированные отчёты не генерируются повторно (status=success в DB)

### Этап 7: Проверка после чистки кода

После удаления V2 дублей:

```bash
# Import check — ничего не сломалось
python -c "from agents.v3 import orchestrator, config, scheduler; print('OK')"

# Полный тест: dry run
python -m agents.v3 --dry-run

# Полный тест: один отчёт
python -m scripts.test_v2_bridge --deliver daily 2026-03-25
```

- [ ] Все imports работают (нет ImportError на удалённые модули)
- [ ] `--dry-run` без ошибок
- [ ] Daily отчёт генерируется и доставляется
- [ ] Тесты проходят: `python -m pytest tests/ -x -q`

---

## Команды для быстрой диагностики

```bash
# Статус процесса
ps aux | grep "agents.v3" | grep -v grep

# Последние записи conductor
sqlite3 agents/v3/data/conductor.db "SELECT date, report_type, status, attempts FROM conductor_log ORDER BY date DESC LIMIT 10;"

# Последние orchestrator runs
python -c "
from shared.data_layer import _db_cursor
with _db_cursor('wb') as cur:
    cur.execute('SELECT task_type, status, started_at, duration_ms FROM orchestrator_runs ORDER BY started_at DESC LIMIT 10')
    for row in cur.fetchall():
        print(row)
"

# Проверка gate прямо сейчас
python -c "
import asyncio
from agents.v3.gates import check_all
r = asyncio.run(check_all('wb'))
print(f'Ready: {r.can_generate}')
for g in r.gates: print(f'  {g.name}: {\"✅\" if g.passed else \"❌\"} {g.message}')
"

# Тест LLM connectivity
python -c "
import asyncio
from agents.v3.monitor import _check_llm
print(asyncio.run(_check_llm()))
"

# Тест Notion connectivity
python -c "
import asyncio
from agents.v3 import config
from shared.notion_client import NotionClient
nc = NotionClient(token=config.NOTION_TOKEN, database_id=config.NOTION_DATABASE_ID)
print(f'Enabled: {nc.enabled}')
"
```
