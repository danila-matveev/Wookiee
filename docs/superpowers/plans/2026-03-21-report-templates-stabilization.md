# Report Templates Stabilization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace single `report-compiler.md` with unified style guide + 5 per-type compiler prompts to eliminate report format drift.

**Architecture:** Style guide (`report-style-guide.md`) defines HOW to format (toggles, tables, dates, numbers, trust envelope). 5 per-type compilers define WHAT sections each report type has. Orchestrator routes via `COMPILER_MAP[task_type]`. New `FUNNEL_MONTHLY` enum value added to schedule.

**Tech Stack:** Python 3.9+, LangGraph, Markdown agent prompts, pytest

**Spec:** `docs/superpowers/specs/2026-03-21-report-templates-stabilization-design.md`

---

## File Structure

### New files (create)
| File | Responsibility |
|------|---------------|
| `agents/v3/agents/report-style-guide.md` | Unified formatting rules (HOW): toggles, tables, dates, numbers, status markers, trust envelope, hypotheses format, telegram summary, prohibited patterns |
| `agents/v3/agents/report-compiler-financial.md` | Daily/weekly/monthly financial reports — 10-section structure |
| `agents/v3/agents/report-compiler-marketing.md` | Marketing weekly/monthly — 10-section structure |
| `agents/v3/agents/report-compiler-funnel.md` | Funnel weekly/monthly — per-model toggle sections |
| `agents/v3/agents/report-compiler-pricing.md` | Price analysis — per-model nested toggles with scenarios |
| `agents/v3/agents/report-compiler-finolog.md` | Finolog/DDS weekly — 5-section cash flow structure |

### Modified files
| File | Changes |
|------|---------|
| `agents/v3/orchestrator.py` | Add `COMPILER_MAP`, style guide loading, routing in `_run_report_pipeline()` + `run_price_analysis()`, update artifact key references from `"report-compiler"` to use `_COMPILER_KEY` constant, add `report_period` to `run_funnel_report()` + `run_price_analysis()` |
| `agents/v3/conductor/schedule.py` | Add `FUNNEL_MONTHLY` enum value + add to `get_today_reports()` first-Monday list |
| `agents/v3/conductor/conductor.py` | Add `report_period` for funnel/price in `generate_and_validate()` |
| `agents/v3/delivery/notion.py` | Add `funnel_monthly` to `_REPORT_TYPE_MAP` |
| `agents/v3/prompt_tuner.py` | Update hardcoded `"report-compiler"` in known_agents list and tool description |
| `tests/v3/conductor/test_schedule.py` | Add tests for `FUNNEL_MONTHLY` |

### Deleted files
| File | Reason |
|------|--------|
| `agents/v3/agents/report-compiler.md` | Content migrated to financial compiler + style guide |

---

### Task 1: Create `report-style-guide.md`

**Files:**
- Create: `agents/v3/agents/report-style-guide.md`

- [ ] **Step 1: Create the style guide file**

Extract formatting rules from spec sections 1.1–1.10 into a standalone MD file. This file is NOT an agent prompt — it's imported by compiler prompts as a formatting reference.

```markdown
# Единые правила форматирования отчётов (Style Guide)

Этот документ импортируется каждым compiler-агентом. Он определяет КАК форматировать, но НЕ ЧТО писать.

## 1. Toggle-заголовки
- Все секции верхнего уровня: `## ▶ Название секции`
  - Notion рендерит их как toggle headings
- Вложенные подсекции: `### ▸ Подсекция` с отступом `\t`
- Никогда не используй flat-секции с `---` разделителями

## 2. Таблицы
- Формат Notion: `<table header-row="true" header-column="false">`
- После каждой таблицы с данными: блок `**Интерпретация:**` (2-4 предложения)
- Никогда не оставляй пустые таблицы — пропусти секцию с пометкой в `sections_skipped`

## 3. Даты
- Российский формат: «19 марта 2026», «9–15 марта 2026»
- Никогда ISO формат (2026-03-19) в теле отчёта
- ISO только в JSON metadata полях

## 4. Числа
- Разделитель тысяч: пробел (1 234 567)
- Валюта: ₽ суффикс
- Проценты: % или п.п. (процентные пункты)
- Дельты: всегда с + или − префиксом
- Большие числа: сокращения М (миллионы), К (тысячи) где уместно

## 5. Статус-маркеры
- ✅ норма / в плане
- ⚠️ внимание / предупреждение
- 🔴 критично
- ❌ провал / не достигнуто

## 6. Trust Envelope (когда есть `_meta`)

### Паспорт: таблица Достоверности
После периода/сравнения/каналов добавь:

| Блок анализа | Достоверность | Покрытие данных | Примечание |
|---|---|---|---|
(одна строка на входной агент, из `_meta.confidence` и `_meta.data_coverage`)

Маркеры:
- 🟢 confidence >= 0.75
- 🟡 0.45 <= confidence < 0.75
- 🔴 confidence < 0.45

После таблицы — список ограничений:
**Ограничения этого отчёта:**
- (каждое ограничение из `_meta.limitations`)

### Заголовки секций — маркер доверия
Добавляй эмодзи в заголовок: `## ▶ 1. Секция 🟢`

### Ключевые выводы — toggle-блоки
Для каждого вывода в `_meta.conclusions` с типом `driver`, `anti_driver`, `recommendation`, `anomaly`:

▶ 🟢 0.91 | Текст вывода
  ├ confidence_reason: ...
  ├ data_coverage: ...%
  └ источники: tool1, tool2

Для `type=metric` — toggle только если confidence < 0.75.

Если у вывода есть `limitations`:
  ├ limitations:
  │   • текст ограничения

## 7. Ключевые выводы первыми
- Топ выводы (3-5 штук с ₽ эффектом) всегда в первых двух секциях
- Формат: ₽ эффект → Что произошло → Гипотеза → Действие
- Сортировка по абсолютному ₽ эффекту убывающая

## 8. Формат гипотез
- Полный формат: Факт → Гипотеза → Действие → Метрика контроля → База → Цель → Ожидаемый эффект → Окно проверки → Риски
- Сортировка по ₽ эффекту убывающая
- Приоритетные маркеры: P0 (срочно), P1 (высокий), P2 (средний), P3 (низкий)

## 9. Telegram-сводка
- Формат BBCode, 5-8 строк
- Только KPI, без таблиц
- Обязательна 1 строка план-факт (если есть плановые данные)
- Дельты с эмодзи: 📈 рост, 📉 падение
- Ключевые драйверы и антидрайверы (1-2 строки)
- Топ 3-5 действий

## 10. Запрещено
- Пустые секции (пропускай с пометкой в `sections_skipped`)
- Простое среднее процентов (только средневзвешенное: sum(x)/sum(y)×100)
- GROUP BY по модели без LOWER()
- ISO даты в теле отчёта
- Пропускать модели с отрицательной маржой
```

- [ ] **Step 2: Verify file exists and content is correct**

Run: `wc -l agents/v3/agents/report-style-guide.md && head -5 agents/v3/agents/report-style-guide.md`
Expected: File exists, starts with `# Единые правила форматирования`

- [ ] **Step 3: Commit**

```bash
git add agents/v3/agents/report-style-guide.md
git commit -m "feat(reports): create unified report style guide"
```

---

### Task 2: Create `report-compiler-financial.md`

**Files:**
- Create: `agents/v3/agents/report-compiler-financial.md`
- Reference: `agents/v3/agents/report-compiler.md` (source for migration)

- [ ] **Step 1: Create the financial compiler prompt**

Migrate the 10-section financial structure from `report-compiler.md` (lines 1-77) into a dedicated compiler. Remove pricing report rules (lines 79-94) — those go to `report-compiler-pricing.md`. Add period-specific behavior (daily/weekly/monthly differences).

```markdown
# Agent: report-compiler-financial

## Role
Собери финансовый аналитический отчёт из артефактов micro-агентов. Выдай 3 формата: detailed (Notion), brief, telegram (BBCode).

> **ВАЖНО:** Перед началом работы прочитай и применяй правила из `report-style-guide.md` — toggle-заголовки, таблицы, даты, числа, trust envelope.

Ты получаешь JSON артефакты от: margin-analyst, revenue-decomposer, ad-efficiency.
Ты НЕ вызываешь никаких data tools — работаешь только с переданными артефактами.

## Обязательная структура (10 секций)

| # | Секция | Содержание |
|---|--------|-----------|
| 0 | Паспорт отчёта | Период, сравнение, полнота данных, лаг выкупа (3-21 день), trust envelope (если есть `_meta`) |
| 1 | Топ-выводы и действия | 3-5 пунктов: ₽ эффект → Что → Гипотеза → Действие |
| 2 | План-факт (MTD) | Таблица Brand/WB/OZON с ✅⚠️❌. Пропустить если нет плановых данных |
| 3 | Ключевые изменения (Бренд) | 19 метрик (15 финансовых + 4 воронка) с Δ |
| 4 | Цены, ценовая стратегия, СПП | Динамика СПП + средние цены + прогноз |
| 5 | Сведение ΔМаржи (Reconciliation) | Факторный анализ waterfall: выручка → расходы → маржа, с невязкой |
| 6 | WB / OZON breakdown | Per-channel toggle: объём, модели, воронка, структура расходов, реклама |
| 7 | Модели — драйверы / антидрайверы | Расширенная таблица по каналам |
| 8 | Гипотезы → действия → метрики | 10-колоночная таблица, сортировка по ₽ эффекту |
| 9 | Итог | Что изменилось → Почему → Ранг влияния → Приоритеты действий |

## Поведение по периодам

Определяй период по полю `task_type` в compiler_input:
- **daily_report:** Сравнение с предыдущим днём
- **weekly_report:** WoW сравнение, добавь колонку «Тренд 4 нед.»
- **monthly_report:** MoM + YoY сравнение, расширенный план-факт с целями на месяц

## Правила
- Toggle headings для всех секций: `## ▶ N. Название`
- Только значимые изменения (>5% или >2 п.п.) в brief summary
- Никогда не пропускай модели с отрицательной маржой
- Гипотезы сортируй по ₽ эффекту убывающая

