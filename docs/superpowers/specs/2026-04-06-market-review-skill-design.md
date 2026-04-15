# Market Review Skill Design

> Ежемесячный обзор рынка и конкурентов для бренда Wookiee (женское белье, WB)

**Дата:** 2026-04-06
**Статус:** Draft
**Подход:** B — двухпроходный (Collectors + AI Analyst)

---

## Цель

Автоматический ежемесячный скилл, который:
1. Собирает данные о рынке и конкурентах (MPStats API + внутренняя БД + browser research)
2. Верифицирует данные (кросс-проверка)
3. Генерирует глубокий аналитический отчёт с actionable гипотезами (HEAVY LLM)
4. Публикует в Notion на фиксированную страницу

**Не** dashboard и **не** отчёт ради отчёта. Максимум смысла: паттерны, "почему", тестируемые гипотезы.

---

## Архитектура (Pipeline)

```
/market-review [месяц]
  |
  +-- Stage 0: Input
  |     - Месяц для анализа (по умолчанию: прошлый)
  |     - Конфиг: категории, конкуренты, наши топ-модели
  |
  +-- Stage 1: Parallel Collection (Python, ThreadPoolExecutor)
  |     +-- market_categories    [MPStats: тренды категорий]
  |     +-- our_performance      [Internal DB: наши метрики]
  |     +-- competitors_brands   [MPStats: 18 конкурентов]
  |     +-- top_models_ours      [MPStats + DB: 6 моделей]
  |     +-- top_models_rivals    [MPStats: аналоги конкурентов]
  |     +-- new_items            [MPStats: новинки в категориях]
  |     --> /tmp/market_review_data.json
  |
  +-- Stage 1.5: Browser Research (agent-browser / chrome-devtools)
  |     +-- competitors_social   [Instagram: 13 аккаунтов]
  |     +-- competitors_cards    [WB: карточки топ-конкурентов]
  |     --> дополняет JSON
  |
  +-- Stage 2a: Verifier (MAIN tier)
  |     - Кросс-проверка: наши данные из DB vs MPStats (дельта <= 15%)
  |     - Полнота: все категории и бренды имеют данные
  |     - Арифметика: дельты корректны
  |     --> STATUS: PASS | WARN | FAIL
  |
  +-- Stage 2b: Analyst (HEAVY tier, Claude Sonnet)
  |     - Получает ВСЕ данные + конкурентную карту + контекст Wookiee
  |     - Генерирует Markdown-отчёт с Notion-разметкой
  |     --> /tmp/market_review_report.md
  |
  +-- Stage 3: Publication
        +-- docs/reports/YYYY-MM-market-review.md
        +-- Notion page (ID: 2f458a2bd58780648974f98347b2d4d5)
```

---

## Collectors: детали

### Collector 1: `market_categories` (MPStats API)

Категории WB для мониторинга:
- `Женское белье/Комплекты белья`
- `Женское белье/Бюстгальтеры`
- `Женское белье/Трусы`
- `Женское белье/Боди`
- `Спортивное белье` (если доступна в MPStats)

**API:** `GET /api/wb/get/category/trends?path=<path>&d1=<start>&d2=<end>`

По каждой категории за текущий и предыдущий месяц:
- Общая выручка категории, динамика %
- Средний чек, динамика
- Количество продавцов / брендов
- Количество товаров

**Output:**
```json
{
  "categories": {
    "Комплекты белья": {
      "current": {"revenue": ..., "avg_check": ..., "sellers": ..., "items": ...},
      "previous": {...},
      "delta_pct": {"revenue": ..., "avg_check": ..., ...}
    }
  }
}
```

### Collector 2: `our_performance` (Internal DB)

Наши метрики из `shared/data_layer/` за аналогичный период:
- Выручка, заказы, продажи (WB + OZON)
- Средний чек
- Доля рынка = наша выручка / выручка категории (из collector 1)

**Output:**
```json
{
  "our": {
    "current": {"revenue": ..., "orders": ..., "avg_check": ...},
    "previous": {...},
    "delta_pct": {...},
    "market_share": {"Комплекты белья": "2.3%", ...}
  }
}
```

### Collector 3: `competitors_brands` (MPStats API)

По каждому из 18 конкурентов из конфига:

**API:** `GET /api/wb/get/brand/trends?path=<brand>&d1=<start>&d2=<end>`

Метрики: выручка, количество продаж, средний чек, количество SKU.

**Output:**
```json
{
  "competitors": {
    "Birka Art": {
      "current": {"revenue": ..., "sales": ..., "avg_check": ..., "sku_count": ...},
      "previous": {...},
      "delta_pct": {...}
    },
    "SOGU": {...},
    ...
  }
}
```

