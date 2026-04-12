# Wookiee Hub — Project Restructuring & Cleanup

**Date:** 2026-04-03
**Status:** Approved
**Goal:** Навести порядок в монорепо, удалить мусор, описать каждый модуль, подготовить к будущему разделению на отдельные репозитории.

---

## 1. Контекст

Проект Wookiee Hub — платформа управления e-commerce брендами Wookiee и Telaway. За время разработки накопились:
- ~160MB бинарных файлов (Excel, PDF, PNG, JSON)
- Устаревший код (dashboard_api, vasily_api, v3-миграция)
- 80+ файлов завершённых фаз планирования
- Дублирование в shared/data_layer (800-1200 строк WB/OZON параллелизма)
- Глобальные скиллы, живущие в проектной директории

**Решение:** Подход B — "Логические блоки". Чистка мусора + группировка модулей + README для каждого + PROJECT_MAP.md.

---

## 2. Целевая структура

```
wookiee/
├── agents/
│   └── oleg/                    # Оркестратор отчётов (cron 30min, 7-18 МСК)
│       ├── README.md            # NEW: архитектура, зависимости, endpoints
│       ├── services/            # price_analysis, marketing_tools, agent_tools
│       └── watchdog/            # healthcheck, alerter, diagnostic
├── services/
│   ├── README.md                # NEW: обзор всех сервисов
│   ├── sheets_sync/             # Синхронизация WB/OZON/МойСклад → Google Sheets
│   │   └── README.md            # NEW
│   ├── wb_localization/         # Оптимизация складов WB (ИРП коэффициенты)
│   │   └── README.md            # NEW
│   ├── knowledge_base/          # Vector search по учебным материалам WB (FastAPI :8002)
│   │   └── README.md            # NEW
│   ├── content_kb/              # Индексация фото бренда + vector search
│   │   └── README.md            # NEW
│   ├── product_matrix_api/      # Редактор товарной матрицы (FastAPI)
│   │   └── README.md            # NEW
│   ├── logistics_audit/         # Аудит логистических расходов WB
│   │   └── README.md            # NEW
│   └── observability/           # Логирование запусков агентов → Supabase
│       └── README.md            # NEW (переименовать в agent_logs — отдельная задача)
├── shared/
│   ├── README.md                # NEW: описание всех модулей
│   ├── data_layer/              # SQL-запросы по доменам
│   │   └── README.md            # NEW: карта модулей, известные дупликации
│   ├── clients/                 # API-клиенты (WB, OZON, МойСклад, Sheets, OpenRouter)
│   ├── utils/                   # json_utils
│   └── model_mapping.py         # Маппинг моделей/субмоделей
├── mcp_servers/                 # 4 Python MCP-сервера (data, price, marketing, kb)
│   └── README.md                # NEW
├── mcp/                         # 2 TypeScript MCP (Wildberries 158 tools, Finolog 79 tools)
│   └── README.md                # EXISTS, обновить
├── wookiee-hub/                 # React 19 + TypeScript дашборд
│   └── README.md                # NEW
├── sku_database/                # Supabase схемы, миграции, скрипты
│   └── README.md                # NEW
├── deploy/                      # Docker, docker-compose, healthcheck
│   └── README.md                # NEW
├── scripts/                     # Утилитарные скрипты (run_report.py, data_layer shim)
├── tests/                       # Тесты
├── docs/
│   ├── database/                # DB Reference, Metrics Guide, Quality Notes
│   ├── guides/                  # agent-principles, dod, environment-setup
│   ├── reports/                 # Генерируемые отчёты (2 файла, актуальные)
│   └── superpowers/             # Specs + Plans (актуальные — оставить)
├── .claude/
│   ├── skills/                  # Только Wookiee-специфичные скиллы
│   │   ├── financial-overview/  # Сравнительный финансовый отчёт
│   │   ├── monthly-plan/        # Месячный бизнес-план (multi-agent)
│   │   └── content-search/      # Поиск фото бренда
│   ├── commands/                # Slash-команды для отчётов
│   └── agents/                  # Описания агентов (wb-specialist, data-analyst, etl-engineer)
└── PROJECT_MAP.md               # NEW: полная карта проекта
```

