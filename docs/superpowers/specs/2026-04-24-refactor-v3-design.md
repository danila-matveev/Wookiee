# Wookiee — Refactor v3 (Фаза 1: Cleanup + Colleague-Ready Repo)

**Date:** 2026-04-24
**Status:** Draft — pending user approval
**Supersedes cleanup-v2 (2026-04-13):** нет. Расширяет и актуализирует.
**Next:** Фаза 2 — `/hygiene` skill spec (отдельная brainstorm-сессия после выполнения Фазы 1).

---

## 1. Цель и Non-Goals

### Цель
Привести `/Users/danilamatveev/Projects/Wookiee` в состояние, пригодное для добавления коллег в репозиторий:
- Убрать мусор и мёртвый код (Oleg, Lyudmila-остатки, бинарные файлы, 13+ лишних страниц в Wookiee Hub, устаревшие docker-сервисы, старые planning-артефакты, 4 неиспользуемых MCP-сервера, `services/product_matrix_api/`).
- Закоммитить и завершить всё активное untracked (`services/creative_kb/`, `services/wb_logistics_api/`, `services/wb_localization/calculators/`, `services/wb_localization/sheets_export/`, тесты).
- Привести структуру к единому виду: одна точка входа в документацию, понятная карта «где что лежит», README в каждом активном модуле, `ONBOARDING.md` для новых коллег.
- Весь рефакторинг — через PR с auto-merge на зелёных проверках от Codex + Copilot.

### Non-Goals
- Не пишется `/hygiene` skill — отдельный spec в Фазе 2.
- Не добавляется новая функциональность в активные сервисы (только завершение начатого untracked).
- Не переписывается Supabase-схема (кроме правок `tools`/`tool_runs` при необходимости).
- Не трогаются глобальные скиллы `~/.claude/skills/` — только проектные `.claude/skills/`.

### Отношение к cleanup-v2
`2026-04-13-project-cleanup-v2-design.md` остаётся source-of-truth по «known garbage» (секции 2.1–2.7). Текущий spec:
- Актуализирует список удаления с учётом изменений за 10 дней.
- Добавляет file-by-file audit через параллельных субагентов.
- Добавляет решения по untracked коду.
- Добавляет trim Wookiee Hub до 2 модулей (Комьюнити + Агенты).
- Добавляет унификацию документации и onboarding.
- Переводит исполнение на PR-workflow с auto-merge.
- Добавляет Orchestrator-Critic и Final Verifier субагентов.

---

## 2. Архитектура субагентов

Рефакторинг состоит из 4 стадий (A, A.5, B, C) с разными ролями субагентов.

### 2.1 Stage A — Parallel Auditors (read-only)

4 субагента параллельно (через `superpowers:dispatching-parallel-agents`). Каждый на свою зону. Ничего не удаляют и не коммитят. Пишут отчёты в `.planning/refactor-audit/`.

| Субагент | Зона ответственности | Выход |
|---|---|---|
| `audit-code` | `agents/`, `services/`, `scripts/`, `shared/`, `mcp_servers/` — мёртвый код (0 импортов), дубли, orphaned файлы, проверка использования `scripts/*` в скиллах/сервисах | `code-audit.md` — список DELETE/KEEP/MERGE с обоснованием |
| `audit-docs` | `docs/`, корневые `.md` (README, AGENTS, CLAUDE, CONTRIBUTING, SECURITY), `.planning/`, `.superpowers/` — устаревшие доки, дубли, оборванные ссылки | `docs-audit.md` — что актуально, что в archive, что переписать |
| `audit-hub` | `wookiee-hub/` — граф зависимостей pages/components/stores/hooks при trim до 2 модулей (Комьюнити + Агенты) | `hub-audit.md` — список файлов к удалению, что нужно создать заново |
| `audit-infra` | `deploy/`, `docker-compose*.yml`, `.claude/`, `.env.example`, `.gitignore`, `pyproject.toml`, `Makefile`, `setup_bot.sh`, `.mcp.json` | `infra-audit.md` — устаревшие конфиги, правила в `.gitignore`, изменения в `.mcp.json` |

Вход каждому: cleanup-v2 spec + этот spec + чёткая инструкция «только report, не трогай файлы».

### 2.2 Stage A.5 — Orchestrator-Critic

**Новый субагент — `refactor-orchestrator`.** Роль: критически проверить результаты Stage A и принять финальное решение.

