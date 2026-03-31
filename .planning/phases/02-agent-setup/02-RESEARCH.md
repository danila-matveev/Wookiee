# Phase 2: Настройка агента — Research

**Researched:** 2026-03-30
**Domain:** LLM Agent Prompt Architecture / Playbook Modularization
**Confidence:** HIGH

## Summary

Phase 2 is a content refactoring phase, not a code-heavy one. The work involves splitting a 1474-line monolithic `playbook.md` into a structured module hierarchy (`core.md`, `rules.md`, `templates/*.md`, `data-map.md`) and updating the orchestrator's prompt assembly logic to load the right modules per task type. All architectural decisions are locked in CONTEXT.md — there is no technology selection needed.

The primary risk is content loss during decomposition of the monolith. The playbook's 19 sections have deep cross-references and duplicate material that lives in both `playbook.md` and the already-in-code preamble sections of `reporter/prompts.py` and `marketer/prompts.py`. Understanding exactly which content lives where is the key research finding — the plan must reconcile the preamble (hardcoded in Python) vs. playbook content (loaded from file) to avoid double-loading or omission.

The secondary concern is the orchestrator prompt-assembly change. Currently `ReporterAgent.__init__` accepts a single `playbook_path: str`. After this phase it needs to accept (or be given) an assembled prompt string from the orchestrator, which must merge `core.md + template/{type}.md + rules.md`. This is a contained Python change.

**Primary recommendation:** The plan has two independent work streams — (1) content authoring (create the .md module files) and (2) code wiring (update orchestrator + agents to load modules). These can be parallelised across two plan files.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Структура модулей**
- D-01: playbook.md разбивается по функции: core.md (бизнес-контекст, формулы, глоссарий, Data Quality правила), templates/ (1 файл на тип отчёта), rules.md (стратегии, антипаттерны, диагностика)
- D-02: marketing_playbook.md и funnel_playbook.md мержатся в соответствующие шаблоны templates/marketing_weekly.md, templates/marketing_monthly.md, templates/funnel_weekly.md
- D-03: Модули живут в `agents/oleg/playbooks/` — новая директория: `agents/oleg/playbooks/core.md`, `agents/oleg/playbooks/rules.md`, `agents/oleg/playbooks/templates/daily.md`, etc.
- D-04: Оркестратор собирает промпт: core.md + нужный template + релевантные rules → передаёт агенту. Агенты сами файлы не читают.
- D-05: Оригинальные playbook.md, marketing_playbook.md, funnel_playbook.md переименовываются в *_ARCHIVE.md — read-only архив, не загружаются агентами

**Структура отчётов**
- D-06: 8 отдельных шаблонов, по одному на каждый тип отчёта: daily.md, weekly.md, monthly.md, marketing_weekly.md, marketing_monthly.md, funnel_weekly.md, dds.md, localization.md
- D-07: Toggle headings строгие — агент ОБЯЗАН использовать точные заголовки из шаблона (`## ▶ Название секции`)
- D-08: ДДС и Локализация — шаблоны создаются на основе реальных отчётов из Notion. ДДС: Текущие остатки → Прогноз по месяцам → Детализация по группам → Кассовый разрыв. Локализация: Сводка по кабинетам → Динамика за неделю → Зональная разбивка → Топ моделей → Регионы
- D-09: ДДС и Локализация работают как data-driven отчёты (без глубокой LLM аналитики) — это намеренно

**Глубина анализа**
- D-10: Одинаковые секции на всех уровнях (daily/weekly/monthly), но разная глубина содержания: daily=ключевые метрики и динамика кратко, weekly=тренды, взаимосвязи, расширенные гипотезы, monthly=P&L, план-факт, стратегия, полная юнит-экономика
- D-11: Гипотезы и юнит-экономика присутствуют на ВСЕХ уровнях (включая daily), но с разной детализацией
- D-12: Инструкции глубины встроены прямо в шаблон (inline), каждая секция помечена depth-маркером: `[depth: brief]`, `[depth: deep]`, `[depth: max]`

**Иерархия данных**
- D-13: Создаётся отдельный `agents/oleg/playbooks/data-map.md` — карта связей tool → данные → секции отчёта
- D-14: data-map.md покрывает ВСЕ агенты (reporter, marketer, funnel), не только финансовые отчёты
- D-15: data-map.md используется в Phase 3 для pre-flight проверок: если tool не возвращает данные, агент знает какие секции пострадают

