# Content Knowledge Base — Design Spec

**Date**: 2026-03-21
**Status**: Draft
**Author**: Claude + Danila
**Approach**: A (Embedding-Only, Gemini Embedding 2 multimodal)

## Problem

Бренд Wookiee имеет тысячи фотографий контента на Яндекс.Диске (каталожные фото, маркетплейсы, дизайн, AB-тесты, реклама блогеров). Найти нужное фото можно только вручную, перебирая папки. Нет возможности:
- Искать фото по визуальному содержимому ("каталожное фото на белом фоне в полный рост")
- Находить похожие фото ("фото как это, но другого цвета")
- Быстро подобрать контент для задачи ("3 лучших фото Bella для карточки")

## Solution

Векторная база данных контента (Content KB) на основе Gemini Embedding 2 — мультимодальной модели, которая нативно понимает изображения и создаёт embeddings в едином пространстве с текстом.

**Подход A**: чистые мультимодальные embeddings без Vision-описаний. Gemini Embedding 2 сам "видит" содержимое фото и кодирует его в вектор. Поиск — по косинусной близости текстового запроса к image embeddings.

**Эволюция**: если качества поиска не хватит — дообогатим Vision-описаниями (подход B) без перестройки архитектуры.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                 Wookiee v3 Multi-Agent System                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────────┐                    │
│  │  Yandex Disk  │───▶│  Indexer Pipeline │                   │
│  │  (OAuth API)  │    │  (cron / manual)  │                   │
│  └──────────────┘    └────────┬─────────┘                    │
│                               │                              │
│                        ┌──────▼──────┐    ┌───────────────┐  │
│                        │   Gemini    │───▶│   Supabase    │  │
│                        │ Embedding 2 │    │   pgvector    │  │
│                        └─────────────┘    │ content_assets│  │
│                                           └───────┬───────┘  │
│                                                   │          │
│  ┌────────────┐   ┌───────────────────┐           │          │
│  │   Oleg     │──▶│  content-searcher │───────────┘          │
│  │  Christina │──▶│  (micro-agent)    │                      │
│  │  Telegram  │──▶│                   │                      │
│  └────────────┘   └───────────────────┘                      │
│                                                              │
│  MCP Server: wookiee-content                                 │
│  Tools: search_content, list_content, get_content_stats      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Components

1. **Yandex Disk Client** (`services/content_kb/yadisk_client.py`)
   - OAuth-авторизованный клиент через библиотеку `yadisk`
   - Рекурсивный обход папок
   - Скачивание файлов для индексации
   - Генерация превью-ссылок на лету

2. **Indexer Pipeline** (`services/content_kb/indexer.py`)
   - Обходит `/Контент/2025/` рекурсивно
   - Парсит путь → метаданные (модель, цвет, артикул, категория)
   - Скачивает → Gemini Embedding 2 → pgvector
   - Инкрементальный: пропускает уже проиндексированные файлы (по md5)
   - Запуск: ручной + крон (раз в сутки)

3. **Content Searcher** (`agents/v3/agents/content-searcher.md`)
   - Micro-agent в мультиагентной системе v3
   - Принимает текстовый запрос → embedding → pgvector similarity search
   - Комбинирует векторный поиск с metadata-фильтрами
   - Возвращает превью + пути + scores

4. **MCP Server** (`services/content_kb/mcp_server.py`)
   - `search_content` — векторный поиск + metadata-фильтры
   - `list_content` — список контента по фильтрам (без векторного поиска)
   - `get_content_stats` — статистика по индексу (кол-во по моделям, категориям)

## Data Model

### Table: `content_assets`