Действия:
1. Читает 4 отчёта + cleanup-v2 + текущий spec.
2. **Критика**: ищет противоречия между отчётами, неполноты, слишком агрессивные/трусливые решения.
3. **Cross-check**: для каждого DELETE-кандидата выполняет grep импортов **во всех зонах** (не только в своей).
4. **Зеркальный список**: проверяет файлы в корне проекта и директориях, не покрытых ни одним audit-ом.
5. **Risk-check**: у каждого DELETE-решения — обоснование, rollback, проверка что не ломает других.
6. Генерирует финальный **`.planning/refactor-manifest.md`** со структурой:
   - Изменения по 7 PR-шагам (точные пути файлов).
   - Обоснование каждого DELETE (что, почему, где проверили, что могло сломаться).
   - Список flagged items — решения, где нужен твой выбор (спорные не берёт на себя).
   - Финальное имя для `services/observability/` после переименования.
   - Решение по Oleg extraction: нужно ли переносить `agents/oleg/services/*_tools.py` в `shared/services/` (зависит от того, импортируются ли они где-то кроме удаляемых MCP-серверов).
7. Опционально: вызывает `codex-arch-review` для адверсариальной критики manifest'а.
8. Показывает manifest пользователю. **Stage B не начинается без approval.**

### 2.3 Stage B — Sequential Execution (PR-шаги)

7 PR-шагов строго последовательно. Каждый через `/pullrequest` skill (Codex + Copilot review, auto-merge на зелёных).

| # | Ветка | Что делает | Риск |
|---|---|---|---|
| 1 | `refactor/binary-cleanup` | Удаление `.xlsx`/`.pdf`/`.docx`/`.png`/`.wmv` по cleanup-v2 2.1–2.3 + дополнения из manifest (включая `.wmv` запись экрана, iCloud-дубликаты «*2.*», `scripts 2.txt`, `skills-lock 2.json`) | низкий |
| 2 | `refactor/gitignore-hardening` | Расширение `.gitignore` для блокировки будущего мусора | низкий |
| 3 | `refactor/commit-untracked` | Коммит активных untracked (`creative_kb`, `wb_logistics_api`, `wb_localization/calculators+sheets_export`, тесты) + README к каждому + привязка тестов к своим сервисам | средний |
| 4 | `refactor/remove-dead-code` | Удаление `agents/finolog_categorizer/`, `services/product_matrix_api/`, `mcp_servers/*` (все 4 локальных MCP), `.mcp.json` entries, `services/dashboard_api/` если подтверждено audit, старых Dockerfiles, `.planning/archive/`, `.superpowers/brainstorm/`, других dead-code находок orchestrator'а | средний |
| 5 | `refactor/oleg-cleanup` | Удаление `agents/oleg/` целиком. Если orchestrator подтвердил что `*_tools.py` нужны где-то ещё — extraction в `shared/services/` перед удалением. Обновление импортов. Создание `docs/archive/oleg-v2-architecture.md`. | высокий |
| 6 | `refactor/hub-trim` | Снос 13+ лишних страниц Hub. Остаётся скелет «Комьюнити» (Отзывы, Вопросы, Ответы, Аналитика) + «Агенты» (Табло скиллов, История запусков). Обновление router/меню. | средний |
| 7 | `refactor/docs-unification` | Переименование `services/observability/` → `services/<new_name>`. README в каждом модуле, `ONBOARDING.md`, обновлённый `docs/index.md`, PR-template, `docs/skills/*.md`, placeholder-скелет `.claude/skills/hygiene/` | низкий |

### 2.4 Stage C — Final Verifier

**Новый субагент — `refactor-verifier`.** После слияния всех 7 PR-ов. Роль: «дошли ли до цели».

Действия:
1. Сравнивает финальное состояние репо с Refactor Manifest.
2. Прогоняет `pytest`, линт, `npm run build` в Hub.
3. Sampling-проверка работы активных скиллов (dry-run): `/tool-status`, `/finance-report --dry-run` и т.п.
4. Проверка документации: все ссылки живые, нет упоминаний Oleg/Lyudmila/Vasily как активных.
5. Генерирует `**.planning/refactor-verification.md**`:
   - GREEN: подтверждено рабочим.
   - YELLOW: требует ручной проверки (Hub UI, опциональные флоу).
   - RED: сломано — нужно фиксить.
