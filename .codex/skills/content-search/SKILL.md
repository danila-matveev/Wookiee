---
name: content-search
description: "Интерактивный поиск фото бренда в Content KB (~10K фото, vector search). Помогает сформировать запрос, подобрать контент под маркетинговую воронку, показывает превью. Триггеры: найди фото, поиск контента, content search, фото модели, каталожные фото, подбери фото, маркетплейсы фото, блогеры фото, content KB, контент база, подобрать фотографии."
---

# Content Search — интерактивный поиск фото бренда

### Tool Logging

At start: `ToolLogger('/content-search').start(trigger='manual', user='danila')` → save `RUN_ID`.
At end: `ToolLogger('/content-search').finish(RUN_ID, status='success', items_processed={RESULTS_COUNT})`.

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
logger = ToolLogger('/content-search')
run_id = logger.start(trigger='manual', user='danila')
print(f'RUN_ID={run_id}')
"
```

## Когда вызывать

Автоматически при любом запросе на поиск фото, подбор контента, работу с фотобазой бренда.

## Workflow

### Шаг 1 — Сбор требований (интерактивный)

Проведи пользователя через уточнения. Пропускай шаги, если пользователь уже указал параметры в запросе. Используй AskUserQuestion для структурированных вопросов.

**1.1 Модель (model_name)**

Известные модели: Alice, Audrey, Bella, Charlotte, Eva, Joy, Lana, Miafull, Moon, Ruby, Space, Valery, Vuki, Wendy.

Также существуют сеты (комплекты): set_Bella, set_Wendy и т.д.

Если пользователь не указал модель — спроси: "Какую модель ищем?"

**1.2 Назначение контента → определяет category**

Спроси: "Для чего нужны фото?" и подбери category:

| Назначение | category | Описание |
|---|---|---|
| Карточка товара на маркетплейсе (WB, Ozon) | `маркетплейсы` | Оптимизированные фото для карточки товара |
| Сайт бренда | `сайт` | Фото для сайта, включая размерные сетки и инфографику |
| Соцсети / блогеры / UGC | `блогеры` | Контент от инфлюенсеров и для соцсетей |
| Lamoda | `lamoda` | Фото специально для Lamoda |
| Студийная каталожная съёмка | `фото` | Исходные фотосессии — самая большая коллекция |
| Дизайн / баннеры / креативы | `дизайн` | Дизайн-материалы, макеты |
| A/B тесты карточек | `аб_тесты` | Варианты для сплит-тестов |

**1.3 Визуальные требования → формируют text query**

Спроси про визуальные характеристики (если не указаны):

- **Ракурс**: спереди / сзади / сбоку / крупный план / полный рост / поясной
- **Стиль**: студийная (нейтральный фон) / имиджевая (цветной фон, настроение) / lifestyle
- **Эмоции**: нейтральная поза / с эмоциями / динамичная
- **Особенности**: "виден вырез", "на белом фоне", "с аксессуарами"

**1.4 Цвет и артикул (опционально)**

- **color**: black, white, beige, brown, coffee, light_beige, light_brown, dark_beige, graphite, green, nude, wine_red и др.
- **sku**: артикул WB (6-12 цифр)

### Шаг 2 — Формирование поискового запроса

Собери параметры:
- `query` — текстовый запрос из визуальных требований (шаг 1.3), на русском. Пример: "Фотография девушки в белье вид спереди в полный рост на нейтральном фоне"
- `model_name` — из шага 1.1
- `category` — из шага 1.2
- `color` — из шага 1.4 (если указан)
- `sku` — из шага 1.4 (если указан)
- `limit` — по умолчанию 5 для начала, до 20
- `min_similarity` — по умолчанию 0.1 (низкий порог, чтобы не отсекать результаты)

### Шаг 3 — Выполнение поиска

Запусти через Bash:

```bash
python3 -c "
import asyncio, json
from services.content_kb.search import search_content
result = asyncio.run(search_content(
    query='ТЕКСТОВЫЙ_ЗАПРОС',
    limit=5,
    model_name='MODEL',      # или None
    color='COLOR',            # или None
    category='CATEGORY',      # или None
    sku='SKU',                # или None
    min_similarity=0.1,
    include_preview=False,
))
print(json.dumps(result, indent=2, ensure_ascii=False))
" 2>&1 | grep -v Warning | grep -v genai | grep -v google | grep -v support | grep -v README | grep -v switch | grep -v bug | grep -v FutureWarning
```

**Важно:**
- Всегда используй `include_preview=False` при первом поиске (экономит время)
- `min_similarity=0.1` — низкий порог, чтобы увидеть больше результатов
- Фильтруй Python warnings через grep -v

### Шаг 4 — Показ результатов

**4.1 Таблица результатов:**

Покажи в виде таблицы:

| # | Similarity | Цвет | Категория | Файл | Путь |
|---|-----------|------|-----------|------|------|

**4.2 Превью (топ-3):**

Скачай и покажи топ-3 результата:

```bash
python3 -c "
from services.content_kb.yadisk_client import YaDiskClient
client = YaDiskClient()
data = client.download_bytes('DISK_PATH')
with open('/tmp/content_search_1.jpg', 'wb') as f:
    f.write(data)