### Claude's Discretion
- Точная декомпозиция 19 секций playbook.md между core.md, rules.md и templates/
- Конкретные depth-маркеры для каждой секции каждого шаблона
- Формат data-map.md (таблица, YAML, или другой)
- Как обновить orchestrator/prompts.py для загрузки модулей вместо монолитного playbook

### Deferred Ideas (OUT OF SCOPE)
- Добавление LLM аналитики в ДДС/Локализацию — возможно в будущем, но не в Phase 2
- Автоматическое обновление шаблонов на основе feedback — Phase 5+ или backlog
- Интеграция data-map.md с pre-flight проверками — Phase 3 (Надёжность)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLAY-01 | playbook.md разбит на модули (core + templates + rules) без потери бизнес-правил | Section mapping table below identifies exact destination for each of 19 playbook sections |
| PLAY-02 | Каждый тип отчёта загружает только релевантные модули плейбука | Orchestrator prompt-assembly pattern documented; playbook_path mechanism identified for modification |
| PLAY-03 | Глубина анализа настроена по периоду: daily=компактный, weekly=глубокий, monthly=максимальный | depth-marker inline pattern recommended; daily/weekly/monthly differences documented |
| VER-03 | Структура отчётов единообразна с toggle-заголовками | All section headers use `## ▶ …` (U+25B6); strict-headings rule captured in templates |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python pathlib | stdlib | File loading from `agents/oleg/playbooks/` | Already used in `reporter/prompts.py` and `marketer/prompts.py` |
| Markdown (.md) | — | Playbook module format | Already the format of all existing playbooks |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python f-string | stdlib | Inline module assembly in orchestrator | Assembling core + template + rules into single prompt string |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended Project Structure
```
agents/oleg/playbooks/
├── core.md                  # бизнес-контекст, формулы, глоссарий, Data Quality
├── rules.md                 # стратегии, антипаттерны, диагностика
├── data-map.md              # tool → данные → секции отчёта
└── templates/
    ├── daily.md             # финансовый дневной
    ├── weekly.md            # финансовый недельный
    ├── monthly.md           # финансовый месячный
    ├── marketing_weekly.md  # маркетинговый недельный
    ├── marketing_monthly.md # маркетинговый месячный
    ├── funnel_weekly.md     # воронка продаж
    ├── dds.md               # ДДС (finolog)
    └── localization.md      # Локализация WB

agents/oleg/
├── playbook.md              # → переименовать в playbook_ARCHIVE.md
├── marketing_playbook.md    # → переименовать в marketing_playbook_ARCHIVE.md
└── funnel_playbook.md       # → переименовать в funnel_playbook_ARCHIVE.md
```

### Pattern 1: Playbook Module Content Mapping

The 19 sections of `playbook.md` map to modules as follows:

| Section | Destination | Rationale |
|---------|-------------|-----------|
| 1. Бизнес-контекст и цели | `core.md` | Business context shared by all report types |
| 2. Правила анализа (5 рычагов, конверсии, юнит-экономика, цены, структура затрат, иерархия продуктов, drill-down) | `core.md` | Fundamental analysis rules cross-cutting all reports |
| 3. Глоссарий метрик | `core.md` | Universal reference |
| 4. Сведение изменения маржи | `core.md` | Formula/methodology shared across reports |
| 5. Протокол верификации и качества данных | `core.md` | Data quality rules apply everywhere |
| 6. Формулы (верифицированные) | `core.md` | Mathematical definitions |
| 7. ОПИУ (P&L) — правила отклонений | `core.md` | P&L framework used in monthly, referenced in weekly |
| 8. Формат анализа (full 11-section report structure with all subsections) | Split: section skeleton → `templates/daily.md`, `templates/weekly.md`, `templates/monthly.md` with `[depth: brief/deep/max]` markers on each subsection | This is the report structure definition |
| 9. Правила анализа по периодам | Inline into respective template files (section 9.1 → daily.md, 9.2 → weekly.md, 9.3 → monthly.md) | Period-specific rules belong in the template they govern |
| 10. Анализ рекламы и маркетинга (ДРР, связка реклама-трафик, паттерны) | `rules.md` | Cross-cutting rule that can be referenced by all templates |
| 11. Протокол глубокой диагностики Модели/SKU | `rules.md` | Diagnostic strategy, referenced when anomaly detected |
| 12. Принципы написания отчётов | `rules.md` | Style/anti-patterns for all report types |
| 13. Ценовой анализ и рекомендации | `rules.md` (strategy rules) + inline reference in templates where price section appears | Strategic rules; section structure inline in weekly/monthly templates |
| 14. Action list | `rules.md` | Output format rule |
| 15. Обратная связь и самопроверка | `rules.md` | Quality-check rule |
| 16. Формат отчётов (toggle headings, date format, top-conclusions rules) | `core.md` (format rules section) | Universal formatting rules |
| 17. План-факт | `core.md` (interpretation rules) + inline in templates (as section entry) | Tool interpretation shared; section appears in all financial reports |
| 18. МойСклад в оборачиваемости и ROI | `core.md` (interpretation rules) + inline in templates | Tool field definitions shared |
| 19. Усиление правила по выкупам | Inline per-template: daily template notes NO buyout analysis, weekly notes "with lag caveat", monthly notes "fully reliable" | Period-specific rule — belongs in each template |