```sql
CREATE TABLE content_assets (
    id              BIGSERIAL PRIMARY KEY,
    embedding       vector(3072) NOT NULL,

    -- Путь и файл
    disk_path       TEXT NOT NULL UNIQUE,
    file_name       VARCHAR(500) NOT NULL,
    mime_type       VARCHAR(100) NOT NULL,
    file_size       BIGINT,
    md5             VARCHAR(32) NOT NULL,

    -- Метаданные из пути
    year            SMALLINT NOT NULL DEFAULT 2025,
    content_category VARCHAR(50),     -- фото, маркетплейсы, дизайн, аб_тесты, сайт, lamoda, блогеры
    model_name      VARCHAR(100),     -- Bella, Vuki, Alice, Moon, Ruby...
    color           VARCHAR(100),     -- black, white, beige, brown, light_beige...
    sku             VARCHAR(50),      -- артикул WB (257144777)

    -- Системные
    indexed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_content_assets_model ON content_assets (model_name);
CREATE INDEX idx_content_assets_color ON content_assets (color);
CREATE INDEX idx_content_assets_category ON content_assets (content_category);
CREATE INDEX idx_content_assets_sku ON content_assets (sku);

-- Векторный индекс (создаётся после первичной индексации)
-- CREATE INDEX idx_content_embedding ON content_assets
--   USING ivfflat (embedding vector_cosine_ops) WITH (lists = N);

-- RLS
ALTER TABLE content_assets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Full access for postgres" ON content_assets FOR ALL TO postgres USING (true);
CREATE POLICY "Read access for authenticated" ON content_assets FOR SELECT TO authenticated USING (true);
```

### SQL Search Function

```sql
CREATE OR REPLACE FUNCTION search_content(
    query_embedding vector(3072),
    match_count INT DEFAULT 10,
    filter_model VARCHAR DEFAULT NULL,
    filter_color VARCHAR DEFAULT NULL,
    filter_category VARCHAR DEFAULT NULL,
    filter_sku VARCHAR DEFAULT NULL,
    min_similarity FLOAT DEFAULT 0.3
)
RETURNS TABLE (
    id BIGINT,
    disk_path TEXT,
    file_name VARCHAR,
    similarity FLOAT,
    model_name VARCHAR,
    color VARCHAR,
    content_category VARCHAR,
    sku VARCHAR,
    mime_type VARCHAR,
    file_size BIGINT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        ca.id,
        ca.disk_path,
        ca.file_name,
        1 - (ca.embedding <=> query_embedding) AS similarity,
        ca.model_name,
        ca.color,
        ca.content_category,
        ca.sku,
        ca.mime_type,
        ca.file_size
    FROM content_assets ca
    WHERE
        (filter_model IS NULL OR LOWER(ca.model_name) = LOWER(filter_model))
        AND (filter_color IS NULL OR LOWER(ca.color) = LOWER(filter_color))
        AND (filter_category IS NULL OR LOWER(ca.content_category) = LOWER(filter_category))
        AND (filter_sku IS NULL OR ca.sku = filter_sku)
        AND 1 - (ca.embedding <=> query_embedding) >= min_similarity
    ORDER BY ca.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

### Path Parsing

Метаданные извлекаются из структуры папок автоматически:

```
/Контент/2025/5. МАРКЕТПЛЕЙСЫ/Bella/Bella-black/257144777/01.png
  → year=2025
  → content_category=маркетплейсы
  → model_name=Bella
  → color=black
  → sku=257144777

/Контент/2025/1. ВСЕ ФОТО/1. Готовый контент/Bella/1. Основные/Bella-black/photo.jpg
  → year=2025
  → content_category=фото
  → model_name=Bella
  → color=black

/Блогеры/Реклама блогеров/campaign_1/photo.jpg
  → content_category=блогеры
```

Маппинг категорий из имён папок:

| Папка | content_category |
|-------|-----------------|
| 1. ВСЕ ФОТО | фото |
| 2. ВИДЕО | видео (пока пропускаем) |
| 3. ИСХОДНИКИ | исходники (пропускаем — RAW/PSD) |
| 4. ДИЗАЙН | дизайн |
| 5. МАРКЕТПЛЕЙСЫ | маркетплейсы |
| 6. САЙТ | сайт |
| 7. АБ тесты | аб_тесты |
| 8. LAMODA | lamoda |
| Блогеры/ | блогеры |

Известные модели (парсятся из имён папок):
`Alice, Audrey, Bella, Charlotte, Eva, Joy, Lana, Miafull, Moon, Ruby, Space, Valery, Vuki, Wendy`

Сеты: `set_Bella, set_Moon, set_Ruby, set_Vuki, set_Wendy, Set Moon, Set Vuki, Set bella, Set ruby`

## Indexer Pipeline

### Flow

```python
# Псевдокод
def index_all():
    client = YaDiskClient(token=YANDEX_DISK_TOKEN)
    embedder = GeminiEmbedder(model="gemini-embedding-2-preview", dimensions=3072)
    store = ContentStore(supabase_connection)

    existing_md5s = store.get_all_md5s()

    files = client.list_images_recursive("/Контент/2025")
    new_files = [f for f in files if f.md5 not in existing_md5s]

    for batch in chunks(new_files, size=6):  # API limit: 6 images per request
        images = []
        metadatas = []
        for file_info in batch:
            image_bytes = client.download_bytes(file_info.path)
            metadata = parse_path_metadata(file_info.path)
            images.append(image_bytes)
            metadatas.append({**metadata, **file_info})

        embeddings = embedder.embed_images(images)

        store.insert_batch(embeddings, metadatas)
        time.sleep(2)  # rate limiting
