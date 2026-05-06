---
name: hh-research
description: HR-ресёрч на HH.ru — анализ рынка вакансий, улучшение формулировок собственных вакансий, исследование работодателей. Использует MCP-сервер headhunter. Триггеры — /hh-research, проанализируй вакансии на hh, рынок hh, исследуй компанию на hh, улучши мою вакансию.
triggers:
  - /hh-research
  - hh-research
  - проанализируй вакансии
  - рынок hh
  - исследуй компанию на hh
  - улучши мою вакансию
  - market scan вакансий
---

# HH Research Skill

Скилл закрывает три HR-сценария через MCP-сервер `headhunter` (10 инструментов API hh.ru):

1. **Market scan** — собрать срез рынка вакансий по должности/keywords и выдать summary (вилка зарплат, топ-навыки, регионы, форматы работы, бенефиты).
2. **Vacancy refinement** — взять черновик пользовательской вакансии, найти топ-аналогов, предложить конкретные улучшения.
3. **Employer research** — собрать профиль компании: активные вакансии, частота публикаций, технологический стек.

Опционально — при наличии OAuth — управление своими резюме и откликами (см. Stage 4).

> **Важно:** этот MCP не умеет искать чужие резюме (нет такого тула в публичном API HH). Если пользователь просит «найди кандидата» — мягко переориентировать на «давай соберём профиль вакансий по этой роли + найдём кого именно нанимают конкуренты».

## Доступные MCP-инструменты

| Tool | Назначение | OAuth? |
|------|------------|--------|
| `mcp__headhunter__hh_search_vacancies` | Поиск вакансий с фильтрами (text, area, experience, employment, schedule, salary, per_page) | нет |
| `mcp__headhunter__hh_get_vacancy` | Детали одной вакансии по `vacancy_id` | нет |
| `mcp__headhunter__hh_get_employer` | Информация о компании по `employer_id` | нет |
| `mcp__headhunter__hh_get_similar` | Похожие вакансии для `vacancy_id` | нет |
| `mcp__headhunter__hh_get_areas` | Справочник регионов | нет |
| `mcp__headhunter__hh_get_dictionaries` | Справочник enum-значений (experience, employment, schedule) | нет |
| `mcp__headhunter__hh_get_resumes` | Список своих резюме | OAuth |
| `mcp__headhunter__hh_get_resume` | Детали своего резюме по `resume_id` | OAuth |
| `mcp__headhunter__hh_apply_to_vacancy` | Откликнуться на вакансию | OAuth |
| `mcp__headhunter__hh_get_negotiations` | История своих откликов | OAuth |

Полезные area_id: `1` Москва, `2` СПб, `113` Россия (вся), `4` Новосибирск, `1438` Краснодар.

## Stage 0: Determine intent

Спроси через AskUserQuestion (одна question, single-select):

```
question: "Что хочешь сделать?"
header: "Сценарий"
options:
  - "Сканировать рынок по должности"     → market_scan
  - "Улучшить черновик моей вакансии"     → vacancy_refine
  - "Исследовать компанию"                → employer_research
  - "Свои резюме и отклики (нужен OAuth)" → my_resumes
```

В зависимости от выбора — переходи на соответствующий Stage.

## Stage 1: Market Scan

Выполни инструкции из `prompts/market_scan.md`. Кратко:

1. Уточни через AskUserQuestion: должность (text), регион (Москва/СПб/Россия/другое), уровень опыта (опционально), формат (опционально).
2. Вызови `hh_search_vacancies` с `per_page=100, page=0` и при необходимости `page=1` (итого до 200 вакансий).
3. Для топ-10 вакансий по `salary.from` (или по `published_at desc`) — подтяни детали через `hh_get_vacancy` и `hh_get_employer`.
4. Агрегируй данные по шаблону `templates/market_summary.md`.
5. Выдай результат в чат + сохрани markdown в `data/hh_research/<role-slug>/<YYYY-MM-DD>-market-scan.md` (создать директорию при необходимости).

## Stage 2: Vacancy Refinement