6. Если есть RED — открывает PR #8 `refactor/verification-fixes`.

### 2.5 Поток целиком

```
Stage A (parallel)        →  4 audit reports
Stage A.5 (orchestrator)  →  refactor-manifest.md → USER APPROVAL
Stage B (PRs 1-7)         →  каждый через /pullrequest, Codex+Copilot review, auto-merge
Stage C (verifier)        →  verification report → PR #8 если нужно
```

---

## 3. Что удаляем (delta поверх cleanup-v2)

Базовый список — секции 2.1–2.7 cleanup-v2. Ниже только дельта. Финальный точный список — за `refactor-orchestrator`.

### 3.1 Добавляем к удалению

| Путь | Причина |
|---|---|
| `agents/finolog_categorizer/` | Уже удалялся в `789d005`, вернулся untracked — удалить окончательно |
| `services/product_matrix_api/` | Не используется |
| `mcp_servers/wookiee_data/`, `wookiee_kb/`, `wookiee_marketing/`, `wookiee_price/` | Все 4 локальных MCP не используются |
| `mcp_servers/common/`, `mcp_servers/__init__.py` | Осиротевшие после удаления серверов |
| `.mcp.json` — entries `wookiee-data`/`wookiee-kb`/`wookiee-marketing`/`wookiee-price` | Очистка конфига |
| `services/logistics_audit/Запись экрана (01.04.2026 15-30-09) (2).wmv` | Видеозапись |
| `wookiee-hub/src/pages/analytics-*.tsx` (abc, overview, promo, unit) | Не входит в 2 оставляемых модуля |
| `wookiee-hub/src/pages/catalog.tsx`, `shipments.tsx`, `supply.tsx`, `production.tsx`, `ideas.tsx`, `development.tsx`, `dashboard.tsx`, `dashboard-placeholder.tsx` | Не входит в 2 оставляемых модуля |
| `wookiee-hub/src/pages/comms-broadcasts.tsx`, `comms-store-settings.tsx` | Блок Comms оставляем только про отзывы |
| `wookiee-hub/src/pages/product-matrix/` и связанные компоненты/stores/hooks/data/lib (определит audit-hub по графу) | Модули не входят в оставляемые |
| `wookiee-hub/*.png`, `wookiee-hub/index 2.html`, `package-lock 2.json`, `tsconfig.temp 2.json` | iCloud-дубликаты |
| `wookiee-hub/планы/` | Старые референсы |
| `scripts 2.txt`, `skills-lock 2.json` | iCloud-дубликаты |

### 3.2 Пересматриваем (audit-orchestrator финализирует)

| Путь | Вопрос |
|---|---|
| `services/dashboard_api/` | Нужен ли модулю «Агенты» Hub, или UI ходит прямо в Supabase через supabase-js? Orchestrator решит — удалить полностью или оставить и доработать |
| `docs/future/agent-ops-dashboard/` | Переносится ли концепция в новый модуль «Агенты», или идёт в archive |
| `services/knowledge_base/` | Активен ли — проверить по импортам и скиллам |
| `services/ozon_delivery/` | Активен ли — проверить по импортам и скиллам |
| `agents/oleg/services/*_tools.py` | Импортируются ли где-то кроме удаляемых MCP? Если да — extraction в `shared/services/`, иначе — удалить с Oleg |

### 3.3 Оставляем (новое по сравнению с cleanup-v2)

| Путь | Причина |
|---|---|
| `services/creative_kb/` | Активный untracked — коммитим, доводим до финала |
| `services/wb_logistics_api/` | Активный untracked — коммитим, Dockerfile, docker-compose, интеграция с logistics-report |
| `services/wb_localization/calculators/`, `sheets_export/` | Активный untracked — коммитим, README, привязка тестов |
| `tests/wb_localization/*`, `tests/services/logistics_audit/*` | Новые тесты — коммитим, привязываем к сервисам |
| `.claude/skills/*` | Все активны по решению пользователя; audit-infra проверит каждую директорию/файл |

### 3.4 Переименовываем

| Было | Станет | Решение |
|---|---|---|
| `services/observability/` | Имя подберёт orchestrator, кандидаты: `tool_telemetry/`, `tool_metrics/`, `run_logger/` | Утверждается в manifest |

### 3.5 Агенты-scaffold