---

## 3. Взаимосвязи модулей

### Система отчётов (Oleg + Skills + Commands)

Это взаимосвязанная экосистема:
- **Oleg Agent** (`agents/oleg/`) — оркестратор, запускается по cron
- **Skills** (`financial-overview`, `monthly-plan`) — скиллы для Claude Code, используют те же данные
- **Commands** (`.claude/commands/daily-report`, `weekly-report`, etc.) — slash-команды, вызывающие скрипты
- **MCP серверы** (`wookiee-data`, `wookiee-price`, `wookiee-marketing`) — инструменты из Oleg, доступные Claude

Все используют `shared/data_layer/` для SQL-запросов и `shared/clients/` для API.

Детальная декомпозиция связей — отдельная задача после чистки.

### Data Layer — известные проблемы

- 12+ параллельных WB/OZON функций (finance, pricing, inventory, traffic, advertising)
- 5 дубликатов Supabase connection в sku_mapping.py
- `validate_wb_data_quality()` в quality.py — 0 использований
- Рефакторинг data_layer — **отдельная фаза**, не в этой задаче

---

## 4. Полный список удаления

### 4.1 Бинарные файлы (~160MB)

```
# Excel — удалить (НЕ используются сегодня)
services/logistics_audit/Аудит логистики 2026-01-01 — 2026-03-23.xlsx     # 124M
services/logistics_audit/ИП Фисанов. Проверка логистики...xlsx             # 24M
services/wb_localization/Отчеты готовые/                                    # ~400K (6 файлов)
services/wb_localization/data/reports/*.xlsx                                # 146K (2 файла, фев 2026)
docs/database/POWERBI DATA SAMPLES/*.xlsx                                  # 94K (2 файла)

# PDF — удалить
docs/archive/agents/vasily/docs/wb_references/*.pdf                        # 3.7M (2 файла)

# PDF — ОСТАВИТЬ (используются, добавлены 3 апреля)
# services/logistics_audit/Расчет переплаты по логистике.pdf               # 634K
# services/logistics_audit/Рекомендации к изменениям в расчете логистики.pdf # 342K

# PNG — удалить
wookiee-hub/mockups/*.png                                                  # 5.5M (2 файла)
wookiee-hub/e2e-*.png                                                      # ~400K (5 файлов)
wookiee-hub/планы/референсы-otveto/                                        # ~1.5M (12 файлов)
*.png (корневые мокапы)                                                    # ~600K

# JSON data — удалить
agents/oleg/data/price_report_*.json                                       # ~4M (13 файлов)
```

### 4.2 Устаревший код

```
# Dashboard API — удалить целиком
services/dashboard_api/                        # Бэкенд для Hub, пересоздадим

# Vasily API — удалить конфиг (код не существует)
deploy/Dockerfile.vasily_api
deploy/Dockerfile.dashboard_api
deploy/deploy-v3-migration.sh

# Docker-compose — убрать vasily-api и dashboard_api сервисы

# Oleg legacy
agents/oleg/logs/oleg_v2.log                  # 237K, устаревший v2

# Retired agents
docs/archive/retired_agents/lyudmila/          # 3.2M

# Playwright logs
.playwright-mcp/                               # 30+ файлов

# Dead code
shared/data_layer/quality.py → validate_wb_data_quality()  # 0 использований (удалить функцию)
```

### 4.3 Planning/Specs мусор

```
# Завершённые фазы
.planning/archive/v1.0/                        # 80+ файлов
.planning/research/                            # 5 файлов
.planning/milestones/v2.0-phases/              # ~30 файлов

# Устаревшие планы
docs/future/agent-ops-dashboard/               # 3.2M (10 файлов, нереализованная фича)
docs/plans/2026-02-25-dashboard-tz.md          # 61K, старое ТЗ
docs/plans/2026-02-25-db-audit-results.md      # 43K, дубликат
docs/plans/2026-04-business-plan.md            # 46K, черновик (есть final)

# Specs/Plans — ОСТАВИТЬ актуальные (financial-overview, monthly-plan, logistics)
# Удалить только завершённые/нерелевантные (smart-conductor, multi-agent-redesign, v3)
docs/superpowers/specs/2026-03-19-multi-agent-redesign.md
docs/superpowers/specs/2026-03-21-smart-conductor-design.md
docs/superpowers/specs/2026-03-25-vasily-localization-full-description.md
```