**Note on Preamble Duplication:** `reporter/prompts.py::REPORTER_PREAMBLE` and `marketer/prompts.py::MARKETER_PREAMBLE` already contain hardcoded summaries of some playbook rules (e.g., выкупы, ДРР разбивка, GROUP BY LOWER). These preambles continue to serve as agent-specific role definitions. The playbook modules provide the detail behind each rule. After modularization, `core.md` will contain the full rules; preambles retain their role-framing function. Do NOT remove preamble content — it sets agent identity and quick-reference rules that must precede any large context.

### Pattern 2: Orchestrator Prompt Assembly

**Current mechanism (to be replaced):**
```python
# reporter/agent.py
def get_system_prompt(self) -> str:
    return get_reporter_system_prompt(self._playbook_path)

# reporter/prompts.py
def get_reporter_system_prompt(playbook_path: str = None) -> str:
    playbook_content = Path(playbook_path).read_text()
    return f"{REPORTER_PREAMBLE}\n\n---\n\n{playbook_content}"
```

**New mechanism (D-04):** Orchestrator assembles the prompt and passes it to the agent. The cleanest change with minimal blast radius:

```python
# In orchestrator.py or a new playbooks/loader.py helper
def build_agent_prompt(task_type: str, playbooks_dir: Path) -> str:
    core = (playbooks_dir / "core.md").read_text()
    template = (playbooks_dir / "templates" / TEMPLATE_MAP[task_type]).read_text()
    rules = (playbooks_dir / "rules.md").read_text()
    return f"{core}\n\n---\n\n{template}\n\n---\n\n{rules}"

TEMPLATE_MAP = {
    "daily": "daily.md",
    "weekly": "weekly.md",
    "monthly": "monthly.md",
    "marketing_weekly": "marketing_weekly.md",
    "marketing_monthly": "marketing_monthly.md",
    "funnel_weekly": "funnel_weekly.md",
    "dds": "dds.md",
    "localization": "localization.md",
    "custom": "weekly.md",  # fallback: custom maps to weekly depth
}
```

The agent constructors already accept `playbook_path: str`. The least-invasive change is to rename this parameter (or add a sibling) to accept a pre-assembled prompt string, or to call `build_agent_prompt` before constructing agents in the orchestrator's initialization path.

**Key constraint:** Funnel agent (`funnel/prompts.py`) is special — it has no playbook path at all and uses a minimal `FUNNEL_PREAMBLE`. `funnel_weekly.md` template + `core.md` fragments should be assembled similarly, but the funnel preamble must remain as agent identity.

### Pattern 3: Depth-Marker Inline Syntax

Per D-12, each section in a template file carries a depth marker. Recommended format:

```markdown
## ▶ Топ-выводы и действия
[depth: brief] 1-2 строки: главное изменение + одно действие. Без таблиц.
[depth: deep] 3-5 выводов с ₽ эффектом. Краткие таблицы допустимы.
[depth: max] 5+ выводов, полная таблица ₽ эффектов, гипотезы с подтверждением, матрица приоритетов.
```

The LLM reads the current report type from the instruction/task context and applies the matching depth level. This is a prompt instruction, not code logic.

### Pattern 4: data-map.md Format

Recommended tabular format (plain Markdown, easy for LLM to parse):