`agents/` остаётся как директория с `__init__.py` и README «Текущие скиллы — в `.claude/skills/`. Сюда — будущие true-agent реализации». Вся текущая логика (`agents/oleg/`, `agents/finolog_categorizer/`) удаляется.

### 3.6 Санитарные правила orchestrator'а

Orchestrator гарантирует в manifest:
- Ни один удаляемый файл не импортируется из остающегося кода (grep).
- Ни один удаляемый файл не упоминается в остающейся документации без пометки «удалён» (grep по всем `.md`).
- Ни одна удаляемая страница Hub не линкуется из `router.tsx`, `App.tsx` и меню.

---

## 4. Что остаётся и что достраиваем

### 4.1 Активный runtime-контур (после рефакторинга)

**Python-бэкенд:**
```
shared/                      — общие библиотеки (data_layer, config, clients, notion, tool_logger)
shared/services/             — возможный новый модуль для extracted Oleg tools (если orchestrator подтвердит необходимость)
services/
  marketplace_etl/           — ETL WB/OZON → PostgreSQL
  etl/                       — вспомогательные ETL (сверка, качество)
  sheets_sync/               — Google Sheets ↔ Supabase
  wb_localization/           — локализация WB + calculators + sheets_export
  ozon_delivery/             — (подлежит проверке orchestrator'ом)
  content_kb/                — vector search фото (pgvector)
  creative_kb/               — untracked → коммитим, завершаем
  knowledge_base/            — (подлежит проверке orchestrator'ом)
  logistics_audit/           — аудит логистики WB+OZON
  wb_logistics_api/          — untracked → коммитим, завершаем
  <new_name>/                — бывший observability/, переименован
  dashboard_api/             — (подлежит проверке orchestrator'ом)
sku_database/                — товарная матрица (Supabase)
scripts/                     — CLI-скрипты (прочищены audit-code от неиспользуемых)
agents/                      — пустой scaffold с README
```

**Frontend (wookiee-hub):**

Структура — вектор, точные имена файлов и роуты (переиспользовать существующие `comms-*.tsx` с переименованием vs создавать новые под `community/`) определит `audit-hub` в отчёте и финализирует orchestrator в manifest:

```
wookiee-hub/src/
  pages/
    <Комьюнити>              — 4 под-раздела: Отзывы, Вопросы, Ответы, Аналитика
                               (варианты: single page с tabs, либо 4 роута под community/)
    <Агенты>                 — 2 под-раздела: Табло скиллов, История запусков
                               (варианты: single page с tabs, либо 2 роута под agents/)
  components/                — компоненты для 2 модулей (reuse existing comms/* где возможно)
  layout/                    — шапка, сайдбар (ровно 2 пункта меню: «Комьюнити», «Агенты»)
  config/, types/, stores/,
  hooks/, lib/, data/        — audit-hub удалит то, что не используется после trim
```

Главное — в меню 2 пункта, итого 4+2 под-разделов по содержанию.

### 4.2 Что достраиваем (новый функционал)

**А. Модуль «Агенты» в Hub — новая страница + компоненты.**

Источник данных — существующие таблицы Supabase `tools` и `tool_runs`.

В рамках Фазы 1 — только **scaffold**:
- Роут + страница списка скиллов из `tools`.
- Страница истории запусков из `tool_runs`.
- Базовая таблица без украшательств.

Полный UI (фильтры, графики, детальные карточки) — опционально в Фазе 1.5 или отдельным дизайном через `/ui-ux-pro-max` после Фазы 1. Orchestrator отметит это в manifest как «nice-to-have».

**Б. README в каждом активном модуле** — шаблон:
```markdown
# <Название>
## Назначение
<1-2 предложения>
## Точка входа / как запускать
<команда>
## Зависимости
- Data: <Supabase, API, Sheets>
- External: <OpenRouter, Finolog, MPStats>
## Связанные скиллы
- `/skill-name` — <как связан>
## Owner
<имя>
```

**В. Унификация документации** — см. раздел 6.

### 4.3 Что завершаем (доработки untracked)

| Сервис | Что доделать |
|---|---|
| `services/creative_kb/` | README, интеграция с content_kb, привязка к скиллу `content-search` |
| `services/wb_logistics_api/` | README, Dockerfile (существует untracked), docker-compose запись, интеграция с `logistics-report` |
| `services/wb_localization/calculators/` | README, привязка к основному wb_localization |
| `services/wb_localization/sheets_export/` | README, привязка тестов |
| `tests/wb_localization/*` | Коммит + привязка к wb_localization + calculators |
| `tests/services/logistics_audit/*` | Коммит + привязка к logistics_audit |