```

### Skipped content (phase 1)

- **Видео** (`2. ВИДЕО/`) — добавим в фазе 2
- **Исходники** (`3. ИСХОДНИКИ/`) — RAW/PSD файлы, не для поиска
- **Разработка продукта** — не контент

### Rate Limiting

- Gemini Embedding 2: до 6 изображений за запрос
- Бесплатный тарифр: ограничения RPM (уточнить при реализации)
- Пауза 2 сек между батчами
- Exponential backoff при 429

### Incremental Indexing

1. При запуске: загружаем set(md5) всех уже проиндексированных файлов
2. Для каждого файла с диска: если md5 есть в set — пропускаем
3. Новые файлы: индексируем
4. Удалённые файлы: помечаем (или удаляем) из БД
5. Запуск: `python -m services.content_kb.scripts.index_all`

## Micro-Agent: content-searcher

Файл: `agents/v3/agents/content-searcher.md`

```markdown
# Agent: content-searcher

## Role
Search and retrieve visual content (photos, images) from the brand's Yandex.Disk
content library. Answer questions like "find catalog photos of Bella in black"
or "show me AB test images from September". Return previews and download links.

## Rules
- Parse user query to extract metadata filters (model_name, color, sku, category)
  before doing vector search — metadata filters narrow results and improve speed
- Always combine vector search with available metadata filters
- If query mentions a specific model name, ALWAYS add filter_model
- If query mentions a color, ALWAYS add filter_color
- model_name matching is case-insensitive
- Known models: Alice, Audrey, Bella, Charlotte, Eva, Joy, Lana, Miafull,
  Moon, Ruby, Space, Valery, Vuki, Wendy
- Known colors: black, white, beige, brown, light_beige
- If more than 10 results found, show top 5 with previews +
  text summary of remaining ("ещё 15 фото в папке Bella-black")
- For each result, provide: preview image, full disk path, similarity score
- Preview URLs are temporary (generated on the fly via Yandex Disk API)

## MCP Tools
- wookiee-content: search_content, list_content, get_content_stats

## Output Format
JSON artifact with:
- query: string (original user query)
- filters_applied: {model_name, color, category, sku} (null if not applied)
- total_found: int
- results: [{disk_path, file_name, preview_url, similarity, model_name,
  color, category, sku}]