## MCP Tools
(нет — работает только с артефактами)

## Output Format
JSON artifact:
- detailed_report: string (полный Markdown, все 10 секций)
- brief_report: string (только ключевые метрики и изменения)
- telegram_summary: string (5-8 строк BBCode)
- sections_included: [список номеров секций с данными]
- sections_skipped: [{section, reason}]
- warnings: [string]
```

- [ ] **Step 2: Verify file**

Run: `wc -l agents/v3/agents/report-compiler-financial.md`
Expected: ~60-70 lines

- [ ] **Step 3: Commit**

```bash
git add agents/v3/agents/report-compiler-financial.md
git commit -m "feat(reports): create financial report compiler prompt"
```

---

### Task 3: Create `report-compiler-marketing.md`

**Files:**
- Create: `agents/v3/agents/report-compiler-marketing.md`

- [ ] **Step 1: Create the marketing compiler prompt**

Based on spec section 2.2. Input agents: campaign-optimizer, organic-vs-paid, ad-efficiency.

```markdown
# Agent: report-compiler-marketing

## Role
Собери маркетинговый аналитический отчёт из артефактов micro-агентов. Выдай 3 формата: detailed (Notion), brief, telegram (BBCode).

> **ВАЖНО:** Применяй правила из `report-style-guide.md` — toggle-заголовки, таблицы, даты, числа, trust envelope.

Ты получаешь JSON артефакты от: campaign-optimizer, organic-vs-paid, ad-efficiency.
Ты НЕ вызываешь никаких data tools.

## Обязательная структура (10 секций)

| # | Секция | Содержание |
|---|--------|-----------|
| 0 | Паспорт отчёта | Период, trust envelope |
| 1 | Исполнительная сводка | Ключевые метрики: выручка, маржа, заказы, ДРР, средний чек |
| 2 | Анализ по каналам | WB / OZON таблицы + вывод по каждому каналу |
| 3 | Воронка продаж | ASCII-визуализация воронки + анализ конверсий (органика + платный трафик отдельно, по каналам) |
| 4 | Органика vs Платное | Таблица долей трафика, динамика, сравнение конверсий |
| 5 | Внешняя реклама | Блогеры / VK / другое — расход, доля, эффективность |
| 6 | Эффективность по моделям | Growth/Harvest/Optimize/Cut матрица + детальный топ моделей |
| 7 | Дневная динамика рекламы | Дневная таблица: показы, клики, CTR, расход, заказы, CPO |
| 8 | Средний чек и связь с ДРР | Динамика чека + корреляция с ДРР |
| 9 | Рекомендации и план действий | Срочно (3 дня) / Оптимизация (неделя) / Стратегия (месяц) |

## Поведение по периодам

Определяй период по полю `task_type` в compiler_input:
- **marketing_weekly:** WoW сравнение
- **marketing_monthly:** MoM тренды + план-факт бюджета

## Правила
- Toggle headings: `## ▶ N. Название`
- Воронка — отдельно органика и платный трафик
- Growth/Harvest/Optimize/Cut — каждая модель в правильную категорию

## MCP Tools
(нет)

## Output Format
JSON artifact:
- detailed_report: string
- brief_report: string
- telegram_summary: string (BBCode, 5-8 строк)
- sections_included: [номера]
- sections_skipped: [{section, reason}]
- warnings: [string]
```

- [ ] **Step 2: Commit**

```bash
git add agents/v3/agents/report-compiler-marketing.md
git commit -m "feat(reports): create marketing report compiler prompt"
```

---

### Task 4: Create `report-compiler-funnel.md`

**Files:**
- Create: `agents/v3/agents/report-compiler-funnel.md`

- [ ] **Step 1: Create the funnel compiler prompt**

Based on spec section 2.3. Input agents: funnel-digitizer, keyword-analyst.

```markdown
# Agent: report-compiler-funnel