Выполни инструкции из `prompts/vacancy_refine.md`. Кратко:

1. Попроси пользователя дать черновик своей вакансии (полный текст или ссылку на её активную версию на hh.ru).
2. Извлеки роль/keywords из черновика, вызови `hh_search_vacancies` (top-30 по релевантности).
3. Через `hh_get_vacancy` получи детали топ-10 (с самыми высокими salary.to и/или со свежими `published_at`).
4. Сравни черновик с топ-аналогами по 5 разрезам: salary range, обязанности, требования, бенефиты, формат/график.
5. Выдай: конкретный список «что добавить/убрать/переформулировать» + переписанный пример секций (зарплата, обязанности, бенефиты).

## Stage 3: Employer Research

Выполни инструкции из `prompts/employer_research.md`. Кратко:

1. Уточни название компании.
2. Найди её через `hh_search_vacancies` (text=имя компании, per_page=5) — извлеки `employer.id` из первой вакансии.
3. Вызови `hh_get_employer(employer_id)` — собери описание/сайт/отрасль.
4. Вызови `hh_search_vacancies(employer_id=<id>, per_page=100)` — собери все активные вакансии компании.
5. Агрегируй: количество открытых позиций, разрезы по ролям/уровням, частота публикаций (по `published_at` за последние 30/90 дней), типичный стек/требования, зарплатная политика.

## Stage 4: My Resumes & Applications (OAuth required)

⚠️ **Требует OAuth flow.** Если переменные `HH_ACCESS_TOKEN` и `HH_REFRESH_TOKEN` не заданы в `.env` — сообщи пользователю и предложи запустить `examples/oauth_flow.py` из репо `headhunter-mcp-server`.

При наличии токенов:
1. `hh_get_resumes()` → список резюме.
2. Для каждого резюме — `hh_get_resume(resume_id)` для деталей (опционально).
3. `hh_get_negotiations(per_page=100)` → история откликов со статусами.
4. Сводка: сколько откликов в каждом статусе (в работе / отклонены / приглашены), какие висят без ответа дольше 7 дней.

## Модель LLM

Аналитика и tool-use — `MAIN` тир (см. `.claude/rules/economics.md`): `google/gemini-3-flash-preview` через OpenRouter. Эскалация на HEAVY (`anthropic/claude-sonnet-4-6`) — только если confidence по агрегации вакансий < 0.8 или MAIN сходу не справляется со структурированием.

## Денежные значения

Все расчёты по зарплатам делать через `Decimal` (см. `.claude/rules/python.md`). HH возвращает `salary.from`/`salary.to`/`salary.currency`. Если currency != RUR — сконвертировать (зафиксировать курс на дату отчёта или предупредить пользователя).

## Output

Все отчёты сохраняются в `data/hh_research/<role-slug>/<YYYY-MM-DD>-<stage>.md` для повторного использования аналитики и истории. Slug — латиница, kebab-case (`product-manager`, `senior-backend-python`).

---

## Логирование (выполнить после завершения исследования)

Прочитай `USER_EMAIL` из `.env`. Выполни через Supabase MCP (`execute_sql`, project `gjvwcdtfglupewcwzfhw`):

```sql
WITH ins AS (
  INSERT INTO tool_runs (
    id, tool_slug, status, trigger_type, triggered_by,
    items_processed, notes,
    started_at, finished_at, duration_sec
  ) VALUES (
    gen_random_uuid(), '/hh-research',
    '{status}', 'manual', 'user:{USER_EMAIL}',
    {vacancies_count}, 'role={role_slug}',
    now() - interval '{duration_sec} seconds', now(), {duration_sec}
  ) RETURNING tool_slug
)
UPDATE tools SET
  total_runs = total_runs + 1,
  last_run_at = now(),
  last_status = '{status}',
  updated_at = now()
WHERE slug = '/hh-research';
```

Где: `{status}` = `success` или `error`, `{vacancies_count}` = количество найденных вакансий, `{role_slug}` = slug роли, `{USER_EMAIL}` из `.env`, `{duration_sec}` = секунды.