- summary_text: string (brief description of what was found)
```

## MCP Server: wookiee-content

### Tools

#### `search_content`
Векторный поиск по контенту с metadata-фильтрами.

**Input:**
- `query` (string, required) — текстовый запрос для поиска
- `limit` (int, default 10) — макс. количество результатов
- `model_name` (string, optional) — фильтр по модели
- `color` (string, optional) — фильтр по цвету
- `category` (string, optional) — фильтр по категории контента
- `sku` (string, optional) — фильтр по артикулу
- `min_similarity` (float, default 0.3) — минимальный порог сходства
- `include_preview` (bool, default true) — генерировать превью-ссылки

**Output:**
```json
{
  "total": 5,
  "results": [
    {
      "disk_path": "/Контент/2025/5. МАРКЕТПЛЕЙСЫ/Bella/Bella-black/257144777/01.png",
      "file_name": "01.png",
      "preview_url": "https://downloader.disk.yandex.ru/preview/...",
      "similarity": 0.87,
      "model_name": "Bella",
      "color": "black",
      "category": "маркетплейсы",
      "sku": "257144777"
    }
  ]
}
```

#### `list_content`
Список контента по metadata-фильтрам (без векторного поиска).

**Input:**
- `model_name`, `color`, `category`, `sku` (all optional)
- `limit` (int, default 50)
- `offset` (int, default 0)

#### `get_content_stats`
Статистика по проиндексированному контенту.

**Output:**
```json
{
  "total_assets": 3500,
  "by_category": {"маркетплейсы": 1200, "фото": 900, ...},
  "by_model": {"Bella": 350, "Vuki": 280, ...},
  "last_indexed": "2026-03-21T12:00:00Z"
}
```

## Yandex Disk OAuth Setup

### Шаг 1: Создать приложение

1. Перейти на https://oauth.yandex.ru/client/new
2. Заполнить:
   - Название: `Wookiee Content KB`
   - Платформа: **Веб-сервисы** → URL для разработки: `http://localhost`
3. Права доступа: выбрать **Яндекс.Диск**:
   - `cloud_api:disk.app_folder` — доступ к папке приложения
   - `cloud_api:disk.read` — чтение всех файлов на Диске
4. Сохранить → получить **client_id** и **client_secret**

### Шаг 2: Получить OAuth-токен

1. Открыть в браузере:
   ```
   https://oauth.yandex.ru/authorize?response_type=token&client_id=YOUR_CLIENT_ID
   ```
2. Авторизоваться аккаунтом `Wookiee.shop@yandex.com`
3. Подтвердить доступ
4. Скопировать `access_token` из URL-редиректа

### Шаг 3: Сохранить в проект

Добавить в `.env`:
```
YANDEX_DISK_TOKEN=your_oauth_token_here
```

### Шаг 4: Проверить

```python
import yadisk
client = yadisk.Client(token="your_token")
print(client.check_token())  # True
print(list(client.listdir("/")))  # список файлов
```

## File Structure

```
services/content_kb/
├── __init__.py
├── __main__.py              # uvicorn entrypoint
├── config.py                # YANDEX_DISK_TOKEN, embedding config, DB connection
├── embedder.py              # GeminiEmbedder (reuse pattern from knowledge_base)
├── store.py                 # ContentStore — pgvector CRUD
├── yadisk_client.py         # Yandex Disk OAuth client wrapper
├── indexer.py               # Index pipeline: list → download → embed → store
├── search.py                # Search: query embed → pgvector → preview URLs
├── path_parser.py           # Parse disk path → metadata (model, color, sku, category)
├── mcp_server.py            # MCP tools: search_content, list_content, get_content_stats
├── app.py                   # FastAPI (optional, for standalone testing)
│
├── migrations/
│   └── 001_create_content_assets.py
│
└── scripts/
    ├── index_all.py         # Full indexing: python -m services.content_kb.scripts.index_all
    └── search_cli.py        # CLI test: python -m services.content_kb.scripts.search_cli "query"

agents/v3/agents/
└── content-searcher.md      # Micro-agent definition
```

## Cost Estimate

| Операция | Объём | Стоимость |
|----------|-------|-----------|
| Индексация фото (embedding) | ~5000 фото | ~$0.60 |
| Поисковые запросы (embedding) | ~100/день | ~$0.01/день |
| Supabase pgvector | Существующий инстанс | $0 (доп.) |
| Yandex Disk API | Бесплатно | $0 |
| **Итого старт** | | **~$1** |
| **Итого в месяц** | | **~$0.30** |

## Future Enhancements (не в этой фазе)

1. **Подход B**: Vision-описания через Gemini Flash → структурированные поля (поза, фон, инфографика, модель-человек)
2. **Видео-индексация**: Gemini Embedding 2 поддерживает видео до 120 сек
3. **Обогащение метриками**: CTR, конверсия из рекламных кабинетов → привязка к content_assets
4. **Telegram-бот**: интерфейс для команды — "подбери 3 фото для карточки Bella"
5. **Дедупликация**: поиск визуальных дубликатов через similarity threshold > 0.95
6. **Автотегирование**: при добавлении нового фото — автоматически определять модель/цвет если не в пути