print(f'Downloaded: {len(data)} bytes')
" 2>&1 | grep -v Warning
```

Затем покажи изображение через Read tool: `Read /tmp/content_search_1.jpg`

Повтори для каждого из топ-3 результатов (content_search_1.jpg, content_search_2.jpg, content_search_3.jpg).

**4.3 Аннотация по воронке:**

Для каждого результата укажи, для какой стадии маркетинговой воронки он подходит (см. таблицу ниже).

### Шаг 5 — Итерация

После показа результатов предложи:
- "Показать другие ракурсы?"
- "Попробовать другой цвет?"
- "Показать ещё результатов?"
- "Поискать в другой категории?"

Если пользователь хочет продолжить — вернись к шагу 2 с обновлёнными параметрами.

---

## Маркетинговая воронка

Используй эту таблицу для рекомендаций и аннотаций:

| Стадия воронки | Категории контента | Что искать | Цель |
|---|---|---|---|
| **Awareness** (охват, узнаваемость) | фото, сайт, блогеры | Hero shots, lifestyle, имиджевые, UGC | Привлечь внимание, первое впечатление |
| **Consideration** (рассмотрение, выбор) | фото, маркетплейсы, дизайн | Детальные виды всех ракурсов, размерная сетка, инфографика | Помочь сравнить и выбрать |
| **Conversion** (покупка) | маркетплейсы, lamoda | Оптимизированные карточки товара, все обязательные фото | Финальный толчок к покупке |
| **Optimization** (улучшение) | аб_тесты | A/B варианты главного фото, инфографики | Повышение конверсии через тесты |

Когда пользователь описывает задачу через воронку (например "нужны фото для карточки на WB"), используй маппинг для автоматического подбора category и типа query.

---

## Дополнительные команды

### Статистика базы

```bash
python3 -c "
import json
from services.content_kb.store import ContentStore
stats = ContentStore().get_stats()
print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))
"
```

### Список контента по фильтрам (без vector search)

```bash
python3 -c "
import json
from services.content_kb.store import ContentStore
items = ContentStore().list_content(model_name='Wendy', category='фото', limit=20)
print(f'Found: {len(items)}')
for item in items:
    print(f'  {item[\"color\"] or \"?\":15} | {item[\"file_name\"]:30} | {item[\"disk_path\"]}')
"
```

### Количество фото по модели/цвету

```bash
python3 -c "
import psycopg2
from services.content_kb import config
conn = psycopg2.connect(host=config.POSTGRES_HOST, port=config.POSTGRES_PORT, dbname=config.POSTGRES_DB, user=config.POSTGRES_USER, password=config.POSTGRES_PASSWORD, sslmode='require')
cur = conn.cursor()
cur.execute('''
    SELECT LOWER(model_name), color, COUNT(*)
    FROM content_assets
    WHERE status = 'indexed' AND LOWER(model_name) = LOWER(%s)
    GROUP BY LOWER(model_name), color
    ORDER BY COUNT(*) DESC
''', ('Wendy',))
for r in cur.fetchall():
    print(f'  {r[0]:15} | {r[1] or \"без цвета\":20} | {r[2]} шт.')
cur.close(); conn.close()
"
```

---

## Важные замечания

- Все команды запускаются из корня проекта (working directory)
- Требуются env vars: `GOOGLE_API_KEY`, `YANDEX_DISK_TOKEN`, `POSTGRES_HOST/PORT/DB/USER/PASSWORD` (из `.env`)
- Embedding текстового запроса занимает ~1-2 сек (Gemini API)
- Скачивание превью ~2-3 сек на файл (YaDisk API)
- Similarity scores 0.35-0.50 — хороший результат для text↔image cross-modal search
- Для больших наборов: сначала покажи таблицу, потом предложи скачать превью конкретных файлов
