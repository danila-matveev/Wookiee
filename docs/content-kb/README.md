# Content Knowledge Base

Семантический поиск по фотобазе бренда. ~10,000 фото проиндексированы мультимодальной моделью Gemini Embedding 2 и хранятся в Supabase pgvector. Поиск по текстовому описанию + фильтрация по метаданным (модель, цвет, категория, артикул).

## Архитектура

```
Yandex.Disk (хранилище фото)
    ↓ list_images_recursive()
Python indexer (нормализация + дедупликация по MD5)
    ↓ embed_image()
Gemini Embedding 2 (мультимодальная модель, 3072-dim)
    ↓ INSERT
Supabase PostgreSQL + pgvector (vector search)
    ↓ search_content()
Claude Code / MCP / API (результаты + превью)
```

## Текущий статус

- **Проиндексировано:** ~10,146 фото
- **Ошибок:** 0
- **Модели:** Alice, Audrey, Bella, Charlotte, Eva, Joy, Lana, Miafull, Moon, Ruby, Space, Valery, Vuki, Wendy
- **Категории:** фото, маркетплейсы, сайт, lamoda, блогеры, дизайн, аб_тесты
- **Корни:** `/Wookiee/Контент/2025`, `/Wookiee/Контент/2026`, `/Wookiee/Блогеры`

---

## Что уже сделано

1. **Пайплайн индексации** — инкрементальный: пропускает уже проиндексированные (по MD5), определяет перемещения файлов, помечает удалённые
2. **Нормализация изображений** — HEIC/TIFF → JPEG, CMYK/P/L/LA → RGB, resize >4096px, сжатие >10MB
3. **Vector search** — текстовый запрос → embedding → cosine distance в pgvector с фильтрами по метаданным
4. **MCP tools** — `search_content`, `list_content`, `get_content_stats` для интеграции с v3 агентами
5. **Скилл `/content-search`** — интерактивный помощник для Claude Code: уточняет запрос, ищет, показывает превью
6. **Скрипты** — `index_all`, `fast_finish` (параллельный), `retry_failed`, `retry_and_finish`

---

## Схема базы данных

### Таблица `content_assets`

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| `id` | BIGSERIAL | PRIMARY KEY | Авто-ID |
| `embedding` | vector(3072) | NOT NULL | Вектор эмбеддинга (Gemini) |
| `disk_path` | TEXT | NOT NULL, UNIQUE | Полный путь на YaDisk |
| `file_name` | VARCHAR(500) | NOT NULL | Имя файла |
| `mime_type` | VARCHAR(100) | NOT NULL | MIME-тип (image/jpeg и т.д.) |
| `file_size` | BIGINT | | Размер в байтах |
| `md5` | VARCHAR(32) | NOT NULL | Хэш файла (дедупликация) |
| `year` | SMALLINT | NULL | Год (из пути) |
| `content_category` | VARCHAR(50) | | фото, маркетплейсы, дизайн и т.д. |
| `model_name` | VARCHAR(100) | | Название модели (Wendy, Bella...) |
| `color` | VARCHAR(100) | | Цвет (black, white, coffee...) |
| `sku` | VARCHAR(50) | | Артикул WB |
| `status` | VARCHAR(20) | DEFAULT 'indexed' | indexed / failed / deleted |
| `indexed_at` | TIMESTAMPTZ | DEFAULT NOW() | Дата индексации |
| `updated_at` | TIMESTAMPTZ | | Дата обновления |

### Индексы

- `idx_content_assets_model` — btree на `model_name`
- `idx_content_assets_color` — btree на `color`
- `idx_content_assets_category` — btree на `content_category`
- `idx_content_assets_sku` — btree на `sku`
- Vector index (HNSW) — создаётся при >10K записей

### RLS-политики

- `service_role_full_access_content_assets` → роль `postgres`: полный доступ
- `authenticated_select_content_assets` → роль `authenticated`: только SELECT

### SQL-функция `search_content()`

```sql
search_content(
    query_embedding vector(3072),
    match_count INT DEFAULT 10,
    filter_model VARCHAR DEFAULT NULL,
    filter_color VARCHAR DEFAULT NULL,
    filter_category VARCHAR DEFAULT NULL,
    filter_sku VARCHAR DEFAULT NULL,
    min_similarity FLOAT DEFAULT 0.3
) RETURNS TABLE (id, disk_path, file_name, similarity, model_name, color, content_category, sku, mime_type, file_size)
```

Логика: фильтрует `status = 'indexed'`, применяет метаданные-фильтры (case-insensitive через `LOWER()`), вычисляет `similarity = 1 - cosine_distance`, сортирует по близости.

**Миграция:** `services/content_kb/migrations/001_create_content_assets.py`

---

## Структура папок на Yandex.Disk

Парсер `services/content_kb/path_parser.py` извлекает метаданные из структуры папок:

```
/Wookiee/Контент/{ГОД}/{N. КАТЕГОРИЯ}/{Модель}/{Модель-цвет}/{Артикул}/файл.jpg
```

### Примеры путей

