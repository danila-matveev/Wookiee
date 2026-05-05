# /hh-research — HR-ресёрч на HH.ru

**Запуск:** `/hh-research` (или фразы из триггеров: «проанализируй вакансии», «рынок hh», «исследуй компанию на hh», «улучши мою вакансию»).

## Что делает

Закрывает три HR-сценария через MCP-сервер `headhunter` (10 публичных инструментов API hh.ru):

1. **Market scan** — собирает 100-200 актуальных вакансий по должности, агрегирует зарплатную вилку (p25/p50/p75), ключевые навыки, форматы работы, регионы, бенефиты.
2. **Vacancy refinement** — берёт черновик пользовательской вакансии, находит топ-аналогов, выдаёт конкретные правки по 5 разрезам (зарплата / обязанности / требования / бенефиты / формат).
3. **Employer research** — собирает профиль компании: индустрия, активные вакансии, частота найма за 7/30/90 дней, технологический стек, зарплатная политика vs рынок.
4. *(опционально, требует OAuth)* свои резюме и история откликов на HH.

## Что MCP НЕ умеет

Поиск чужих резюме на HH.ru недоступен через публичный API — это требует employer-аккаунта с платной подпиской. Скилл явно перенаправит запрос «найди кандидата» на сценарий market scan + employer research (где конкуренты сейчас активно нанимают на эту роль).

## Параметры

Скилл интерактивный — на старте задаёт через AskUserQuestion: сценарий → должность/keywords → регион → уровень опыта → формат работы.

## Результат

Markdown-отчёт сохраняется в `data/hh_research/<role-slug>/<YYYY-MM-DD>-<stage>.md` + краткое резюме в чате.

## Зависимости

- **MCP-сервер:** `headhunter` (Python, репо `gmen1057/headhunter-mcp-server`, клонирован в `/Users/danilamatveev/Projects/headhunter-mcp-server/`).
- **Wrapper:** `scripts/run_hh_mcp.sh` — загружает HH-credentials из `.env` и запускает Python-сервер из venv.
- **Конфиг:** запись `headhunter` в `.mcp.json` (без секретов — они в `.env`).
- **Credentials в `.env`:**
  - `HH_CLIENT_ID`, `HH_CLIENT_SECRET`, `HH_APP_TOKEN` — обязательны для всех публичных tools.
  - `HH_REDIRECT_URI` — нужен только для OAuth flow (Stage 4).
  - `HH_ACCESS_TOKEN`, `HH_REFRESH_TOKEN` — заполняются после прохождения OAuth (опционально).

## Получение credentials

1. Открыть https://dev.hh.ru/admin → авторизоваться через свой аккаунт hh.ru.
2. Создать новое приложение (тип «Авторизация по `client_credentials` + OAuth»).
3. Скопировать `Client ID`, `Client Secret`, `App Token` в Wookiee `.env`.
4. Перезапустить Claude Code, чтобы MCP-сервер подхватил переменные.

API HH.ru для соискателей **бесплатный**, регистрация приложения тоже.

## Файлы

- `.claude/skills/hh-research/SKILL.md` — главные инструкции для Claude.
- `.claude/skills/hh-research/prompts/{market_scan,vacancy_refine,employer_research}.md` — детальные руководства для каждого сценария.
- `.claude/skills/hh-research/templates/market_summary.md` — шаблон выдачи market scan.
- `scripts/run_hh_mcp.sh` — wrapper-скрипт запуска MCP.
- `/Users/danilamatveev/Projects/headhunter-mcp-server/` — клонированный MCP-сервер с venv.