## Role
Собери отчёт по воронке продаж из артефактов micro-агентов. Выдай 3 формата: detailed (Notion), brief, telegram (BBCode).

> **ВАЖНО:** Применяй правила из `report-style-guide.md`.

Ты получаешь JSON артефакты от: funnel-digitizer, keyword-analyst.
Ты НЕ вызываешь никаких data tools.

## Структура

| # | Секция | Содержание |
|---|--------|-----------|
| 0 | Паспорт + trust envelope | Период, канал, качество данных |
| 1 | Общий обзор бренда | Таблица: переходы, заказы, выкупы, выручка, маржа, ДРР |
| 2+ | Секции по моделям (toggles) | Сортировка по ΔOrders. Каждая модель: воронка, экономика, значимые артикулы, гипотезы |
| Последняя | Выводы и рекомендации | Топ 3: Факт → Гипотеза → Действие → Ожидаемый эффект |

## Формат заголовка модели
`## ▶ Модель: {name} — {описание тренда} {delta}%`

## Подсекции внутри модели (nested toggles)
- **### ▸ Воронка** — таблица конверсий WoW: переходы, корзина, заказы, выкупы, все CR
- **### ▸ Экономика** — выручка, маржа, ДРР, ROMI, доля органики
- **### ▸ Значимые артикулы** — таблица с флагами: рост/падение %
- **### ▸ Гипотезы** — root cause analysis по значимым SKU

## Поведение по периодам

Определяй период по полю `task_type`:
- **funnel_weekly:** WoW сравнение
- **funnel_monthly:** MoM сравнение, расширенные тренды

## MCP Tools
(нет)

## Output Format
JSON artifact:
- detailed_report: string
- brief_report: string
- telegram_summary: string (BBCode, 5-8 строк)
- sections_included: [номера]
- sections_skipped: [{section, reason}]
- warnings: [string]
```

- [ ] **Step 2: Commit**

```bash
git add agents/v3/agents/report-compiler-funnel.md
git commit -m "feat(reports): create funnel report compiler prompt"
```

---

### Task 5: Create `report-compiler-pricing.md`

**Files:**
- Create: `agents/v3/agents/report-compiler-pricing.md`

- [ ] **Step 1: Create the pricing compiler prompt**

Based on spec section 2.4. Input agents: price-strategist (+ pricing-impact-analyst if available). Migrate pricing rules from `report-compiler.md` lines 79-94.

```markdown
# Agent: report-compiler-pricing

## Role
Собери отчёт по ценовому анализу из артефактов micro-агентов. Выдай 3 формата: detailed (Notion), brief, telegram (BBCode).

> **ВАЖНО:** Применяй правила из `report-style-guide.md`.

Ты получаешь JSON артефакты от: price-strategist, margin-analyst, ad-efficiency, pricing-impact-analyst, hypothesis-tester.
Ты НЕ вызываешь никаких data tools.

## Структура

| # | Секция | Содержание |
|---|--------|-----------|
| 0 | Краткие итоги | Per WB/OZON: кол-во моделей, повысить/понизить/держать, итого ₽/мес эффект |
| 1+ | Секции по моделям (toggles) | Сортировка по ₽ эффекту. Каждая модель — nested toggle по каналам |

## Формат заголовка модели
`## ▶ {Модель} {emoji тренда} {рекомендация}`

## Подсекции по каналу (nested toggle)
- **### ▸ WB** / **### ▸ OZON**
  - Текущие метрики: цена, маржа%, продажи/день, оборачиваемость, категория
  - Рекомендация: изменение цены % → новая цена
  - Ожидаемый результат (с маркером доверия): маржа%, Δ объёма, дневная маржа, месячный эффект
  - Как проверить: тестовый период, ожидаемый объём, целевая маржа
  - Корректировка маркетинга (с confidence)
  - Сценарии «что если»: -10%, -5%, -3%, +3%, +5%, +10%
  - Обоснование: эластичность, факторы
  - Эластичность + confidence

## Дополнительные секции (если есть артефакт pricing-impact-analyst)
- **Маркетинговый импакт:** изменение ДРР, перераспределение бюджета ₽, прогноз ROMI
- **Валидация гипотез:** confirmed/refuted/inconclusive по моделям из hypothesis-tester