```markdown
## Tool → Data → Report Sections

| Tool | Agent | Data Returned | Used In Sections | Report Types |
|------|-------|--------------|-----------------|--------------|
| get_brand_finance | reporter | маржа, выручка, заказы, реклама | § Ключевые изменения, § Сведение ΔМаржи | daily, weekly, monthly |
| get_margin_levers | reporter | 5 рычагов маржи по каналам | § Сведение ΔМаржи (Reconciliation) | daily, weekly, monthly |
| get_plan_vs_fact | reporter, marketer | план, факт MTD, прогноз | § План-факт | weekly, monthly |
| get_advertising_stats | reporter | реклама внутр/внешн, cart_to_order | § Реклама WB/OZON, § Воронка | daily, weekly, monthly |
| get_model_breakdown | reporter | по-модельная декомпозиция, остатки, ROI | § Модели — драйверы/антидрайверы | daily, weekly, monthly |
| get_article_economics | reporter | profit_per_sale, ROMI, CAC per article | § Юнит-экономика артикулов | weekly, monthly |
| get_marketing_overview | marketer | воронка по каналам, средний чек | § Анализ по каналам, § Воронка | marketing_weekly, marketing_monthly |
| get_model_ad_efficiency | marketer | ROMI per model | § Чёрные дыры рекламы | marketing_weekly, marketing_monthly |
| get_search_keywords | marketer | ключевые слова по моделям | § Ключевые слова: генераторы и пустышки | marketing_weekly, marketing_monthly |
| build_funnel_report | funnel | готовый отчёт воронки | весь отчёт | funnel_weekly |
| get_article_unit_economics | funnel | водопад затрат на единицу | § Экономика артикулов | funnel_weekly |
```

Phase 3 will use this map to implement pre-flight checks. The map must be complete (all tools from `reporter/tools.py`, `marketer/tools.py`, `funnel/tools.py`) by end of Phase 2.

### Anti-Patterns to Avoid

- **Content duplication between core.md and templates:** Core defines the rule once; templates reference it by name (e.g., "apply 5-lever margin decomposition per core.md §2"). Templates should NOT re-state the full rule text.
- **Removing preamble content from Python files:** `REPORTER_PREAMBLE` and `MARKETER_PREAMBLE` serve as agent role declarations, not playbook content. They must remain. The risk is the planner treating them as redundant.
- **Flat depth markers (all sections same depth in daily):** The daily template must explicitly suppress full P&L, full unit-economics table, model strategy matrix — these sections either have `[depth: brief]` with a one-liner or are marked as skip for daily.
- **Forgetting funnel_weekly depth:** The funnel agent does not use depth markers — its prompt is minimal and delegates entirely to `build_funnel_report`. The funnel_weekly.md template should document this special behavior.
- **Incomplete data-map.md:** If any tool is missing from the map, Phase 3 pre-flight checks cannot cover it.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Prompt assembly | Custom Jinja/template engine | Python f-strings + `Path.read_text()` | Already in use, zero dependencies, sufficient for the need |
| Content validation (no sections missing) | Custom section-checker | This is Phase 3 scope (REL-03, REL-05) | Defer to Phase 3 |
| Playbook hot-reload | File watcher / reload mechanism | Read on agent init (current pattern) | Over-engineering; playbooks only change with code deploy |

---

## Common Pitfalls

### Pitfall 1: Preamble vs Playbook Content Overlap
**What goes wrong:** Reporter preamble (`REPORTER_PREAMBLE` in `reporter/prompts.py`) already contains abbreviated rules (GROUP BY LOWER, выкупы, ДРР разбивка, формат дат). If `core.md` repeats these verbatim, the assembled prompt has redundant text. If core.md omits them, the preamble remains the only source.
**Why it happens:** The preamble was written as a standalone prompt when there was no modular system. Now it's a partial overlap.
**How to avoid:** Preamble = agent role + quick-ref rules (keep as-is). core.md = full authoritative definitions. Preamble rules can stay abbreviated; core.md provides the complete versions.
**Warning signs:** If the assembled prompt is >15,000 tokens, something is duplicated.

### Pitfall 2: Section 8 (Формат анализа) — 800+ Lines of Embedded Report Structure
**What goes wrong:** playbook.md section 8 is not just rules — it is the actual detailed report structure for ALL report types, with full table schemas. It's currently embedded as one block.
**Why it happens:** This was originally a unified template. Now it needs to be split into per-type templates.
**How to avoid:** Section 8 is the primary source for `templates/daily.md`, `templates/weekly.md`, `templates/monthly.md`. Read `reporter/prompts.py::REPORTER_PREAMBLE` lines 55-203 to see the section skeleton — it's already been partially extracted there. The template files should be derived from what's in prompts.py (the current production version) not from playbook.md section 8 (which may be slightly older).
**Warning signs:** If daily.md and weekly.md have identical section lists, depth markers were not applied.