```
disk:/Wookiee/Контент/2025/1. ВСЕ ФОТО/1. Готовый контент/Wendy/1. Основные/Wendy-black/156103915/photo.jpg
→ year=2025, category=фото, model_name=Wendy, color=black, sku=156103915

disk:/Wookiee/Контент/2025/5. МАРКЕТПЛЕЙСЫ/Bella/Bella-white/163151603/2.png
→ year=2025, category=маркетплейсы, model_name=Bella, color=white, sku=163151603

disk:/Wookiee/Блогеры/Telega.In/WENDY/Креатив 1/01.jpg
→ category=блогеры (нет year, color, sku)
```

### Маппинг категорий

| Папка на диске | category в БД |
|---|---|
| `1. ВСЕ ФОТО` | `фото` |
| `2. ВИДЕО` | `видео` (не индексируется) |
| `3. ИСХОДНИКИ` | `исходники` (не индексируется) |
| `4. ДИЗАЙН` | `дизайн` |
| `5. МАРКЕТПЛЕЙСЫ` | `маркетплейсы` |
| `6. САЙТ` | `сайт` |
| `7. АБ ТЕСТЫ` | `аб_тесты` |
| `LAMODA` | `lamoda` |
| `/Блогеры/` (корень) | `блогеры` |

### Известные модели

Alice, Audrey, Bella, Charlotte, Eva, Joy, Lana, Miafull, Moon, Ruby, Space, Valery, Vuki, Wendy

Также распознаются сеты: `set_Bella`, `Set Moon` и т.д.

---

## Как добавить новые фото

### Шаг 1: Загрузить на YaDisk

Загрузите фото в правильную структуру папок:

```
/Wookiee/Контент/{ГОД}/{N. КАТЕГОРИЯ}/{Модель}/{Модель-цвет}/{Артикул}/
```

**Правила:**
- Категория с номером и точкой: `5. МАРКЕТПЛЕЙСЫ` (номер не влияет, важно название)
- Модель — одно из известных имён (case-insensitive)
- Цвет через дефис: `Wendy-black`, `Bella-light_beige`
- Артикул — папка из 6-12 цифр (опционально)
- Пропускаются: папки `видео`, `исходники`, `разработка продукта`
- Пропускаются: файлы `.svg`, `.psd`, `.ai`, `.eps`, `.pdf`

### Шаг 2: Запустить индексацию

```bash
# Полная индексация одного корня
python3 -m services.content_kb.scripts.index_all "/Wookiee/Контент/2026"

# Полная индексация дефолтного корня (из YANDEX_DISK_ROOT)
python3 -m services.content_kb.scripts.index_all

# Dry run (только посмотреть что будет проиндексировано)
python3 -m services.content_kb.scripts.index_all --dry-run "/Wookiee/Контент/2026"

# Быстрая параллельная доиндексация (4 воркера, пропускает delete detection)
python3 -m services.content_kb.scripts.fast_finish

# Retry всех failed + переиндексация
python3 -m services.content_kb.scripts.retry_and_finish

# Retry из лога
python3 -m services.content_kb.scripts.retry_failed /tmp/content_kb_fast.log
```

**Что происходит при индексации:**

1. Рекурсивный обход папок на YaDisk (API ~1 req/s на директорию)
2. Для каждого файла: проверка MD5 → пропуск / обновление пути / новый файл
3. Скачивание файла → нормализация → Gemini embedding → INSERT в pgvector
4. В конце: пометка удалённых файлов (MD5 есть в БД, но нет на диске)

### Шаг 3: Проверить результат

```bash
# Поиск по тексту
python3 -m services.content_kb.scripts.search_cli "каталожное фото Bella black"

# Статистика
python3 -c "
import json
from services.content_kb.store import ContentStore
stats = ContentStore().get_stats()
print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))
"
```

---

## Embedding (Gemini)

- **Модель:** `gemini-embedding-2-preview` (мультимодальная — понимает и текст, и изображения)
- **Размерность:** 3072 (максимум для image embeddings)
- **Task type:** `RETRIEVAL_DOCUMENT` для изображений, `RETRIEVAL_QUERY` для текстовых запросов
- **Rate limit:** 80 запросов/минуту (встроенный проактивный лимитер в `embedder.py`)
- **Retry:** экспоненциальный backoff при 429 (от 15с до 300с, до 8 попыток)

### Нормализация перед embedding

Gemini API имеет ограничения на входные изображения. Нормализатор (`indexer.py::_normalize_image`) автоматически:

| Проблема | Решение |
|---|---|
| HEIC/HEIF формат | Конвертация в JPEG (требует `pillow-heif`) |
| TIFF формат | Конвертация в JPEG |
| CMYK/P/L/LA/I/F цветовые модели | Конвертация в RGB |
| Размер > 4096px по длинной стороне | Resize с LANCZOS |
| Файл > 10MB | Re-encode в JPEG quality 85 |

---

## Как искать

### Claude Code (интерактивный скилл)

Скажи: "найди фото модели Wendy" или вызови `/content-search`. Скилл проведёт через уточнения и покажет результаты с превью.

### Python API