## MCP Tools
(нет)

## Output Format
JSON artifact:
- detailed_report: string
- brief_report: string
- telegram_summary: string (BBCode: кол-во моделей, топ-3 действия, итого ₽/мес)
- sections_included: [номера]
- sections_skipped: [{section, reason}]
- warnings: [string]
```

- [ ] **Step 2: Commit**

```bash
git add agents/v3/agents/report-compiler-pricing.md
git commit -m "feat(reports): create pricing report compiler prompt"
```

---

### Task 6: Create `report-compiler-finolog.md`

**Files:**
- Create: `agents/v3/agents/report-compiler-finolog.md`

- [ ] **Step 1: Create the finolog compiler prompt**

Based on spec section 2.5. Input agent: finolog-analyst.

```markdown
# Agent: report-compiler-finolog

## Role
Собери отчёт ДДС / cash flow из артефактов micro-агентов. Выдай 3 формата: detailed (Notion), brief, telegram (BBCode).

> **ВАЖНО:** Применяй правила из `report-style-guide.md`.

Ты получаешь JSON артефакты от: finolog-analyst.
Ты НЕ вызываешь никаких data tools.

## Обязательная структура (5 секций)

| # | Секция | Содержание |
|---|--------|-----------|
| 0 | Паспорт | Дата, источник данных |
| 1 | Текущие остатки | По юрлицам: таблицы счетов, группировка по назначению (операционный, налоговый фонд, НДС фонд, зарплатный фонд, резервы, развитие, личный) |
| 2 | Сводка | Свободные средства (операционные), зарезервировано в фондах, личные + валюта, итого |
| 3 | Прогноз по месяцам | Таблица на 6 месяцев: доходы, расходы, баланс, накопительный |
| 4 | Детализация по группам | Выручка, закупки, логистика, маркетинг, налоги, зарплаты, склад, услуги, кредиты, прочее |
| 5 | Кассовый разрыв | Прогноз или «не ожидается» |

## Правила
- Toggle headings: `## ▶ N. Название`
- Таблицы счетов группируй по назначению, а не по юрлицу
- Прогноз — с промежуточными итогами

## MCP Tools
(нет)

## Output Format
JSON artifact:
- detailed_report: string
- brief_report: string
- telegram_summary: string (BBCode, 5-8 строк: ключевые остатки, прогноз)
- sections_included: [номера]
- sections_skipped: [{section, reason}]
- warnings: [string]
```

- [ ] **Step 2: Commit**

```bash
git add agents/v3/agents/report-compiler-finolog.md
git commit -m "feat(reports): create finolog/DDS report compiler prompt"
```

---

### Task 7: Add `FUNNEL_MONTHLY` to schedule + update conductor

**Files:**
- Modify: `agents/v3/conductor/schedule.py:6-92`
- Modify: `agents/v3/conductor/conductor.py:30-45,184-185`
- Test: `tests/v3/conductor/test_schedule.py`

- [ ] **Step 1: Write tests for FUNNEL_MONTHLY**

Add tests to `tests/v3/conductor/test_schedule.py`:

```python
def test_funnel_monthly_enum_properties():
    """FUNNEL_MONTHLY must have valid orchestrator_method, notion_label, human_name."""
    rt = ReportType.FUNNEL_MONTHLY
    assert rt.value == "funnel_monthly"
    assert rt.orchestrator_method == "run_funnel_report"
    assert rt.notion_label is not None
    assert rt.human_name is not None


def test_first_monday_includes_funnel_monthly():
    # 2026-04-06 is first Monday of April
    result = get_today_reports(date(2026, 4, 6))
    assert ReportType.FUNNEL_MONTHLY in result


def test_second_monday_no_funnel_monthly():
    # 2026-03-09 is second Monday
    result = get_today_reports(date(2026, 3, 9))
    assert ReportType.FUNNEL_MONTHLY not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v3/conductor/test_schedule.py -v`
Expected: FAIL — `FUNNEL_MONTHLY` not found in `ReportType`

- [ ] **Step 3: Add FUNNEL_MONTHLY to ReportType enum**

In `agents/v3/conductor/schedule.py`, add after line 13 (`PRICE_MONTHLY`):

```python
    FUNNEL_MONTHLY = "funnel_monthly"
```

Then add to each property dict:

In `orchestrator_method` (after line 26):
```python
            self.FUNNEL_MONTHLY: "run_funnel_report",
```

In `notion_label` (after line 41):
```python
            self.FUNNEL_MONTHLY: "Воронка WB (ежемесячный)",