### Pitfall 3: marketing_playbook.md and funnel_playbook.md Already Contain Section Structures
**What goes wrong:** `marketing_playbook.md` sections 1-9 define rules (targets, formulas, strategy). The section structure for `marketing_weekly.md` template is in `marketer/prompts.py::MARKETER_PREAMBLE` lines 52-139, not in the playbook file.
**Why it happens:** Same split as reporter — preamble holds report structure, playbook holds business rules.
**How to avoid:** Content for `marketing_weekly.md` template comes from `marketer/prompts.py`, not from `marketing_playbook.md`. Marketing playbook content goes to `core.md` (formulas/targets) and `rules.md` (strategy rules).

### Pitfall 4: DDS and Localization Sections Have No Current Code Templates
**What goes wrong:** There is no `dds.md` or `localization.md` template structure in existing Python prompts. These report types have separate scripts (`finolog-cron`, `services/wb_localization/`) that do not use the oleg orchestrator.
**Why it happens:** ДДС and Локализация were built outside the main oleg agent system.
**How to avoid:** Templates for dds.md and localization.md must be authored fresh, based on real Notion reports (D-08). The plan must include a task to extract structure from Notion before writing the template. Since these are data-driven (D-09), templates focus on section headings and field mappings, not analytical depth markers.

### Pitfall 5: Orchestrator Needs to Know task_type Before Agent Init
**What goes wrong:** Currently agents are initialized at startup with a fixed `playbook_path`. For module assembly, the orchestrator needs `task_type` to pick the right template — but `task_type` is known only at `run_chain()` time.
**Why it happens:** Monolith playbook = one path fits all. Modular = path varies per task.
**How to avoid:** Two options: (a) lazy prompt assembly — build the prompt in `get_system_prompt()` by reading `task_type` from the orchestrator context; (b) pass assembled prompt string at `run_chain()` time and thread it through to agent `analyze()`. Option (a) is cleaner but requires agents to know task_type. The cleanest change: add a `playbooks_dir` init param + `task_type` param to `analyze()`, and assemble inside `analyze()` before the tool loop starts. Alternatively: assemble in orchestrator's `_decide_next_step` and pass as part of `instruction` prefix (but this risks token bloat in instruction).

**Recommended approach:** Add a `PlaybookLoader` helper class in `agents/oleg/playbooks/loader.py` with `load(task_type) -> str`. Orchestrator calls it before handing instruction to agent. Agent `get_system_prompt()` returns preamble only; full context is passed via a new `extra_context` parameter to `analyze()`.

---

## Code Examples

### Current Playbook Loading (reporter)
```python
# agents/oleg/agents/reporter/prompts.py — current production code
def get_reporter_system_prompt(playbook_path: str = None) -> str:
    playbook_file = Path(playbook_path) if playbook_path else _DEFAULT_PLAYBOOK
    playbook_content = playbook_file.read_text(encoding="utf-8")
    return f"{REPORTER_PREAMBLE}\n\n---\n\n{playbook_content}"
```

### Proposed PlaybookLoader (new file)
```python
# agents/oleg/playbooks/loader.py
from pathlib import Path

_PLAYBOOKS_DIR = Path(__file__).parent

TEMPLATE_MAP = {
    "daily": "daily.md",
    "weekly": "weekly.md",
    "monthly": "monthly.md",
    "marketing_weekly": "marketing_weekly.md",
    "marketing_monthly": "marketing_monthly.md",
    "funnel_weekly": "funnel_weekly.md",
    "dds": "dds.md",
    "localization": "localization.md",
    "custom": "weekly.md",
}

def load(task_type: str) -> str:
    """Assemble core + template + rules for given task_type."""
    core = (_PLAYBOOKS_DIR / "core.md").read_text(encoding="utf-8")
    template_name = TEMPLATE_MAP.get(task_type, "weekly.md")
    template = (_PLAYBOOKS_DIR / "templates" / template_name).read_text(encoding="utf-8")
    rules = (_PLAYBOOKS_DIR / "rules.md").read_text(encoding="utf-8")
    return f"{core}\n\n---\n\n{template}\n\n---\n\n{rules}"
```

### Updated Orchestrator Usage
```python
# In orchestrator's run_chain() before building chain_context
from agents.oleg.playbooks.loader import load as load_playbook
assembled_playbook = load_playbook(task_type)
# Pass to agent via instruction prefix or new analyze() parameter
```

