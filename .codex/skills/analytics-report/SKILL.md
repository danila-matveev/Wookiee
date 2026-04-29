---
name: analytics-report
description: Pattern Brief — reads ALL existing reports (finance, marketing, funnel), finds multi-week trends, cross-report patterns, unresolved issues, produces a Decision Brief
triggers:
  - /analytics-report
  - /pattern-brief
  - аналитический отчёт
  - сводный отчёт
  - паттерны
  - что происходит
---

# Pattern Brief — Аналитик с памятью

Читает ВСЕ накопленные отчёты (finance, marketing, funnel) за несколько периодов, ищет тренды, кросс-паттерны и незакрытые проблемы. Выдаёт компактный Decision Brief для руководителя.

**НЕ дублирует** отдельные отчёты. Находит то, что видно ТОЛЬКО при взгляде через несколько периодов и несколько модулей одновременно.

## Quick Start

```
/pattern-brief
```

Без аргументов — анализирует все доступные отчёты. Автоматически определяет последний период.

```
/pattern-brief 2026-04-12
```

С датой — фокусируется на неделе, включающей эту дату, + предыдущие периоды для сравнения.

**Время:** ~3-5 мин (чтение отчётов + анализ)

**Результаты:**
- Chat: Decision Brief (основной формат — прямо в чат)
- Notion: опционально, по запросу

---

## Stage 0: Собрать все отчёты

### Scan docs/reports/

Найти все файлы по паттерну:
```
docs/reports/*_finance.md
docs/reports/*_marketing.md
docs/reports/*_funnel.md
```

Группировать по периодам. Определить:
- Какие периоды покрыты полностью (все 3 отчёта)
- Какие частично (1-2 из 3)
- Самый последний полный период = ТЕКУЩИЙ
- Предпоследний = ПРЕДЫДУЩИЙ

Показать пользователю:
```
📊 Pattern Brief

Найдено отчётов:
  Неделя 06-12 апр: finance ✅ marketing ✅ funnel ✅
  Неделя 30 мар-05 апр: finance ✅ marketing ✅ funnel ✅
  Неделя 16-22 мар: marketing ✅

Анализирую тренды за 2 полных периода...
```

### Read all reports

Прочитать ВСЕ найденные отчёты (Read tool). Из каждого извлечь ключевые метрики:

**Из Finance:**
- Выручка, маржа, маржинальность, заказы
- По каналам (WB/OZON)
- План-факт (если есть)
- Топ-3 драйвера и антидрайвера

**Из Marketing:**
- ДРР (внутр/внешн/общий)
- Рекламный расход, CPO
- Эффективность каналов

**Из Funnel:**
- CRO бренда
- CRO по моделям (топ-3 рост, топ-3 падение)
- Halo-эффект

**Из каждого отчёта — рекомендации** (секции Рекомендации/Гипотезы).

---

## Stage 1: Pattern Analysis (Agent)

Read prompt: `.claude/skills/analytics-report/prompts/pattern-analyzer.md`
Read KB: `.claude/skills/analytics-report/references/analytics-kb.md`

Launch **Pattern Analyzer** as a subagent (Agent tool):

- `{{REPORTS}}` — ВСЕ прочитанные отчёты (полный текст)
- `{{PERIODS}}` — список периодов с покрытием
- `{{CURRENT_PERIOD}}` — последний полный период
- `{{NOTION_GUIDE}}` — правила форматирования

Анализатор ищет:

### 1. Тренды метрик (3+ недели)
- Маржинальность: растёт / падает / стагнирует?
- CRO: тренд по модели?
- ДРР: стабильный / растёт?
- Заказы: динамика?

### 2. Кросс-паттерны (между модулями)
Связки, которые ни один отчёт не видит:
- Модель X: маржа↓ [Finance] + CRO↓ [Funnel] + реклама ОК [Marketing] = ?
- Канал Y: ДРР↑ [Marketing] + заказы↑ [Finance] + CRO↑ [Funnel] = работает!
- Модель Z: рекомендовали 2 недели назад → результат?