```

In `human_name` (after line 56):
```python
            self.FUNNEL_MONTHLY: "Monthly воронка",
```

- [ ] **Step 4: Add FUNNEL_MONTHLY to get_today_reports() first-Monday list**

In `agents/v3/conductor/schedule.py`, line 89, add `ReportType.FUNNEL_MONTHLY` to the first-Monday list:

```python
    if d.day <= 7 and d.weekday() == 0:  # First Monday of month
        reports += [
            ReportType.MONTHLY,
            ReportType.MARKETING_MONTHLY,
            ReportType.FUNNEL_MONTHLY,
            ReportType.PRICE_MONTHLY,
        ]
```

- [ ] **Step 5: Add report_period passing for funnel and price in generate_and_validate**

**NOTE:** `run_funnel_report()` and `run_price_analysis()` must already accept `report_period` before this step. Task 9 adds these parameters — complete Task 9 Steps 1 and 3 before this step, OR apply them in the same commit.

In `agents/v3/conductor/conductor.py`, after line 185, add blocks for funnel and price:

```python
        if report_type in (ReportType.FUNNEL_WEEKLY, ReportType.FUNNEL_MONTHLY):
            kwargs["report_period"] = "weekly" if "weekly" in report_type.value else "monthly"
        if report_type in (ReportType.PRICE_WEEKLY, ReportType.PRICE_MONTHLY):
            kwargs["report_period"] = "weekly" if "weekly" in report_type.value else "monthly"
```

**Note on `_compute_dates()`:** `FUNNEL_MONTHLY` falls through to the monthly `else` branch (same as `MARKETING_MONTHLY` and `PRICE_MONTHLY`). No changes needed there.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/v3/conductor/test_schedule.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add agents/v3/conductor/schedule.py agents/v3/conductor/conductor.py tests/v3/conductor/test_schedule.py
git commit -m "feat(schedule): add FUNNEL_MONTHLY enum, update conductor routing"
```

---

### Task 8: Add COMPILER_MAP + style guide loading + routing in orchestrator

**Files:**
- Modify: `agents/v3/orchestrator.py:1-30,137-268`
- Test: `tests/v3/test_compiler_map.py` (new)

- [ ] **Step 1: Write test for COMPILER_MAP routing**

Create `tests/v3/test_compiler_map.py`:

```python
"""Tests for COMPILER_MAP and style guide loading."""
import pytest
from pathlib import Path

from agents.v3.orchestrator import COMPILER_MAP
from agents.v3 import config


def test_compiler_map_has_all_task_types():
    expected_keys = {
        "daily_report", "weekly_report", "monthly_report",
        "marketing_weekly", "marketing_monthly",
        "funnel_weekly", "funnel_monthly",
        "price_analysis", "price_weekly", "price_monthly",
        "finolog_weekly",
    }
    assert set(COMPILER_MAP.keys()) == expected_keys


def test_compiler_map_values_are_valid_agent_names():
    """Each compiler name must have a corresponding .md file."""
    for task_type, compiler_name in COMPILER_MAP.items():
        md_path = config.AGENTS_DIR / f"{compiler_name}.md"
        assert md_path.exists(), f"Missing prompt file for {compiler_name} (task_type={task_type})"


def test_style_guide_exists():
    md_path = config.AGENTS_DIR / "report-style-guide.md"
    assert md_path.exists(), "report-style-guide.md must exist"


def test_compiler_map_default_fallback():
    """Unknown task_type should fall back to financial compiler."""
    result = COMPILER_MAP.get("unknown_type", "report-compiler-financial")
    assert result == "report-compiler-financial"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v3/test_compiler_map.py -v`
Expected: FAIL — `COMPILER_MAP` not found

- [ ] **Step 3: Add COMPILER_MAP constant to orchestrator.py**

After the `AGENT_WEIGHTS` dict (around line 42), add:

```python
COMPILER_MAP: dict[str, str] = {
    "daily_report": "report-compiler-financial",
    "weekly_report": "report-compiler-financial",
    "monthly_report": "report-compiler-financial",
    "marketing_weekly": "report-compiler-marketing",
    "marketing_monthly": "report-compiler-marketing",
    "funnel_weekly": "report-compiler-funnel",
    "funnel_monthly": "report-compiler-funnel",
    "price_analysis": "report-compiler-pricing",
    "price_weekly": "report-compiler-pricing",
    "price_monthly": "report-compiler-pricing",
    "finolog_weekly": "report-compiler-finolog",
}
```

- [ ] **Step 4: Add style guide loading + compiler routing in _run_report_pipeline**