```python
import asyncio
from services.content_kb.search import search_content

result = asyncio.run(search_content(
    query="Фронтальное фото девушки в белье, вид спереди",
    model_name="Wendy",
    category="фото",
    limit=5,
    min_similarity=0.1,
))
# result = {"total": 5, "results": [{...}, ...]}
```

### CLI

```bash
python3 -m services.content_kb.scripts.search_cli "каталожное фото Bella"
```

### MCP Tools (для v3 агентов)

Определены в `services/content_kb/mcp_server.py`:

| Tool | Описание |
|---|---|
| `search_content` | Vector search по текстовому запросу + фильтры |
| `list_content` | Список по метаданным (без vector search) |
| `get_content_stats` | Статистика: количество по категориям и моделям |

---

## Категории и маркетинговая воронка

| Стадия воронки | Категории | Типы контента | Цель |
|---|---|---|---|
| **Awareness** (охват) | фото, сайт, блогеры | Hero shots, lifestyle, UGC, имиджевые | Привлечь внимание |
| **Consideration** (выбор) | фото, маркетплейсы, дизайн | Детальные виды, размерная сетка, инфографика | Помочь выбрать |
| **Conversion** (покупка) | маркетплейсы, lamoda | Оптимизированные карточки товара | Продать |
| **Optimization** (тесты) | аб_тесты | A/B варианты главного фото | Повысить конверсию |

---

## Конфигурация

Файл: `services/content_kb/config.py`

### Environment Variables (из `.env`)

| Переменная | Описание | Где взять |
|---|---|---|
| `GOOGLE_API_KEY` | Ключ Google AI Studio | [aistudio.google.com](https://aistudio.google.com) |
| `YANDEX_DISK_TOKEN` | OAuth токен Яндекс.Диска | [oauth.yandex.ru](https://oauth.yandex.ru) |
| `YANDEX_DISK_ROOT` | Корневая папка (default: `/Wookiee/Контент/2025`) | — |
| `POSTGRES_HOST` | Хост Supabase | Supabase Dashboard → Settings → Database |
| `POSTGRES_PORT` | Порт (default: 5432) | — |
| `POSTGRES_DB` | База (default: postgres) | — |
| `POSTGRES_USER` | Пользователь (default: postgres) | — |
| `POSTGRES_PASSWORD` | Пароль | Supabase Dashboard → Settings → Database |

### Константы

| Параметр | Значение | Описание |
|---|---|---|
| `EMBEDDING_MODEL` | `gemini-embedding-2-preview` | Модель для эмбеддингов |
| `EMBEDDING_DIMENSIONS` | 3072 | Размерность вектора |
| `INDEX_DELAY` | 1.0 сек | Задержка между запросами |
| `MAX_IMAGE_SIZE_BYTES` | 10 MB | Порог для resize |
| `MAX_IMAGE_DIMENSION` | 4096 px | Макс. длина стороны |
| `SKIP_CATEGORIES` | видео, исходники | Не индексировать |

---

## Структура файлов проекта

```
services/content_kb/
├── __init__.py
├── config.py              # Конфигурация и env vars
├── embedder.py            # Gemini Embedding 2 клиент (image + text)
├── indexer.py             # Пайплайн индексации (index_all)
├── path_parser.py         # Извлечение метаданных из путей YaDisk
├── search.py              # Точка входа поиска (search_content)
├── store.py               # pgvector store (ContentStore, ContentAsset)
├── yadisk_client.py       # YaDisk OAuth клиент (list, download, preview)
├── mcp_server.py          # MCP tool definitions для v3 агентов
├── requirements.txt       # Зависимости
├── migrations/
│   └── 001_create_content_assets.py  # Схема, индексы, RLS, SQL-функция
└── scripts/
    ├── index_all.py       # CLI: полная индексация
    ├── search_cli.py      # CLI: тестовый поиск
    ├── fast_finish.py     # Параллельная доиндексация (4 воркера)
    ├── retry_failed.py    # Retry из лога
    └── retry_and_finish.py # Reset failed + переиндексация
```

---

## Troubleshooting

| Ошибка | Причина | Решение |
|---|---|---|
| `400 Request contains an invalid argument` | HEIC/CMYK/слишком большое изображение | Нормализатор должен обрабатывать автоматически. Если нет — проверь pillow-heif |
| `429 Resource Exhausted` | Превышен rate limit Gemini | Встроенный backoff обработает. При частых — снизь CONCURRENCY |
| `504 Deadline Exceeded` | Timeout Gemini API | Retry с backoff (retry_failed.py) |
| `duplicate key value violates unique constraint` | Файл уже проиндексирован по этому пути | Безопасно игнорировать |
| `Invalid OAuth token` | Истёк токен YaDisk | Обновить `YANDEX_DISK_TOKEN` в `.env` |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Проблема с SSL | Проверить sslmode в config, обновить certifi |
| `NULL value in column "year"` | Путь без года (например /Блогеры/) | Колонка year теперь nullable |
| `No module named 'pillow_heif'` | Не установлен HEIC decoder | `pip install pillow-heif` (опционально, HEIC файлы будут пропущены) |
