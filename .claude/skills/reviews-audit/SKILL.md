---
name: reviews-audit
description: "Use when user asks for deep product analysis of WB reviews, questions, returns. LLM clustering of all texts, model cards, gap analysis, rich Notion publishing. Triggers: reviews-audit, аналитика отзывов, анализ возвратов, аудит отзывов, качество ответов"
---

# Аналитика отзывов и возвратов WOOKIEE v2 (Wildberries)

Глубокий продуктовый анализ отзывов, вопросов и возвратов на WB.
Карточка каждой активной модели, LLM-кластеризация всех текстов, gap-анализ позиционирования vs восприятия.

Spec: `docs/superpowers/specs/2026-04-07-reviews-audit-v2-design.md`

## Фаза 1: Параметры

Спроси пользователя:

1. **Период:** неделя / месяц / квартал / год / кастомные даты
2. **Фокус** (опц.): конкретная модель или «все»
3. **Кабинет** (опц.): IP / OOO / оба (дефолт — оба)

Вычисли `date_from`, `date_to`. Гранулярность: год→помесячно, квартал→помесячно, месяц→понедельно, неделя→подневно.

| Период | Карточки моделей | LLM-анализ | Gap-анализ |
|--------|-----------------|-----------|-----------|
| Год/Квартал | Все активные | Все тексты | Да |
| Месяц | Только с алертами + сводная | Все тексты | Только проблемные |
| Неделя | Только алерты | Все тексты | Нет |

## Фаза 2: Сбор данных

```bash
python3 scripts/reviews_audit/collect_data.py \
  --date-from "{{date_from}}" --date-to "{{date_to}}" \
  --cabinet "{{cabinet}}" --output /tmp/reviews_audit_data.json
```

Прочитай JSON, выведи сводку: отзывов / вопросов / моделей с заказами.

**ВАЖНО:** Collector использует `get_osnova_sql()` для маппинга моделей в orders — это НЕПРАВИЛЬНО для аудита отзывов, т.к. схлопывает vuki2→Vuki, mia→Other и т.д. Для Фазы 4 нужно делать ОТДЕЛЬНЫЙ запрос к БД с raw `LOWER(SPLIT_PART(supplierarticle, '/', 1))` без `get_osnova_sql`.

Запроси raw orders напрямую:

```python
# Orders by raw model (WITHOUT get_osnova_sql!)
cur.execute('''
    SELECT LOWER(SPLIT_PART(supplierarticle, '/', 1)) as model,
           COUNT(*) as orders_count,
           SUM(CASE WHEN iscancel::text IN ('0', 'false') OR iscancel IS NULL THEN 1 ELSE 0 END) as buyout_count,
           SUM(CASE WHEN iscancel::text IN ('1', 'true') THEN 1 ELSE 0 END) as return_count
    FROM orders WHERE date >= %s AND date < %s
    GROUP BY 1 ORDER BY 2 DESC;
''', (date_from, date_to))

# Monthly by raw model
cur.execute('''
    SELECT DATE_TRUNC('month', date)::date as month,
           LOWER(SPLIT_PART(supplierarticle, '/', 1)) as model,
           COUNT(*) as orders_count,
           SUM(CASE WHEN iscancel::text IN ('0', 'false') OR iscancel IS NULL THEN 1 ELSE 0 END) as buyout_count,
           SUM(CASE WHEN iscancel::text IN ('1', 'true') THEN 1 ELSE 0 END) as return_count
    FROM orders WHERE date >= %s AND date < %s
    GROUP BY 1, 2 ORDER BY 1, 2;
''', (date_from, date_to))
```

Сохрани в `/tmp/reviews_orders_raw.json`.

## Фаза 3: Фильтрация и маппинг

### 3.1 Маппинг моделей

Основной маппинг — через `productDetails.supplierArticle` из отзывов: `LOWER(SPLIT_PART(article, '/', 1))`.

Если Supabase MCP доступен — дополнительный маппинг через товарную матрицу:

```sql
-- Supabase project: gjvwcdtfglupewcwzfhw
-- ПРАВИЛЬНЫЕ имена таблиц/колонок:
SELECT t.barkod, a.kod as artikul, c.name as cvet, m.kod as model, mo.kod as model_osnova
FROM tovary t
JOIN artikuly a ON a.id = t.artikul_id
JOIN modeli m ON m.id = a.model_id
JOIN modeli_osnova mo ON mo.id = m.model_osnova_id
LEFT JOIN cveta c ON c.id = a.cvet_id;
```

### 3.2 Статусы моделей

```sql
-- ВАЖНО: status_id может быть NULL для всех моделей!
SELECT mo.kod, s.nazvanie as status
FROM modeli_osnova mo LEFT JOIN statusy s ON s.id = mo.status_id;
```

Если все статусы NULL — спросить пользователя какие модели исключить.

### 3.3 Внутренние коды в БД заказов

В таблице `orders` есть артикулы-коды, не совпадающие с отзывами:
- `компбел-ж-бесшов` — внутренний код, маппится на Vuki (60K+ заказов, 0 отзывов)
- `set_wookiee` — старое название Set Vuki
- `duo` — отдельная модель без отзывов
- `moon` vs `moon2` — разные модели в orders, но одна в feedbacks

Эти модели исключить из карточек (нет отзывов), но упомянуть в методологии.

## Фаза 4: Цифровой анализ

Для каждой модели (по raw model из supplierArticle): рейтинг, зона, звёзды, need_5star, заказы, % возвратов, помесячная динамика, алерты, drill-down по артикулам.

Сохрани в `/tmp/reviews_audit_phase4.json`.

