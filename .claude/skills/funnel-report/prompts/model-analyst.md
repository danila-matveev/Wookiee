# Model Analyst — Per-Model Funnel Sections

> Роль: аналитик воронки по моделям бренда Wookiee WB.
> Задача: сгенерировать toggle-секцию для КАЖДОЙ модели ("Продается" + "Запуск") с 4 подсекциями: Воронка, Экономика, Значимые артикулы, Анализ.
> Формат: **Notion Enhanced Markdown** — `<table>` с цветами строк, `<callout>` блоки.
> Стилистический эталон: Notion page 33658a2bd58781ef8e8cec583dad16de (Q4 vs Q1)

---

## Инструкции

**Перед анализом** прочитай Knowledge Base: `.claude/skills/analytics-report/references/analytics-kb.md`.
Прочитай Notion formatting guide: `.claude/skills/analytics-report/templates/notion-formatting-guide.md`.

---

## Входные данные

- `{{FINDINGS}}` — результат Wave A (MODEL_FINDINGS с funnel + economics + significant_articles)
- `{{DIAGNOSTICS}}` — результат Wave B (FUNNEL_DIAGNOSTICS с cause, confidence, effect)
- `{{HYPOTHESES}}` — результат Wave C (FUNNEL_HYPOTHESES с actions и TOP-3)
- `{{RAW_DATA}}` — JSON: traffic.wb_by_model, advertising, finance by model, sku_statuses
- `{{DEPTH}}` / `{{PERIOD_LABEL}}` / `{{PREV_PERIOD_LABEL}}`

---

## Список моделей

Из `sku_statuses`: ВСЕ модели со статусом "Продается" или "Запуск".
ЗАПРЕЩЕНО придумывать модели. Если модели нет в sku_statuses — НЕ включать.

Сортировка: по убыванию выручки (крупные модели первыми).

---

## Шаблон секции модели

Для КАЖДОЙ модели генерируй:

```markdown
## Модель: {Name} — {headline} {toggle="true"}
	### Воронка
	<table fit-page-width="true" header-row="true" header-column="true">
	<tr color="blue_bg">
	<td>Метрика</td>
	<td>Текущая</td>
	<td>Прошлая</td>
	<td>Δ</td>
	</tr>
	<tr>
	<td>Переходы</td>
	<td>{n}</td>
	<td>{n}</td>
	<td>{+/-n}%</td>
	</tr>
	<tr>
	<td>Корзина</td>
	<td>{n}</td>
	<td>{n}</td>
	<td>{+/-n}%</td>
	</tr>
	<tr>
	<td>Заказы</td>
	<td>{n}</td>
	<td>{n}</td>
	<td>{+/-n}%</td>
	</tr>
	<tr>
	<td>Выкупы\*</td>
	<td>{n}</td>
	<td>{n}</td>
	<td>{+/-n}%</td>
	</tr>
	<tr>
	<td>CR переход→корзина</td>
	<td>{n}%</td>
	<td>{n}%</td>
	<td>{+/-n} п.п.</td>
	</tr>
	<tr>
	<td>CR корзина→заказ</td>
	<td>{n}%</td>
	<td>{n}%</td>
	<td>{+/-n} п.п.</td>
	</tr>
	<tr color="green_bg или red_bg — по направлению CRO">
	<td>**CRO (переход→заказ)**</td>
	<td>**{n}%**</td>
	<td>**{n}%**</td>
	<td>**{+/-n} п.п.**</td>
	</tr>
	<tr>
	<td>CRP (переход→выкуп)\*</td>
	<td>{n}%</td>
	<td>{n}%</td>
	<td>{+/-n} п.п.</td>
	</tr>
	</table>
	\*Данные по выкупам неполные (лаг 3-21 день)
	### Экономика
	<table fit-page-width="true" header-row="true" header-column="true">
	<tr color="blue_bg">
	<td>Метрика</td>
	<td>Значение</td>
	</tr>
	<tr>
	<td>Выручка</td>
	<td>{n} ₽</td>
	</tr>
	<tr>
	<td>Маржа</td>
	<td>{n} ₽ ({n}%)</td>
	</tr>
	<tr>
	<td>ДРР</td>
	<td>{n}% (пред. {n}%)</td>
	</tr>
	<tr>
	<td>ROMI</td>
	<td>{n}%</td>
	</tr>
	<tr>
	<td>Средний чек</td>
	<td>{n} ₽</td>
	</tr>
	</table>
	### Значимые артикулы
	<table fit-page-width="true" header-row="true" header-column="true">
	<tr color="blue_bg">
	<td>Артикул</td>
	<td>Заказы</td>
	<td>Выручка</td>
	<td>Маржа</td>
	<td>ДРР</td>
	</tr>
	<tr>
	<td>{article}</td>
	<td>{n}</td>
	<td>{n} ₽</td>
	<td>{n} ₽ ({n}%)</td>
	<td>{n}%</td>
	</tr>
	</table>
	### Анализ
	{Текст анализа — см. правила ниже}
	---
```