### Collector 4: `top_models_ours` (MPStats + DB)

Наши 6 топ-моделей: Венди, Одри, Руби, Джой, Вуки, Мун.

- Из DB: воронка (клик -> корзина -> заказ -> выкуп), выручка
- Из MPStats: `GET /api/wb/get/item/{sku}/sales?d1=...&d2=...` — позиции, оценочные продажи

**Output:**
```json
{
  "our_models": {
    "wendy": {
      "skus": ["sku1", "sku2"],
      "funnel": {"opens": ..., "cart": ..., "orders": ..., "buyouts": ...},
      "conversions": {"cr_open_cart": ..., "cr_cart_order": ..., "cr_open_order": ...},
      "revenue": ...,
      "mpstats_sales": ...
    }
  }
}
```

### Collector 5: `top_models_rivals` (MPStats API)

По каждой нашей топ-модели:
- `GET /api/wb/get/item/{sku}/similar` — находим прямые аналоги конкурентов
- По каждому аналогу: `GET /api/wb/get/item/{sku}/sales` — продажи, цена, рейтинг, отзывы
- Берём топ-3 аналога по выручке

**Output:**
```json
{
  "rival_models": {
    "wendy": {
      "analogs": [
        {"sku": ..., "brand": ..., "price": ..., "sales": ..., "rating": ..., "reviews": ...},
        ...
      ]
    }
  }
}
```

### Collector 6: `new_items` (MPStats API)

Новые SKU в наших категориях за месяц:
- Фильтр: выручка > 500K руб (отсечь мелочь)
- По каждому: бренд, цена, выручка, рейтинг

**Output:**
```json
{
  "new_items": [
    {"sku": ..., "brand": ..., "category": ..., "price": ..., "revenue": ..., "rating": ...},
    ...
  ]
}
```

### Collector 7: `competitors_social` (Browser Research)

По каждому конкуренту с Instagram-аккаунтом (13 из 18):
- Открываем профиль через agent-browser / chrome-devtools
- Собираем последние 10-15 постов за месяц
- Фиксируем: тип контента (reels/фото/карусель), лайки, комменты, тема, хук
- Выделяем "залетевшие" (выше среднего по engagement)

**Output:**
```json
{
  "social": {
    "Birka Art": {
      "account": "@birka_art",
      "followers": 42000,
      "posts_last_month": 12,
      "top_posts": [
        {"type": "reels", "likes": ..., "comments": ..., "topic": "...", "hook": "...", "url": "..."}
      ],
      "avg_engagement": ...
    }
  }
}
```

### Collector 8: `competitors_cards` (Browser Research)

По топ-конкурентам (Birka Art, SOGU, Waistline, Belle You):
- Открываем их топ-карточки на WB
- Фиксируем: обложка, видео, инфографика, структура описания, УТП, ценовая подача
- Сравниваем с нашими

**Output:**
```json
{
  "wb_cards": {
    "Birka Art": {
      "top_items": [
        {"sku": ..., "title": ..., "has_video": true, "infographic_count": 3, "utp": "...", "price_display": "..."}
      ]
    }
  }
}
```

---

## Verifier (Stage 2a)

**Модель:** MAIN (Gemini Flash)

Чеклист:
1. **Кросс-проверка:** наши данные из DB vs MPStats brand trends для Wookiee — дельта <= 15%
2. **Полнота:** все категории и бренды из конфига имеют данные за оба периода
3. **Арифметика:** дельты = (current - previous) / previous * 100
4. **Данные браузера:** если collectors 7-8 вернули ошибки — пометить, не блокировать
5. **Sensitive data:** нет ИНН, юрлиц, токенов в выводе

**Output:**
```
STATUS: PASS | WARN | FAIL
ISSUES: [критические проблемы → abort]
WARNINGS: [некритические → включить в footnote отчёта]
```

Логика:
- PASS → продолжить к Analyst
- WARN → продолжить, warnings включить в отчёт
- FAIL → остановить, показать пользователю что не так

---

## Analyst (Stage 2b)

**Модель:** HEAVY (Claude Sonnet, ~$0.20-0.40 за запуск)

**Input:** весь JSON (Stages 1 + 1.5) + verifier warnings + контекст Wookiee:
- Конкурентная карта (ценовые сегменты, позиционирование)
- Наши бизнес-цели (оборачиваемость x маржа)
- Текущий масштаб (~35-40М/мес)

### Структура отчёта (Notion-страница)

