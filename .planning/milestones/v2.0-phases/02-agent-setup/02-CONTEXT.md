# Phase 2: Настройка агента - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Агент имеет полную базу знаний, понимает иерархию данных, и для каждого типа/периода отчёта знает точную структуру и глубину анализа. Монолитный playbook.md (1474 строки) разбит на модули (core + templates + rules), каждый тип отчёта имеет свой шаблон с toggle-заголовками, маркетинговый и funnel плейбуки интегрированы в общую систему модулей.

</domain>

<decisions>
## Implementation Decisions

### Структура модулей
- **D-01:** playbook.md разбивается по функции: core.md (бизнес-контекст, формулы, глоссарий, Data Quality правила), templates/ (1 файл на тип отчёта), rules.md (стратегии, антипаттерны, диагностика)
- **D-02:** marketing_playbook.md и funnel_playbook.md мержатся в соответствующие шаблоны templates/marketing_weekly.md, templates/marketing_monthly.md, templates/funnel_weekly.md
- **D-03:** Модули живут в `agents/oleg/playbooks/` — новая директория: `agents/oleg/playbooks/core.md`, `agents/oleg/playbooks/rules.md`, `agents/oleg/playbooks/templates/daily.md`, etc.
- **D-04:** Оркестратор собирает промпт: core.md + нужный template + релевантные rules → передаёт агенту. Агенты сами файлы не читают.
- **D-05:** Оригинальные playbook.md, marketing_playbook.md, funnel_playbook.md переименовываются в *_ARCHIVE.md — read-only архив, не загружаются агентами

### Структура отчётов
- **D-06:** 8 отдельных шаблонов, по одному на каждый тип отчёта: daily.md, weekly.md, monthly.md, marketing_weekly.md, marketing_monthly.md, funnel_weekly.md, dds.md, localization.md
- **D-07:** Toggle headings строгие — агент ОБЯЗАН использовать точные заголовки из шаблона (`## ▶ Название секции`). Валидация в Phase 3 может проверять совпадение секций
- **D-08:** ДДС и Локализация — шаблоны создаются на основе реальных отчётов из Notion (structure extracted). ДДС: Текущие остатки → Прогноз по месяцам → Детализация по группам → Кассовый разрыв. Локализация: Сводка по кабинетам → Динамика за неделю → Зональная разбивка → Топ моделей → Регионы
- **D-09:** ДДС и Локализация работают как data-driven отчёты (без глубокой LLM аналитики) — это намеренно, не нужно добавлять аналитические блоки

### Глубина анализа
- **D-10:** Одинаковые секции на всех уровнях (daily/weekly/monthly), но разная глубина содержания: daily=ключевые метрики и динамика кратко, weekly=тренды, взаимосвязи, расширенные гипотезы, monthly=P&L, план-факт, стратегия, полная юнит-экономика
- **D-11:** Гипотезы и юнит-экономика присутствуют на ВСЕХ уровнях (включая daily), но с разной детализацией
- **D-12:** Инструкции глубины встроены прямо в шаблон (inline), каждая секция помечена depth-маркером: `[depth: brief]`, `[depth: deep]`, `[depth: max]`

### Иерархия данных
- **D-13:** Создаётся отдельный `agents/oleg/playbooks/data-map.md` — карта связей tool → данные → секции отчёта
- **D-14:** data-map.md покрывает ВСЕ агенты (reporter, marketer, funnel), не только финансовые отчёты
- **D-15:** data-map.md используется в Phase 3 для pre-flight проверок: если tool не возвращает данные, агент знает какие секции пострадают

### Claude's Discretion
- Точная декомпозиция 19 секций playbook.md между core.md, rules.md и templates/
- Конкретные depth-маркеры для каждой секции каждого шаблона
- Формат data-map.md (таблица, YAML, или другой)
- Как обновить orchestrator/prompts.py для загрузки модулей вместо монолитного playbook

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Текущие плейбуки (источник контента для модулей)
- `agents/oleg/playbook.md` — монолитный плейбук финансового аналитика (1474 строк, 19 секций)
- `agents/oleg/marketing_playbook.md` — маркетинговый плейбук (270 строк)
- `agents/oleg/funnel_playbook.md` — плейбук воронки продаж (194 строки)

### Оркестратор (нужно обновить для модульной загрузки)
- `agents/oleg/orchestrator/prompts.py` — промпты с routing по task_type
- `agents/oleg/orchestrator/orchestrator.py` — маршрутизация агентов, загрузка playbook

### Агенты (потребители плейбуков)
- `agents/oleg/agents/reporter/prompts.py` — промпты reporter-агента
- `agents/oleg/agents/reporter/agent.py` — загрузка playbook в reporter
- `agents/oleg/agents/marketer/prompts.py` — промпты marketer-агента
- `agents/oleg/agents/marketer/agent.py` — загрузка marketing playbook
- `agents/oleg/SYSTEM.md` — системное описание агентов

### Эталонные отчёты в Notion
- Notion: "Сводка ДДС за 17-27 марта 2026" — эталон структуры ДДС отчёта
- Notion: "Анализ логистических расходов за 25-30 марта 2026" — эталон структуры локализации

### Проект
- `AGENTS.md` — правила проекта
- `.planning/REQUIREMENTS.md` — требования PLAY-01, PLAY-02, PLAY-03, VER-03

</canonical_refs>

<code_context>
## Existing Code Insights

### Текущая структура плейбуков
- `playbook.md`: 19 секций (бизнес-контекст, правила анализа, глоссарий, сведение маржи, Data Quality, формулы, ОПИУ, формат анализа, периоды, реклама, диагностика, принципы отчётов, ценовой анализ, action list, feedback, формат отчётов, план-факт, МойСклад, выкупы)
- `marketing_playbook.md`: целевые ДРР, нормы конверсии, маркетинговый анализ
- `funnel_playbook.md`: словарь метрик, маркетинговая воронка, бенчмарки

### Механизм загрузки плейбуков
- Orchestrator загружает playbook.md при инициализации и передаёт в промпт агента
- Routing по task_type: daily/weekly/monthly → reporter, marketing_* → marketer, funnel_* → funnel
- Секция 16 playbook.md уже содержит toggle heading правила (`## ▶ Название секции`)

### Типы отчётов (8 штук)
- Финансовые: daily, weekly, monthly
- Маркетинговые: marketing_weekly, marketing_monthly
- Воронка: funnel_weekly
- ДДС: finolog/dds (отдельный скрипт finolog-cron)
- Локализация: localization (отдельный скрипт)

</code_context>

<specifics>
## Specific Ideas

- ДДС и Локализация — data-driven отчёты без глубокой LLM аналитики, это намеренное решение. Шаблоны фиксируют текущую рабочую структуру из Notion.
- Гипотезы и юнит-экономика должны быть во ВСЕХ финансовых отчётах (включая daily), но с разной глубиной.
- Оригинальные плейбуки сохраняются как архив (*_ARCHIVE.md), не удаляются.

</specifics>

<deferred>
## Deferred Ideas

- Добавление LLM аналитики в ДДС/Локализацию — возможно в будущем, но не в Phase 2
- Автоматическое обновление шаблонов на основе feedback — Phase 5+ или backlog
- Интеграция data-map.md с pre-flight проверками — Phase 3 (Надёжность)

</deferred>

---

*Phase: 02-agent-setup*
*Context gathered: 2026-03-30*