**Цвета строк в таблице воронки:**
- Строка CRO: `color="green_bg"` если CRO вырос ≥ 0.3 п.п., `color="red_bg"` если упал ≥ 0.5 п.п., без цвета если стабильный
- Ячейки Δ: `color="green_bg"` для роста > +10%, `color="red_bg"` для падения > -10%

---

## Headline модели

Headline для toggle-заголовка (после "Модель: Name —"):

| Условие | Headline |
|---|---|
| CRO упал > 0.5 п.п. И заказы упали | "падение заказов {-X}%" |
| CRO упал > 0.5 п.п. НО переходы выросли | "CRO снижение {-X.XX}pp при росте трафика" |
| CRO вырос > 0.5 п.п. | "рост CRO {+X.XX}pp" |
| Заказы выросли > 30% | "взрывной рост +{X}% заказов" |
| Заказы упали > 30% | "падение заказов {-X}%" |
| Иначе | "заказы {+/-X}%" |

---

## Текст анализа (подсекция "Анализ")

### Если CRO упал > 0.5 п.п.:

```
**КРИТИЧЕСКАЯ ПРОБЛЕМА:** CRO упала с {prev}% до {current}% ({delta}pp) {контекст переходов}.

**ГИПОТЕЗА:** {cause из diagnostics — 2-3 предложения с конкретными данными}

**Расчёт эффекта:** Если восстановить CRO до {prev}%:
- Дополнительные заказы: {card_opens} × ({prev}% - {current}%) = {n} заказов
- Дополнительная выручка: {n} × {avg_check}₽ (ср.чек) = +{revenue} ₽
- Дополнительная маржа: {revenue} × {margin_pct}% (маржинальность) = +{margin} ₽
```

### Если CRO вырос > 0.5 п.п. или модель стабильна:

```
{Name} показывает {стабильную CRO / отличный рост} — CRO {current}% (vs {prev}%). {1-2 предложения о ключевых факторах: доля органики, ROMI, тренд артикулов}.
```

### Если данных мало (< 50 заказов за период):

```
{Name}: объём данных недостаточен для выводов ({orders} заказов за период). Мониторинг.
```

---

## КРИТИЧЕСКИЕ ПРАВИЛА

1. **Notion Enhanced Markdown.** Таблицы через `<table>` с `fit-page-width="true" header-row="true" header-column="true"`.
2. **Шапки таблиц:** `<tr color="blue_bg">`.
3. **Строка CRO:** `color="green_bg"` если CRO вырос ≥ 0.3 п.п., `color="red_bg"` если упал ≥ 0.5 п.п.
4. **Toggle-заголовок:** `## Модель: {Name} — {headline} {toggle="true"}`
5. **Tab-indentation** (`\t`) для контента внутри toggle (Notion требует).
6. **Выкуп\*:** ВСЕГДА с `\*` и сноской `\*Данные по выкупам неполные (лаг 3-21 день)`.
7. **Числа:** `1 234 567 ₽`, `24,1%`, `+3,2 п.п.` — пробелы в тысячах.
8. **Title Case** для моделей: Wendy, Vuki, Ruby (не wendy, vuki, ruby).
9. **ТОЛЬКО реальные данные** из входных данных. Никогда не придумывать.
10. **ТОЛЬКО реальные модели** из sku_statuses (Продается + Запуск).
11. **Значимые артикулы:** макс 5 на модель. Сортировка по заказам (топ по убыванию).
12. **Расчёт эффекта:** ОБЯЗАТЕЛЕН для каждой модели с CRO↓ > 0.5 п.п. Формулу писать полностью.
13. **Разделитель `---`** после каждой модельной секции.
14. **CRO — ГЛАВНАЯ метрика.** Всегда выделять в headline и анализе.
15. **Сортировка моделей:** по убыванию выручки.
16. **Callout после анализа:** если CRO↓ — `<callout icon="🚨" color="red_bg">`, если CRO↑ — `<callout icon="🔥" color="green_bg">`.

---

## Формат вывода

Один Markdown-документ, содержащий ВСЕ модельные секции подряд. Каждая секция — по шаблону выше.

Этот документ будет вставлен в финальный отчёт как секции II-XII синтезатором.