### 4.4 Git status — зафиксировать удаления

Все файлы с `D` статусом в `.planning/phases/` — закоммитить удаление.

---

## 5. Скиллы — перенос глобальных

**Перенести из `.claude/skills/` → `~/.claude/skills/`:**
- `workflow-diagram` — универсальный генератор диаграмм
- `gws` — Google Workspace CLI базовый
- `gws-drive` — Google Drive операции
- `gws-sheets` — Google Sheets операции
- `ui-ux-pro-max` — дизайн-система
- `pullrequest` — PR workflow

**Команды** (`.claude/commands/`) — аналогично:
- `workflow-diagram.md` → глобальный
- `gws-drive.md` → глобальный
- `gws-sheets.md` → глобальный
- `pullrequest.md` → глобальный

**Оставить в проекте:**
- `financial-overview`, `monthly-plan`, `content-search` — завязаны на Wookiee данные
- `daily-report`, `weekly-report`, `marketing-report`, `period-report`, `update-docs` — Wookiee-специфичные команды

---

## 6. README для каждого модуля

Каждый README.md содержит:

```markdown
# <Название>

## Назначение
<2-3 предложения>

## Как запускать
<Команда запуска, Docker, cron>

## Зависимости
- Внутренние: shared/data_layer, shared/clients
- Внешние: WB API, Google Sheets API, etc.

## Endpoints (если FastAPI)
- GET/POST маршруты

## Статус
Активен / На поддержке / Deprecated
```

---

## 7. PROJECT_MAP.md — корневая карта

Создать `PROJECT_MAP.md` в корне проекта:
- Обзор всех модулей с 1-строчным описанием
- Диаграмма зависимостей (text-based)
- Что деплоится на сервер
- MCP серверы (локальные + внешние)
- Скиллы и команды
- Связи: Oleg ↔ Skills ↔ Commands ↔ MCP ↔ Data Layer

---

## 8. Action Plan — фазы выполнения

### Phase 1: Удаление мусора (~160MB)
- Удалить все бинарные файлы из п.4.1
- Удалить устаревший код из п.4.2
- Удалить planning мусор из п.4.3
- Закоммитить

### Phase 2: Обновить Docker
- Убрать vasily-api, dashboard_api из docker-compose
- Удалить Dockerfile.vasily_api, Dockerfile.dashboard_api
- Удалить deploy-v3-migration.sh

### Phase 3: README для каждого модуля
- 8 сервисов × README
- agents/oleg/README
- shared/README + shared/data_layer/README
- mcp_servers/README
- wookiee-hub/README
- sku_database/README
- deploy/README

### Phase 4: Перенос глобальных скиллов
- 6 скиллов → ~/.claude/skills/
- 4 команды → ~/.claude/commands/ (если поддерживается)
- Проверить что скиллы работают из глобального уровня

### Phase 5: PROJECT_MAP.md
- Корневая карта проекта
- Описание взаимосвязей Oleg ↔ Skills ↔ Commands ↔ MCP

### Phase 6: Финальная проверка
- git status чистый
- Все README на месте
- Скиллы работают
- Docker-compose валиден

### ОТЛОЖЕНО (отдельные задачи):
- Data Layer рефакторинг (дедупликация WB/OZON)
- Переименование observability → agent_logs
- Детальная декомпозиция связей Oleg ↔ Skills
- Разделение на отдельные репозитории

---

## 9. Риски

| Риск | Митигация |
|------|-----------|
| Удалим файл, который используется в проде | Проверять git log --since и grep imports перед удалением |
| Перенос скиллов сломает их | Проверять работоспособность после переноса |
| Docker-compose станет невалидным | docker-compose config --quiet после изменений |
| Импорты сломаются при удалении dashboard_api | grep для всех import dashboard_api перед удалением |
