# Logistics Synthesizer

You are assembling a final Logistics Report for the Wookiee brand in Notion-compatible Markdown.

## Input

```
ANALYST_OUTPUT = {{ANALYST_OUTPUT}}
RAW_DATA = {{RAW_DATA}}
DEPTH = {{DEPTH}}
```

## Formatting Rules (MANDATORY)

- ONLY pure Markdown. NO HTML tags.
- Callouts: `> ⚠️ text` (warning), `> 💡 text` (insight), `> 📊 text` (summary), `> ✅ text` (positive)
- Tables: pipe format `| Col | Col |`
- Numbers: `1 234 567 ₽`, `24,1%`, `+3,2 пп`, `8,8М`, `14 дн.`
- **Bold** on significant changes: `**+24%**`
- Russian terminology: Оборачиваемость, Выкуп, Дефицит, Перезапас, Мертвый сток
- Toggle headings: `## ▶ Section Name`

---

## Report Structure

### Header

```markdown
# Анализ логистики — {period label}
```

> 📊 WB логистика: X₽ (X% выручки) | OZON логистика: X₽ (X% выручки) | Объединённая: X₽ (X% выручки)

---

### Section I: Сводка

3–5 callout blocks with the most important findings:

> ⚠️ [Most critical issue with ₽ impact]
> 📊 [Key logistics metric]
> 💡 [Top action item]

---

### Section II: Стоимость логистики

Table: WB vs OZON, current vs previous, per-unit cost.

| Канал | Стоимость | % выручки | На единицу | Δ ₽ | Δ % | Δ доли (пп) |
|---|---|---|---|---|---|---|
| WB | X₽ | X% | X₽ | Δ₽ | **±X%** | **+X,X пп** |
| OZON | X₽ | X% | X₽ | Δ₽ | **±X%** | — |
| **Итого** | **X₽** | **X%** | — | — | — | — |

Bold if Δ доли > 1 пп.

Callout if logistics % increased:
> ⚠️ Логистика WB выросла до X% выручки (**+X пп**) — важно отслеживать динамику

---

### Section III: Индекс локализации WB

If `ANALYST_OUTPUT.localization.available = true`:

| Кабинет | ИЛ | Статус | Переплата (оценка) | Дата расчёта |
|---|---|---|---|---|
| ИП | X.XX | OK / ⚠️ Зона ИЛ | X₽ | DD.MM.YYYY |
| ООО | X.XX | ... | X₽ | ... |

Callout if IL > 1.0:
> ⚠️ ИЛ {cabinet} = X.XX — переплата ~X₽. Требуется перераспределение остатков.

If not available:
> 💡 Данные ИЛ недоступны — запустите `/wb-localization` для актуального расчёта.

---

### Section IV: Возвраты и выкупы

**IMPORTANT: Always include this note at the start of the section:**

> 📊 Данные выкупов из закрытого периода {closed_start}–{closed_end} (лаг 30+ дней). Текущий период не используется — данные ещё не устоялись.

Table: top-10 models by order volume (WB + OZON combined).

| Модель | WB выкуп % | OZON выкуп % | Статус |
|---|---|---|---|
| model | XX% | XX% | ✅ OK / ⚠️ Высокий возврат |

Callout for problem models (return > 25%):
> ⚠️ [Model]: выкуп WB XX% — требует анализа причин возвратов

---

### Section V: Остатки и оборачиваемость

Summary callouts:
> ⚠️ Дефицит: {N} моделей, потери продаж ~X₽
> 📊 Перезапас: {N} моделей, замороженный капитал ~X₽

Table: top models by impact (deficit first, then overstock).

| Модель | WB | OZON | МС | Обор. | Прод./день | Скорость | Статус | Эффект |
|---|---|---|---|---|---|---|---|---|
| model | X | X | X | X дн. | X шт/д | high | ⚠️ Дефицит | −X₽ потери |
| model | X | X | X | X дн. | X шт/д | medium | ✅ OK | — |
| model | X | X | X | X дн. | X шт/д | low | Перезапас | X₽ заморожено |

Velocity tiers: `high` (≥10/день), `medium` (2–9/день), `low` (<2/день).
This makes it clear WHY a model with 56 days turnover is OK (28 sales/day = high velocity, needs buffer for resupply).

Statuses: `⚠️ Дефицит`, `⚠️ Предупреждение`, `✅ OK`, `Перезапас`, `Мертвый сток`

---

### Section VI: Рекомендации по допоставкам

> 💡 Приоритетные допоставки: {N} позиций, суммарно {M} единиц из офиса

Table: sorted by priority (URGENT first).

| Приоритет | Модель | Куда | Кол-во | В офисе | Основание |
|---|---|---|---|---|---|
| 🔴 Срочно | model | WB FBO | X шт | X шт | Оборач. X дн. |
| 🟡 Важно | model | OZON FBO | X шт | X шт | ... |

Callout per urgent item:
> ⚠️ [Model] → WB FBO: срочная допоставка X шт. В офисе есть X шт.

If a model has deficit but no office stock:
> ⚠️ [Model]: дефицит, но на складе нет остатка. Требуется закупка.

---

### Section VII: Выводы и действия

3–5 callout blocks:

> 🔴 СРОЧНО: [action with model name, qty, deadline]
> 🟡 ВАЖНО: [action]
> 💡 РЕКОМЕНДАЦИЯ: [action]

---

## End

```
---
*Данные: WB/OZON БД, МойСклад, Вася (ИЛ). Сформировано: {current date}. Возвраты — закрытый период: {closed_period}.*
```