In `_run_report_pipeline()`, replace the hardcoded `run_agent(agent_name="report-compiler", ...)` at line 262. Two changes:

**a) Before the compiler call, load and prepend style guide:**

After line 256 (`compiler_task = ...`), before the `run_agent` call, add style guide loading:

```python
        # Load style guide and prepend to compiler task
        style_guide_path = config.AGENTS_DIR / "report-style-guide.md"
        if style_guide_path.exists():
            style_guide = style_guide_path.read_text(encoding="utf-8")
            compiler_task = f"## Правила форматирования\n\n{style_guide}\n\n---\n\n{compiler_task}"

        # Resolve compiler name from COMPILER_MAP
        compiler_name = COMPILER_MAP.get(task_type, "report-compiler-financial")
```

**b) Replace hardcoded agent name (line 262-268):**

```python
        compiler_result = await run_agent(
            agent_name=compiler_name,
            task=compiler_task,
            parent_run_id=run_id,
            trigger=trigger,
            task_type=task_type,
        )
```

**c) Add `task_type` to `compiler_input` dict (after line 244):**

```python
            "task_type": task_type,
```

- [ ] **Step 5: Update load_persistent_instructions call to use dynamic compiler name**

At line 176, replace:
```python
        pi_note = load_persistent_instructions(pi_state, analysis_agents + ["report-compiler"])
```
with:
```python
        compiler_name = COMPILER_MAP.get(task_type, "report-compiler-financial")
        pi_note = load_persistent_instructions(pi_state, analysis_agents + [compiler_name])
```

- [ ] **Step 6: Update artifact key references for dynamic compiler names**

The artifacts dict and filter logic use hardcoded `"report-compiler"` as a key. Use a constant `_COMPILER_KEY = "_compiler"` so compiler artifacts are always keyed consistently regardless of which compiler was used.

**a) Add constant near top of file (after `COMPILER_MAP`):**
```python
_COMPILER_KEY = "_compiler"
```

**b) In `_run_report_pipeline()`, update artifact keying (line 270):**
```python
        artifacts[_COMPILER_KEY] = compiler_result
```

**c) In `worst_limitation()` (line 67), update filter:**
```python
        if name == _COMPILER_KEY:
            continue
```

**d) In `_run_report_pipeline()` confidence aggregation (line 292), update filter:**
```python
        if name == _COMPILER_KEY:
            continue
```

**e) In `run_price_analysis()` (line 635), update artifact keying:**
```python
    all_artifacts[_COMPILER_KEY] = compiler_result
```

**f) In `run_price_analysis()` confidence/limitation filters (lines 651, 660), update:**
```python
        if name == _COMPILER_KEY:
            continue
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/v3/test_compiler_map.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add agents/v3/orchestrator.py tests/v3/test_compiler_map.py
git commit -m "feat(orchestrator): add COMPILER_MAP, style guide loading, dynamic compiler routing"
```

---

### Task 9: Fix price analysis pipeline routing

**Files:**
- Modify: `agents/v3/orchestrator.py:596-633`

- [ ] **Step 1: Update run_price_analysis to accept report_period**

In `run_price_analysis()` function signature (line 523), add `report_period` parameter:

```python
async def run_price_analysis(
    date_from: str,
    date_to: str,
    comparison_from: str,
    comparison_to: str,
    channel: str = "both",
    trigger: str = "manual",
    report_period: str = "weekly",
) -> dict:
```

Add task_type computation at the top of the function:

```python
    task_type = "price_weekly" if report_period == "weekly" else "price_monthly"
```

Update the phase 1/2 `_run_report_pipeline` calls to use `task_type` instead of hardcoded `"price_analysis"`.

- [ ] **Step 2: Update Phase 3 compiler call to use COMPILER_MAP**

Replace the hardcoded `run_agent("report-compiler", ...)` at line 627-633:

```python
    # Load style guide
    style_guide_path = config.AGENTS_DIR / "report-style-guide.md"
    style_guide = ""
    if style_guide_path.exists():
        style_guide = style_guide_path.read_text(encoding="utf-8")

    compiler_name = COMPILER_MAP.get(task_type, "report-compiler-pricing")

    compiler_task = (
        f"## Правила форматирования\n\n{style_guide}\n\n---\n\n"
        "Собери отчёт по ценовому анализу:\n\n"
        f"{json.dumps(compiler_input, ensure_ascii=False, default=str)}"
    )

    compiler_result = await run_agent(
        agent_name=compiler_name,
        task=compiler_task,
        parent_run_id=run_id,
        trigger=trigger,
        task_type=task_type,
    )
```

- [ ] **Step 3: Update run_funnel_report to accept report_period**