Разбиение по PR — внутри #3 или отдельным под-шагом, определит orchestrator.

---

## 5. Git workflow & PR setup

### 5.1 Защита main (одноразовая настройка перед Stage A)

- **Branch protection** на `main`:
  - Запрет прямых push.
  - Любые изменения — только через PR.
  - Требование: хотя бы 1 approval или GitHub Auto-Merge после зелёных ревью-ботов.
  - Require status checks to pass перед мёржем.
- **Auto-merge** включён на уровне репозитория.
- **Delete head branches** после мёржа.

`refactor-orchestrator` делает pre-flight: проверяет что защита включена. Если нет — прерывает работу и просит включить.

### 5.2 PR-шаблон — `.github/pull_request_template.md`

```markdown
## Что изменено
<1-3 буллета>

## Почему
<ссылка на spec / refactor-manifest или короткое обоснование>

## Как проверено
- [ ] Локальный lint/тесты прошли
- [ ] Удаляемые файлы не импортируются из остающегося кода (grep)
- [ ] Ссылки в docs актуальны

## Связанные PR / spec
<refactor-manifest.md section X, PR #Y>
```

### 5.3 Поток одного PR-шага

```
1. Claude создаёт ветку refactor/<step-name>
2. Делает коммиты по манифесту
3. Локально прогоняет pytest (если есть тесты) + ruff/lint
4. git push → открывает PR через gh
5. Вызывает /pullrequest → запускает Codex + Copilot review параллельно
6. Результат:
   - Все зелёные → Auto-Merge срабатывает → PR мёржится → ветка удаляется
   - BLOCK от ревьюера → /pullrequest сам или с участием пользователя фиксит, цикл
   - WARNING → Claude решает критично или нет, документирует в комменте
7. Следующий PR-шаг
```

### 5.4 Специальный случай: PR #6 (Hub trim)

Авторевью-боты не видят визуальных регрессий UI. Дополнительные checks:
- До открытия PR: `npm run build` локально — должна пройти сборка.
- `npm test` если `vitest.config.ts` есть (он есть).
- Опционально через `dogfood` skill: smoke-test оставшихся 2 модулей в headless-браузере + скриншот в PR.
- **Manual checkpoint**: PR #6 не получает Auto-Merge автоматически — ждёт ручного подтверждения пользователя. Единственный шаг с ручным контролем в Фазе 1.

### 5.5 Rollback-стратегия

- Мёржнутый PR сломал main → `git revert` merge-commit → новый PR «Revert PR #N» → auto-merge.
- PR открыт, но понятно что не подходит → `gh pr close <N>` + удаление ветки. Манифест правится, новый PR.
- Stage A.5 выдал плохой manifest → правка вручную или новая итерация orchestrator'а. Stage B не стартует до approval.

### 5.6 Observability для пользователя

- GitHub: лента PR `refactor/*`, статусы, auto-merged закрываются.
- Terminal (Claude): короткий отчёт после каждого шага — «PR #N открыт», «PR #N смёржен», «PR #N имеет BLOCK, исправляю».

---

## 6. Унификация документации

### 6.1 Целевая структура

```
/ (repo root)
├── README.md                 — главный файл: что это, зачем, быстрый старт, карта
├── ONBOARDING.md             — новый: для коллег, install → первая команда → куда дальше
├── AGENTS.md                 — правила разработки (актуализируется)
├── CLAUDE.md                 — Claude-specific ссылки (актуализируется)
├── CONTRIBUTING.md           — PR, коммиты, ревью (переписывается под новый workflow)
├── SECURITY.md               — проверка актуальности
│
└── docs/
    ├── index.md              — КАРТА: все разделы с 1-строчным описанием
    ├── architecture.md       — runtime-архитектура (обновляется)
    ├── infrastructure.md     — серверы, деплой (обновляется)
    ├── skills/               — новое: один .md на активный скилл (возможно полу-автоген из .claude/skills/*/SKILL.md + tools таблица)
    ├── services/             — описания сервисов (ссылки на README модулей)
    ├── database/             — справочник метрик и качества данных (как есть)
    ├── guides/               — DoD, окружение, логирование (как есть)
    ├── superpowers/          — specs, plans (как есть)
    ├── archive/              — ретайрнутые агенты, старые истории
    └── adr.md                — архитектурные решения (обновляется)
```