**I. Рынок: динамика категорий**
- Таблица: категория -> выручка (тек/пред) -> дельта % -> ср.чек -> кол-во продавцов
- Наша доля рынка по каждой категории
- Callout: где растём быстрее рынка (зелёный) / отстаём (красный)
- Вывод: 2-3 предложения "почему" + что делать

**II. Конкуренты: кто вырос/упал и почему**
- Таблица: бренд -> выручка -> дельта % -> ср.чек -> кол-во SKU
- Топ-3 "выстрелили" + топ-3 "просели"
- Паттерны: что общего у растущих (цена? ассортимент? контент?)

**III. Наши топ-модели vs конкуренты**
- По каждой модели (Венди, Одри, Руби, Джой, Вуки, Мун):
  - Наши конверсии (клик -> корзина -> заказ) vs топ-3 аналога
  - Цена vs аналоги
  - Где сильно хуже -> фокус роста
  - Где лучше -> что сохранить
- Callout: "главный фокус месяца" — 1-2 модели с наибольшим потенциалом

**IV. Контент и соцсети конкурентов**
- Топ-5 "залетевших" постов конкурентов (ссылка + почему сработало)
- Паттерны карточек WB: что делают лучшие (обложки, видео, инфографика)
- Список: "практика -> где увидели -> почему работает -> как тестим у себя"

**V. Гипотезы и действия**
- 5-7 тестируемых гипотез формата: "Наблюдение -> Подтверждение (цифра/ссылка) -> Действие"
- Каждая с оценкой потенциального эффекта ("если конверсия +1% -> +X руб/мес")
- Приоритет: Quick Wins первыми

### Правила для Analyst
- Никаких "компания молодец" — только "что конкретно делают и как повторить"
- Гипотезы только тестируемые (с метрикой успеха и сроком проверки)
- Цифры всегда с дельтой (абс + %)
- Если данных недостаточно — честно "нет данных", не додумывать
- Процентные метрики: ТОЛЬКО средневзвешенные

---

## Publication (Stage 3)

1. **MD файл:** `docs/reports/YYYY-MM-market-review.md`
2. **Notion:** публикация на страницу `2f458a2bd58780648974f98347b2d4d5`
   - Используем Notion MCP tools (create-page / update-page)
   - Формат: Markdown -> Notion blocks через `shared/notion_blocks.py`

---

## Error Handling

| Ситуация | Поведение |
|----------|-----------|
| MPStats API недоступен / rate limit | Collector возвращает error в meta, остальные продолжают. Analyst помечает "данные MPStats недоступны" |
| Browser research падает (Instagram блок, WB не грузится) | Collector пропускается. Секция IV помечается "требует ручного сбора" |
| Verifier -> FAIL | Pipeline останавливается. Пользователю показывается что не сошлось |
| Внутренняя БД недоступна | Collector our_performance падает. Без наших данных отчёт бессмысленен -> FAIL |
| LLM rate limit / error | Retry 1x на MAIN -> escalate to HEAVY -> FREE |

---

## Стоимость запуска

| Компонент | Модель | ~Tokens | ~Cost |
|-----------|--------|---------|-------|
| 6 MPStats collectors | Python, no LLM | -- | $0 |
| 2 Browser collectors | Chrome DevTools | -- | $0 |
| Verifier | MAIN (Gemini Flash) | ~5K | ~$0.01 |
| Analyst | HEAVY (Claude Sonnet) | ~30-50K | $0.20-0.40 |
| **Итого** | | | **~$0.25-0.45** |

---

## Конфиг

Файл: `scripts/market_review/config.py`