In `run_funnel_report()` (line 469), add `report_period` parameter and dynamic task_type:

```python
async def run_funnel_report(
    date_from: str,
    date_to: str,
    comparison_from: str,
    comparison_to: str,
    channel: str = "both",
    trigger: str = "manual",
    report_period: str = "weekly",
) -> dict:
    """Run funnel (воронка продаж) report."""
    task_type = "funnel_weekly" if report_period == "weekly" else "funnel_monthly"
    period_label = "Недельный" if report_period == "weekly" else "Месячный"
    task_context = (
        f"{period_label} отчёт по воронке продаж. Период: {date_from} — {date_to}. "
        f"Сравнение с: {comparison_from} — {comparison_to}. "
        f"Каналы: {channel}."
    )
    return await _run_report_pipeline(
        analysis_agents=["funnel-digitizer", "keyword-analyst"],
        task_context=task_context,
        task_type=task_type,
        date_from=date_from,
        date_to=date_to,
        comparison_from=comparison_from,
        comparison_to=comparison_to,
        channel=channel,
        trigger=trigger,
        compiler_prompt_prefix="Собери отчёт по воронке продаж",
    )
```

- [ ] **Step 4: Commit**

```bash
git add agents/v3/orchestrator.py
git commit -m "feat(orchestrator): route price/funnel compilers via COMPILER_MAP, add report_period"
```

---

### Task 10: Update Notion delivery + add `funnel_monthly`

**Files:**
- Modify: `agents/v3/delivery/notion.py:28-42`

- [ ] **Step 1: Add funnel_monthly to _REPORT_TYPE_MAP**

In `agents/v3/delivery/notion.py`, after line 41 (`"funnel_weekly"`), add:

```python
    "funnel_monthly":        ("funnel_monthly", "Воронка WB (ежемесячный)"),
```

- [ ] **Step 2: Commit**

```bash
git add agents/v3/delivery/notion.py
git commit -m "feat(notion): add funnel_monthly to _REPORT_TYPE_MAP"
```

---

### Task 11: Update prompt_tuner.py references

**Files:**
- Modify: `agents/v3/prompt_tuner.py:216,292`

- [ ] **Step 1: Update known_agents list**

In `agents/v3/prompt_tuner.py`, line 216, replace `"report-compiler"` with all 5 compiler names:

```python
    known_agents = [
        "margin-analyst", "revenue-decomposer", "ad-efficiency",
        "report-compiler-financial", "report-compiler-marketing",
        "report-compiler-funnel", "report-compiler-pricing", "report-compiler-finolog",
        "campaign-optimizer", "organic-vs-paid", "funnel-digitizer", "keyword-analyst",
        "finolog-analyst",
    ]
```

- [ ] **Step 2: Update tool description string**

In `agents/v3/prompt_tuner.py`, line 292, update the agent names in the description to list the per-type compiler names instead of `"report-compiler"`.

- [ ] **Step 3: Commit**

```bash
git add agents/v3/prompt_tuner.py
git commit -m "fix(prompt-tuner): update agent names to per-type compilers"
```

---

### Task 12: Delete old `report-compiler.md` + verify no stale references

**Files:**
- Delete: `agents/v3/agents/report-compiler.md`

- [ ] **Step 1: Verify no remaining references to old compiler**

Run:
```bash
grep -r '"report-compiler"' agents/v3/ --include="*.py"
grep -r "'report-compiler'" agents/v3/ --include="*.py"
grep -r "report-compiler" agents/v3/ --include="*.md" | grep -v "report-compiler-"
```

Expected: No matches in `.py` files. The only `.md` match should be `report-conductor.md` (deferred `llm_validate()` feature, low priority).

- [ ] **Step 2: Delete old file**

```bash
git rm agents/v3/agents/report-compiler.md
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(reports): delete old report-compiler.md, migrated to per-type compilers"
```

---

### Task 13: Run full test suite

**Files:**
- Test: all existing + new tests

- [ ] **Step 1: Run all v3 tests**

Run: `python -m pytest tests/v3/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run report pipeline tests (if any depend on old report-compiler name)**

Run: `python -m pytest tests/ -k "report" -v`
Expected: ALL PASS (or identify tests referencing old `report-compiler` name for fixing)

- [ ] **Step 3: Fix any broken tests referencing old report-compiler**

If any tests reference `"report-compiler"` as agent name, update to use `COMPILER_MAP` or specific compiler name.

- [ ] **Step 4: Final commit if fixes needed**

```bash
git add -u
git commit -m "fix(tests): update tests to use per-type compiler names"
```