### 6.2 Удаляем/переносим в archive

- Устаревшее по решению orchestrator'а (`PROJECT_MAP.md` если заменён `docs/index.md` и т.п.)
- `docs/future/agent-ops-dashboard/` — archive или delete.
- Все `.md`, упоминающие Oleg как активный — переписываются или переносятся в `docs/archive/`.

### 6.3 ONBOARDING.md — шаблон (финализируется в PR #7)

```markdown
# Onboarding в Wookiee

## За 30 минут вы:
1. Склонируете репо
2. Настроите .env
3. Запустите один отчёт

## Prerequisites
- Python 3.11+
- Node 20+
- Доступы: GitHub collaborator, Supabase invite, Notion workspace, OpenRouter API key

## Шаг 1. Clone & env
<команды>

## Шаг 2. Первая команда
<пример: python scripts/run_report.py --dry-run>

## Шаг 3. Первый PR
1. Ветка feature/your-name-hello
2. Поправьте любой README опечатку
3. gh pr create — дождитесь ревью-ботов
4. Auto-merge сделает своё

## Куда дальше
- Скиллы → docs/skills/
- Сервисы → docs/services/
- Правила → AGENTS.md
- PR → CONTRIBUTING.md

## Контакты
- Owner: <пользователь>
- Telegram/почта: <…>
```

### 6.4 docs/skills/\<name>.md — шаблон

```markdown
# /<skill-name>

## Назначение
<1-2 предложения>

## Триггеры
<из .claude/skills/<name>/SKILL.md>

## Входные данные
- Источники: <Supabase tables, Sheets, API>

## Выходные данные
- Куда публикует: <Notion DB, Sheets, Telegram>

## Команды запуска
<команды или триггер-фразы>

## Связанные сервисы/скрипты
- `scripts/<…>` — <роль>
- `services/<…>` — <роль>

## Статус
production | beta | deprecated
```

### 6.5 PR #7 (docs-unification) — что включает

- Новые файлы: `ONBOARDING.md`, `docs/skills/<name>.md` для каждого активного скилла, README для каждого модуля, `.github/pull_request_template.md`, placeholder `.claude/skills/hygiene/README.md`.
- Обновления: `README.md`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `docs/index.md`, `docs/architecture.md`.
- Переносы: устаревшие upstream в `docs/archive/`.
- Удаления: дубликаты, заменённые новой структурой.

После мёржа PR #7 → Фаза 1 технически завершена (осталась Stage C — verifier).

---

## 7. Фаза 2 concept — `/hygiene` skill (preview)

**Не детальный дизайн.** Точный spec — отдельно после Фазы 1.

### 7.1 Что это
Проектный скилл `.claude/skills/hygiene/`. Запуск:
- Вручную: `/hygiene`
- По расписанию: через `/schedule` (например daily 06:00)

Действия при запуске:
1. Сканирует репо.
2. Находит drift от целевого состояния Фазы 1.
3. Создаёт ветку `chore/hygiene-<дата>`, коммитит исправления.
4. PR через `/pullrequest` с Codex + Copilot review.
5. Auto-merge на зелёных.

### 7.2 Autonomy модель (гибрид D, утверждено в brainstorm)

**Полностью автономно:**
- Коммит незапушенного (по whitelist-путям).
- Пуш в feature-ветку + PR.
- Удаление явного мусора по whitelist (`.DS_Store`, iCloud-дубликаты, `__pycache__`, старые `.wmv`/`.mov`).
- Форматирование (ruff, prettier при наличии конфига).
- Обновление `docs/index.md` при добавлении нового сервиса/скилла.
- Обновление `docs/skills/<name>.md` при изменении `.claude/skills/<name>/SKILL.md`.

**С аппрувом (кладёт в PR, ждёт):**
- Удаление файла/папки вне whitelist.
- Переименование/перенос директорий.
- Удаление не-используемого сервиса/скилла.
- Изменения в `AGENTS.md`, `README.md`, `.env.example`.
- Любые архитектурные правки.

**Никогда:**
- Force-push.
- Удаление из защищённого whitelist (`shared/`, `sku_database/`, `.env*`).
- Изменение branch protection / CI.
- Откат чужих коммитов.