### Depth Marker Convention in Templates
```markdown
## ▶ Юнит-экономика артикулов (Top/Bottom)
<!-- [depth: brief] Для ТОП A/B модели: единственная таблица 3 строки. Нет детализации по ROMI. -->
<!-- [depth: deep] Для каждой A/B модели ТОП-3 и BOTTOM-3. ROMI < 100% → убыточный флаг. -->
<!-- [depth: max] Полная таблица ТОП-3/BOTTOM-3 по ВСЕМ моделям. profit_per_sale < 0 → критический алерт. Отдельная подсекция с action list. -->
```

---

## Runtime State Inventory

This phase is content authoring + Python code edits. No runtime state is impacted.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — playbook content is files, not DB records | None |
| Live service config | None — playbook paths are code config, not external service config | None |
| OS-registered state | None | None |
| Secrets/env vars | None — playbook path can be relative, no env vars involved | None |
| Build artifacts | None — .md files, no compiled artifacts | None |

---

## Environment Availability

Step 2.6: SKIPPED — phase is code/content-only changes with no external dependencies beyond Python stdlib.

---

## Validation Architecture

`workflow.nyquist_validation` is not explicitly set to false in `.planning/config.json` — validation section is included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (assumed from project; no config file found in agents/oleg/) |
| Config file | None found — Wave 0 gap |
| Quick run command | `python -m pytest tests/agents/oleg/ -x -q` |
| Full suite command | `python -m pytest tests/agents/oleg/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLAY-01 | All 19 playbook sections are present across core.md + templates/* + rules.md | unit (content check) | `python -m pytest tests/agents/oleg/playbooks/test_module_coverage.py -x` | ❌ Wave 0 |
| PLAY-02 | PlaybookLoader returns correct template for each of 8 task_types | unit | `python -m pytest tests/agents/oleg/playbooks/test_loader.py -x` | ❌ Wave 0 |
| PLAY-03 | Each financial template contains depth markers for brief/deep/max | unit (content check) | `python -m pytest tests/agents/oleg/playbooks/test_depth_markers.py -x` | ❌ Wave 0 |
| VER-03 | All section headings in all 8 templates use `## ▶` toggle format | unit (content check) | `python -m pytest tests/agents/oleg/playbooks/test_toggle_headings.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/agents/oleg/playbooks/ -x -q`
- **Per wave merge:** `python -m pytest tests/agents/oleg/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/agents/oleg/playbooks/__init__.py` — test package
- [ ] `tests/agents/oleg/playbooks/test_module_coverage.py` — PLAY-01: verifies no playbook section is lost
- [ ] `tests/agents/oleg/playbooks/test_loader.py` — PLAY-02: verifies 8 task_type → file mappings
- [ ] `tests/agents/oleg/playbooks/test_depth_markers.py` — PLAY-03: verifies depth markers in daily/weekly/monthly
- [ ] `tests/agents/oleg/playbooks/test_toggle_headings.py` — VER-03: verifies `## ▶` format in all 8 templates

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `agents/oleg/agents/reporter/prompts.py` — current prompt assembly mechanism (confirmed)
- Direct code inspection: `agents/oleg/agents/marketer/prompts.py` — current marketer prompt (confirmed)
- Direct code inspection: `agents/oleg/orchestrator/orchestrator.py` — orchestrator chain flow (confirmed)
- Direct content inspection: `agents/oleg/playbook.md` (19 sections, header structure confirmed via grep)
- Direct content inspection: `agents/oleg/marketing_playbook.md` (9 sections, confirmed)
- Direct content inspection: `agents/oleg/funnel_playbook.md` (9 sections, confirmed)

### Secondary (MEDIUM confidence)
- `agents/oleg/agents/reporter/agent.py` — constructor pattern for playbook_path parameter (confirmed)
- `agents/oleg/agents/marketer/agent.py` — same pattern (confirmed)
- `.planning/phases/02-agent-setup/02-CONTEXT.md` — locked decisions (primary constraint source)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all technology already in production
- Architecture: HIGH — direct code inspection confirms current mechanism; proposed changes are minimal extensions
- Content mapping: MEDIUM — mapping of 19 playbook sections to modules is a judgment call at Claude's discretion; the planner must make final assignment decisions
- Pitfalls: HIGH — all identified from direct code inspection, not inference

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable codebase, low churn risk)