## Фаза 5: LLM-кластеризация текстов

Запусти **субагент** (Agent tool, general-purpose, run_in_background=true).

Субагент читает `/tmp/reviews_audit_data.json`, обрабатывает ВСЕ отзывы с текстом порциями по 200, выявляет ВСЕ кластеры проблем и преимуществ с частотностью, помесячной динамикой, per_model разбивкой.

Сохраняет в `/tmp/reviews_audit_clusters.json`.

**Фазы 4 и 5 можно запустить параллельно** — они независимы.

## Фаза 6: Продуктовый анализ по моделям

Для года/квартала: субагент формирует полный MD-отчёт с карточкой КАЖДОЙ активной модели. Субагент читает phase4.json + clusters.json + data.json (вопросы).

Сохраняет в `docs/reports/reviews-audit-{{YYYY-MM-DD}}.md`.

## Фаза 7: Gap-анализ (Notion MCP)

Notion → страница WOOKIEE → база «Модельный ряд»:
- Поле `Name` (модель), `Позиционирование` (продуктовый смысл)
- Только для моделей с проблемами: Задумка vs Реальность → Gap → Рекомендация

## Фаза 8: Публикация в Notion

### 8.1 Notion MCP — enhanced markdown

Публикуй через `notion-create-pages` в базу «Аналитические отчёты» (data_source_id: `30158a2b-d587-8091-bfc3-000b83c6b747`).

**ПРАВИЛЬНЫЙ синтаксис Notion enhanced markdown:**

Toggle-заголовки (НЕ `<toggle>` теги!):
```
## Ruby — флагман бренда (4.85 ⭐) {toggle="true"}
	Контент внутри toggle (ОБЯЗАТЕЛЬНО TAB-отступ!)
	Ещё контент с TAB-отступом
```

Callout-блоки:
```
<callout icon="🔥" color="red_bg">
	Текст с TAB-отступом и **жирным**
</callout>
```

Цветные таблицы:
```
<table fit-page-width="true" header-row="true">
<tr color="blue_bg">
<td>Заголовок</td><td>Значение</td>
</tr>
<tr color="green_bg">
<td>Хорошо</td><td>4.85</td>
</tr>
<tr color="red_bg">
<td>Плохо</td><td>4.18</td>
</tr>
</table>
```

Цвет блока: `Текст {color="green_bg"}`

### 8.2 Стратегия публикации (2 вызова max)

**Вызов 1** — создать страницу:
- Executive Summary (5 callout-блоков)
- Сводная таблица моделей (цветная)
- Карточки топ-7 моделей (toggle-заголовки, полная детализация)

**Вызов 2** — update_page, append:
- Остальные карточки моделей (toggle-заголовки)
- Кластеры проблем (таблица, все)
- Кластеры преимуществ (таблица, все)
- Рекомендации (3 callout-блока: CRITICAL red, IMPORTANT yellow, IMPROVEMENTS blue)
- Методология

**НЕ делать >3 вызовов** — Notion MCP может потерять соединение.

### 8.3 Свойства страницы

```json
{
  "Name": "🔍 Аудит отзывов WOOKIEE: {{date_from}} — {{date_to}}",
  "date:Период начала:start": "{{date_from}}",
  "date:Период начала:is_datetime": 0,
  "date:Период конца:start": "{{date_to}}",
  "date:Период конца:is_datetime": 0,
  "Источник": "reviews-audit",
  "Статус": "Актуальный"
}
```

### 8.4 Структура карточки модели (внутри toggle)

```
## MODEL — краткое описание (рейтинг ⭐) {toggle="true"}
	<callout icon="📊" color="blue_bg">
		**Рейтинг: X.XX** (зона) | Отзывов: N | Вопросов: N | Заказов: N | Возвраты: X.X%
		Звёзды: ⭐1: N | ⭐2: N | ⭐3: N | ⭐4: N | ⭐5: N
	</callout>
	**Динамика рейтинга:**
	<table fit-page-width="true" header-row="true">
	<tr color="blue_bg">
	<td>Месяц</td><td>Отзывы</td><td>Рейтинг</td><td>% негатив</td><td>Заказы</td><td>% возвратов</td>
	</tr>
	<tr>
	<td>2025-10</td><td>394</td><td>4.87</td><td>3.6%</td><td>3 857</td><td>34.5%</td>
	</tr>
	</table>
	### Что ценят покупатели
	- **Комфорт** — 185 упом. (21.4%)
		> "Отличное белье, мягкое, нигде не жмет"
	### Проблемы
	- **Маломерит** — 80 упом. (9.3%)
		> "Топ маленький как на 42, трусики большие"
	### Рекомендации
	- **Производство:** пересмотреть размерную сетку
	- **Карточка:** добавить фото на разных фигурах
	- **Cross-sell:** Joy, Vuki2
```

## Принципы (ОБЯЗАТЕЛЬНО)

1. **Доли, а не абсолюты.** Рост возвратов пропорционально заказам = норма.
2. **Текст > звёзды.** 5★ с претензией = негативный.
3. **Пороги значимости.** <5 случаев = шум.
4. **Динамика долей.** 1% → 3% = алерт.
5. **Drill-down.** Модель → артикул → цвет.
6. **Actionable.** Не «улучшите», а «проверить краску Ruby синий, партия Q1 2026».
7. **GROUP BY с LOWER().** Всегда.
8. **Выводимые — не анализировать.**
9. **Raw model для orders.** НЕ использовать `get_osnova_sql()` — он схлопывает модели.
10. **iscancel — TEXT.** Всегда `iscancel::text IN ('0', 'false')`.