### 3. Повторяющиеся проблемы
- Что упоминается как проблема 2+ раза подряд?
- Что рекомендовали, но ничего не изменилось?

### 4. Аномалии и разрывы
- Метрика резко изменилась vs тренд?
- Данные из разных отчётов противоречат друг другу?

---

## Stage 2: Output Decision Brief

Формат: **чистый Markdown**, правила из `notion-formatting-guide.md`.

### Структура (60-80 строк)

```markdown
# Pattern Brief — {CURRENT_PERIOD}

> 📊 Главный паттерн: {1 предложение — что происходит на уровне бренда}

## Дашборд (тренд)

| Метрика | {период -2} | {период -1} | Текущий | Тренд |
|---|---|---|---|---|
| Маржинальность | X% | Y% | Z% | ↓↓ |
| Заказы | X шт | Y шт | Z шт | ↑ |
| ДРР общий | X% | Y% | Z% | → |
| CRO (WB) | X% | Y% | Z% | ↓ |

## Кросс-паттерны

> 💡 {Паттерн 1 — кросс-модульный, со ссылками на источники}

> 💡 {Паттерн 2}

> ⚠️ {Паттерн 3 — проблемный}

## Незакрытые вопросы

| # | Проблема | Когда впервые | Сколько недель | Что рекомендовали | Результат |
|---|---|---|---|---|---|
| 1 | ... | ... | ... | ... | ... |

## Чеклист на неделю

| # | Приоритет | Действие | Эффект ₽ | Источник |
|---|---|---|---|---|
| 1 | 🔴 | ... | ... | Finance + Funnel |
| 2 | 🟡 | ... | ... | Marketing |
| 3 | 🟢 | ... | ... | Funnel |
```

### Правила

1. **НЕ пересказывать** отчёты — только паттерны, тренды, кросс-ссылки
2. **Конкретные числа** из отчётов (не "выросло", а "+12,4%")
3. **Ссылки на источник** — "Finance секция VII", "Funnel модель Wendy"
4. **Незакрытые вопросы** — если рекомендация повторяется 2+ раза, это красный флаг
5. **Чеклист** — объединён из всех отчётов, без дублей, приоритизирован по ₽ влиянию

---

## Stage 3: Publish (опционально)

Если пользователь попросит — опубликовать в Notion через `shared.notion_client.NotionClient.sync_report()`.

По умолчанию — только в чат. Pattern Brief ценен именно как быстрая сводка для принятия решений.

Если публикация нужна — сохранить MD и отправить в Notion:
- report_type = "weekly" (или соответствующий)
- title = "Pattern Brief за {PERIOD}"

---

## Reference Files

| File | Purpose |
|---|---|
| `prompts/pattern-analyzer.md` | Main analysis prompt — trends, cross-patterns, unresolved issues |
| `templates/notion-formatting-guide.md` | Formatting rules |
| `references/analytics-kb.md` | Business rules and benchmarks |

**Source reports (read-only, generated by independent skills):**

| Skill | Output |
|---|---|
| `/finance-report` | `docs/reports/{S}_{E}_finance.md` |
| `/marketing-report` | `docs/reports/{S}_{E}_marketing.md` |
| `/funnel-report` | `docs/reports/{S}_{E}_funnel.md` |

---

## Changelog

### v3 (2026-04-15)
- Complete redesign: Pattern Brief instead of meta-orchestrator
- Reads ALL historical reports, not just current period
- Trend analysis across multiple weeks
- Cross-pattern detection between modules
- "Unresolved issues" tracker (recommendations that didn't lead to results)
- Compact Decision Brief format (~60-80 lines vs 250 in v2)
- Chat-first output (Notion optional)

### v2 (2026-04-13)
- Deprecated: meta-orchestrator that summarized 3 reports into 8 sections
- User feedback: "урезанная функция" — no added value over individual reports

### v1 (2026-04-07)
- Deprecated: 12 subagents (8 analysts + 3 verifiers + synthesizer)