### 7.3 Черновой список checks

| Check | Что проверяет | Default |
|---|---|---|
| `unpushed-work` | Незакоммиченные/незапушенные изменения | auto-commit+push |
| `stray-binaries` | `.xlsx/.pdf/.wmv/.png` вне whitelist | auto-delete |
| `icloud-dupes` | Файлы с « 2» в имени | auto-delete |
| `orphan-imports` | Модули с 0 импортами | ask-user |
| `orphan-docs` | `.md` без ссылок | ask-user |
| `skill-registry-drift` | `.claude/skills/*` ≠ Supabase `tools` | auto-sync |
| `broken-doc-links` | Оборванные ссылки в `.md` | ask-user |
| `missing-readme` | Новая директория без README | ask-user |
| `gitignore-violations` | Файлы, которые должны быть в gitignore | auto-ignore |
| `stale-branches` | Feature-ветки старше 14 дней без активности | ask-user |
| `pycache-committed` | `__pycache__` в треке | auto-untrack |

### 7.4 Конфигурация

`.claude/hygiene-config.yaml` — создаётся в PR #7 как placeholder (вместе со scaffold `.claude/skills/hygiene/`), финализируется в Фазе 2:

```yaml
whitelist_zones:
  allow_binaries:
    - services/logistics_audit/*Итоговый*.xlsx
    - docs/images/
schedule:
  frequency: daily
  time: "06:00"
  timezone: Europe/Moscow
auto_fix:
  unpushed_work: true
  stray_binaries: true
  icloud_dupes: true
ask_user:
  orphan_imports: true
  orphan_docs: true
notification:
  channel: telegram
  only_if: ask_required
```

### 7.5 Почему отдельный spec

После Фазы 1 будут видны реальные паттерны мусора, тайминги checks, процент false-positive на `orphan-imports`/`orphan-docs`. Детали skill родятся из наблюдения, не из догадки.

### 7.6 Что фиксируется в Фазе 1 про Фазу 2

- Концепция (этот раздел).
- Pustой scaffold `.claude/skills/hygiene/` с README «Фаза 2 — планируется» — создаётся в PR #7.
- Instruction: после Фазы 1 запустить `/superpowers:brainstorm` для Фазы 2.

---

## 8. Порядок исполнения

1. **Pre-flight** (один раз перед Stage A):
   - Проверка GitHub branch protection + auto-merge включены.
   - Создание директории `.planning/refactor-audit/`.
2. **Stage A** (parallel): 4 auditor-субагента пишут отчёты.
3. **Stage A.5** (orchestrator): генерация `refactor-manifest.md` → **user approval**.
4. **Stage B** (sequential PRs 1-7): каждый через `/pullrequest`, auto-merge.
5. **Stage C** (verifier): запуск `refactor-verifier`, при необходимости PR #8.
6. **Completion**: отметка Фазы 1 как завершённой, переход к brainstorm Фазы 2.

---

## 9. Success Criteria

Фаза 1 считается успешной, если:
- Все 7 PR-шагов смёржены в main (или их часть + PR #8 fixes).
- `git status` чист (ни одного untracked файла не по whitelist).
- `pytest` зелёный.
- `npm run build` в Hub зелёный.
- Верификатор не нашёл RED-состояний.
- Новый человек может пройти `ONBOARDING.md` от клонирования до первой команды.
- `agents/oleg/` удалён, в документации нет упоминаний Oleg как активного.
- Wookiee Hub содержит только 2 модуля (Комьюнити, Агенты).
- `mcp_servers/` удалён, `.mcp.json` чист от неиспользуемых локальных MCP.
- Каждый активный модуль в `services/` имеет README.
- `docs/index.md` — единая точка входа в документацию.

---

## 10. Open Questions (решаются orchestrator'ом)

1. Имя для переименования `services/observability/`.
2. Решение по `services/dashboard_api/`: удалить или доработать под модуль «Агенты».
3. Решение по `services/knowledge_base/`, `services/ozon_delivery/` (активны или legacy).
4. Решение по `docs/future/agent-ops-dashboard/` (archive или delete).
5. Нужна ли extraction `agents/oleg/services/*_tools.py` в `shared/services/` (по grep-проверке импортов).
6. Как оформить историю «Агенты» в Hub: tabs в одной странице или 2 под-страницы с роутами.