```python
# Категории WB для мониторинга
CATEGORIES = [
    "Женское белье/Комплекты белья",
    "Женское белье/Бюстгальтеры",
    "Женское белье/Трусы",
    "Женское белье/Боди",
    # "Спортивное белье",  # раскомментировать если есть в MPStats
]

# Конкуренты: бренд -> MPStats path
COMPETITORS = {
    # Прямые конкуренты (бесшовное на МП)
    "Birka Art": {"mpstats_path": "Birka Art", "segment": "econom-mid", "instagram": "@birka_art"},
    "Время Цвести": {"mpstats_path": "Время Цвести", "segment": "mid", "instagram": "@vremyazvesti"},
    "SOGU": {"mpstats_path": "SOGU", "segment": "mid-premium", "instagram": "@sogu.shop"},
    "Waistline": {"mpstats_path": "Waistline", "segment": "mid-premium", "instagram": "@waistline_shop"},
    "RIVERENZA": {"mpstats_path": "RIVERENZA", "segment": "econom", "instagram": None},
    "Blizhe": {"mpstats_path": "Blizhe", "segment": "mid", "instagram": None},
    # Широкий ландшафт
    "Belle You": {"mpstats_path": "Belle You", "segment": "mid-premium", "instagram": "@belleyou.ru"},
    "Bonechka": {"mpstats_path": "Bonechka", "segment": "econom", "instagram": "@bonechka_lingerie"},
    "Lavarice": {"mpstats_path": "Lavarice", "segment": "mid", "instagram": "@lavarice_"},
    "Incanto": {"mpstats_path": "Incanto", "segment": "mid", "instagram": "@incanto_official"},
    "Mark Formelle": {"mpstats_path": "Mark Formelle", "segment": "econom-mid", "instagram": "@markformelle"},
    "VIKKIMO": {"mpstats_path": "VIKKIMO", "segment": "econom", "instagram": "@vikkimo_underwear"},
    "Love Secret": {"mpstats_path": "Love Secret", "segment": "econom", "instagram": "@lovesecret.shop"},
    "MASAR Lingerie": {"mpstats_path": "MASAR Lingerie", "segment": "mid", "instagram": "@masar.lingerie"},
    "Mirey": {"mpstats_path": "Mirey", "segment": "mid", "instagram": "@mirey.su"},
    "Morely": {"mpstats_path": "Morely", "segment": "premium", "instagram": "@morely.ru"},
    "Cecile": {"mpstats_path": "Cecile", "segment": "unknown", "instagram": None},
    "Where Underwear": {"mpstats_path": "Where Underwear", "segment": "unknown", "instagram": None},
}

# Наши топ-модели: модель -> список SKU на WB
OUR_TOP_MODELS = {
    "wendy": [],   # TODO: заполнить реальными SKU
    "audrey": [],
    "ruby": [],
    "joy": [],
    "wookie": [],
    "moon": [],
}

# Notion
NOTION_PAGE_ID = "2f458a2bd58780648974f98347b2d4d5"

# Browser research: какие конкуренты для глубокого анализа карточек
WB_CARD_DEEP_ANALYSIS = ["Birka Art", "SOGU", "Waistline", "Belle You"]
```

---

## Запуск

- **Ручной (skill):** `/market-review` или `/market-review март`
- **Ручной (CLI):** `python scripts/market_review/collect_all.py --month 2026-03 --output /tmp/market_review_data.json`
- **Автоматический:** добавить `MARKET_MONTHLY` в `scripts/run_report.py` (1-е число каждого месяца)

---

## Новые файлы

| Файл | Назначение |
|------|------------|
| `shared/clients/mpstats_client.py` | API клиент MPStats (auth, rate limiting, retry) |
| `scripts/market_review/collect_all.py` | Оркестратор коллекторов (ThreadPoolExecutor) |
| `scripts/market_review/config.py` | Конфиг: категории, конкуренты, модели |
| `scripts/market_review/collectors/market_categories.py` | MPStats: тренды категорий |
| `scripts/market_review/collectors/our_performance.py` | Internal DB: наши метрики |
| `scripts/market_review/collectors/competitors_brands.py` | MPStats: тренды конкурентов |
| `scripts/market_review/collectors/top_models_ours.py` | MPStats + DB: наши модели |
| `scripts/market_review/collectors/top_models_rivals.py` | MPStats: аналоги конкурентов |
| `scripts/market_review/collectors/new_items.py` | MPStats: новинки в категориях |
| `scripts/market_review/collectors/competitors_social.py` | Browser: Instagram конкурентов |
| `scripts/market_review/collectors/competitors_cards.py` | Browser: WB карточки конкурентов |
| `.claude/skills/market-review/SKILL.md` | Skill definition (stages, prompts, variables) |
| `.claude/skills/market-review/prompts/analyst.md` | Промпт для Analyst (HEAVY) |
| `.claude/skills/market-review/prompts/verifier.md` | Промпт для Verifier (MAIN) |

---

## Масштабирование (будущее)

Текущий дизайн покрывает блоки 1, 3, и частично 2, 4. Для полного покрытия задачи из Битрикса:

| Блок | Статус | Что нужно для автоматизации |
|------|--------|-----------------------------|
| 1. Рынок | Автоматизирован | -- |
| 2. Контент/маркетинг МП | Частично (browser) | Более глубокий парсинг WB карточек |
| 3. Топ-модели | Автоматизирован | -- |
| 4. Соцсети | Частично (Instagram) | TG channels, VK (если нужно) |
| 5. Блогеры | Не автоматизирован | TG search API, Instagram mentions parser |
| 6. Новинки RU+зарубеж | Частично (MPStats для РФ) | Парсинг зарубежных D2C сайтов |
| 7. Сборка в Notion | Автоматизирован | -- |
