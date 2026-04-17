# Creative KB — Design Spec

- **Author:** Danila Matveev
- **Date:** 2026-04-17
- **Status:** Draft (awaiting PoC validation)
- **Related:** `services/content_kb/` (прообраз для фото), `sku_database/` (паттерн RLS-миграций)

---

## 1. Goal

Создать единую структурированную базу **всех рекламных креативов бренда Wookiee** — видео, ЯПС-статьи, тексты АДС и АДБ — с автоматической распаковкой содержимого и привязкой performance-метрик. База должна отвечать на вопрос «какие креативы/хуки/сценарии работают» на уровне отдельных элементов контента, а не на уровне кампаний.

### Пользовательский запрос
> «Оцифровать весь видеоконтент бренда в единую систему, состыковать с рекламными кампаниями (АДС, АДБ, ЯПС, блогер-посевы), распаковать каждое видео на составляющие (тема, хуки, структура, транскрипт, сценарий, креатор) и статьи ЯПС (заголовок, структура, тональность, ключевые сообщения), а затем анализировать что работает.»

### Non-goals (MVP)
Следующее **не входит** в текущий scope и отложено в V2:
- Brief generator для новых креативов
- API-интеграции Instagram / VK Ads / Яндекс.Директ (в MVP — только Sheets)
- Embeddings и semantic search
- Распаковка видео YaDisk, которые **не** использовались ни в одной рекламной кампании
- Автоматический ре-unpack при изменении промпта (только ручной trigger)
- Переименование физических файлов на YaDisk (только `display_slug` в БД)

---

## 2. Staged Rollout

Гейтированный подход — тратим минимум, пока не подтверждена ценность на каждом этапе.

```
Stage 1: PoC на 1 видео
   Input:   1 видео Wendy "Полина_история про лиф" (топ по охватам 7.2M)
   Backend: Claude Code subscription (через ffmpeg frames + whisper)
   Cost:    ~$0 (subscription)
   Gate:    JSON распаковки соответствует ожиданиям пользователя
           ↓
Stage 2: Pilot — Wendy used-in-creatives
   Input:   только Wendy-видео/статьи/тексты с реальным usage в Sheets (~50-100)
   Backend: Claude Code subscription (если квота OK) → fallback Gemini API
   Cost:    $0-3
   Gate:    95%+ распаковано, 90%+ video_ref матчится, 10 случайных проверок ок
           ↓
Stage 3: Full scale — остальные 13 моделей used-in-creatives
   Input:   audrey/moon/ruby/... (~300-500 видео + ~100 статей + ~500 текстов)
   Backend: Gemini API (через OpenRouter)
   Cost:    ~$15-20
   Gate:    Analysis ведёт к actionable insights (подтверждает ценность)
           ↓
Stage 4 (V2): Wendy ВСЕ видео (включая неиспользованные YaDisk)
   Решение принимается только после Stage 3 по реальной пользе
```

**Budget alert:** `GEMINI_MONTHLY_BUDGET_USD=30` (с запасом на итерации промпта). Срабатывает в `tool_runs` агрегате по дням — останавливает скрипты при превышении.

---

## 3. Architecture

Новый сервис `services/creative_kb/`, параллельный существующему `services/content_kb/` (фото). Переиспользует YaDisk client, path_parser и sheets_client. Отдельная PostgreSQL schema `creatives` в существующем Supabase проекте `gjvwcdtfglupewcwzfhw` — изоляция от товарной матрицы без отдельного biling'а.

### Data flow

```
YaDisk /ВИДЕО/*.mp4                 →  creatives.videos
Sheet "Статьи ЯПС"                   →  creatives.articles     (video_ref FK)
Sheet "Креативы АДС"                 →  creatives.ads_texts    (channel=ads)
Sheet "Креативы АДБ"                 →  creatives.ads_texts    (channel=adb)
                                            ↓
                                 ┌──────────┴──────────┐
                                 │  Unpack (LLM)       │
                                 │  claude_subscription│
                                 │   | claude_api      │
                                 │   | gemini_api      │
                                 └──────────┬──────────┘
                                            ↓
        creatives.video_unpacked  |  creatives.article_unpacked  |  creatives.ads_text_unpacked

Sheet "Отчёт ЯПС/АДС/АДБ ежедневный" →  creatives.usages
Sheet "Видео посевы"                   →  creatives.usages  (target=video)
public.wb_orders × campaigns.utm_tag  →  creatives.usages  (attribution)
```

### Три независимых pipeline'а

1. **Asset ingestion** — что у нас есть (crawl YaDisk + parse Sheets)
2. **Unpacking** — что внутри каждого креатива (LLM → structured JSON)
3. **Performance ingestion** — как это сработало (Sheets → usages)

Pipeline'ы не зависят друг от друга: если валится один, остальные работают.

---

## 4. Database Schema

Namespace: `creatives.*`. RLS enabled на всех таблицах. Role `anon` заблокирована. Trigger проверяет polymorphic integrity для `usages`.

### 4.1 Reference tables

```sql
CREATE SCHEMA IF NOT EXISTS creatives;

CREATE TABLE creatives.models (
  id SMALLINT PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,              -- wendy, audrey, ...
  display_name TEXT NOT NULL
);

CREATE TABLE creatives.creators (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,              -- anzhelika, polina, katya, ...
  display_name TEXT,
  yadisk_folder_hint TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE creatives.campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_sheet TEXT NOT NULL,             -- 'Статьи ЯПС' | 'Креативы АДС' | 'Креативы АДБ'
  channel TEXT NOT NULL CHECK (channel IN ('yaps','ads','adb')),
  campaign_number TEXT NOT NULL,          -- 'statya_1', 'creo_1', ...
  model_id SMALLINT REFERENCES creatives.models(id),
  color TEXT,
  sku TEXT,
  utm_tag TEXT,
  created_date DATE,
  UNIQUE (source_sheet, campaign_number, model_id, color)
);
```

### 4.2 Asset tables (что есть)

```sql
CREATE TABLE creatives.videos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  yadisk_path TEXT UNIQUE NOT NULL,
  yadisk_public_url TEXT,
  md5 TEXT,
  size_bytes BIGINT,
  duration_sec NUMERIC(6,2),
  format TEXT DEFAULT 'vertical' CHECK (format IN ('vertical','horizontal','square')),
  model_id SMALLINT REFERENCES creatives.models(id),
  color TEXT,
  creator_id UUID REFERENCES creatives.creators(id),

  display_slug TEXT,                      -- model_color_scenario_yymmdd_hash4 (generated)

  unpack_status TEXT DEFAULT 'pending'
    CHECK (unpack_status IN ('pending','processing','done','failed')),
  unpack_error TEXT,
  review_status TEXT DEFAULT 'auto'
    CHECK (review_status IN ('auto','verified','flagged')),

  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ DEFAULT NOW(),
  deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_videos_model_color ON creatives.videos(model_id, color);
CREATE INDEX idx_videos_unpack_status ON creatives.videos(unpack_status);

CREATE TABLE creatives.articles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id UUID REFERENCES creatives.campaigns(id) ON DELETE CASCADE,
  title TEXT,
  body_text TEXT NOT NULL,
  photo_url TEXT,
  rendered_url TEXT,                      -- сверстанная страница на wildberries-promo-page-wookiee.pro
  video_ref UUID REFERENCES creatives.videos(id),
  model_id SMALLINT REFERENCES creatives.models(id),
  color TEXT,
  sku TEXT,
  published_date DATE,

  unpack_status TEXT DEFAULT 'pending',
  unpack_error TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE creatives.ads_texts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id UUID REFERENCES creatives.campaigns(id) ON DELETE CASCADE,
  channel TEXT NOT NULL CHECK (channel IN ('ads','adb')),
  creo_number TEXT NOT NULL,              -- creo_1, creo_2, ...
  body_text TEXT NOT NULL,
  edits_text TEXT,                        -- колонка "Правки" из Sheets
  video_ref UUID REFERENCES creatives.videos(id),
  model_id SMALLINT REFERENCES creatives.models(id),
  color TEXT,
  sku TEXT,

  unpack_status TEXT DEFAULT 'pending',
  unpack_error TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.3 Unpack tables (что поняли про креатив)

Append-only, поддерживают версионирование. При изменении промпта — новая строка с `unpack_version=N+1` и `is_current=true`, предыдущая становится `is_current=false`.

```sql
CREATE TABLE creatives.video_unpacked (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id UUID NOT NULL REFERENCES creatives.videos(id) ON DELETE CASCADE,

  unpack_version INT NOT NULL,
  model_used TEXT NOT NULL,               -- 'claude-sonnet-4-6', 'gemini-2.5-pro', ...
  prompt_hash TEXT NOT NULL,              -- git-hash промпта из prompts/ папки
  unpacked_at TIMESTAMPTZ DEFAULT NOW(),
  is_current BOOLEAN DEFAULT TRUE,

  -- Основная распаковка (см. Appendix A для JSON schema)
  theme TEXT,
  language TEXT,
  niches TEXT[],
  tags TEXT[],
  transcript TEXT,
  transcript_segments JSONB,              -- [{start, end, text}, ...]
  gist TEXT,                              -- суть в 1-2 предложениях
  structure JSONB,                        -- [{start, end, title, description}, ...]
  visual_hook TEXT,
  text_hook TEXT,
  scenario_type TEXT,                     -- 'до-после' | 'распаковка' | 'лайфхак' | ...
  funnel_destination TEXT,                -- 'wb' | 'ozon' | 'instagram' | 'сайт'

  -- Wookiee-specific
  product_shown TEXT[],
  setting TEXT,                           -- 'home' | 'street' | 'studio' | 'cafe'
  mood TEXT,
  cta TEXT,
  creator_guess_id UUID REFERENCES creatives.creators(id),

  UNIQUE (video_id, unpack_version)
);

CREATE UNIQUE INDEX ux_video_unpacked_current
  ON creatives.video_unpacked (video_id) WHERE is_current = TRUE;

CREATE TABLE creatives.article_unpacked (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id UUID NOT NULL REFERENCES creatives.articles(id) ON DELETE CASCADE,
  unpack_version INT NOT NULL,
  model_used TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  unpacked_at TIMESTAMPTZ DEFAULT NOW(),
  is_current BOOLEAN DEFAULT TRUE,

  title_analysis TEXT,
  structure JSONB,                        -- [{section, content_summary, word_count}, ...]
  tone TEXT,                              -- 'экспертный' | 'дружеский' | ...
  visual_setup TEXT,
  product_shown TEXT[],
  key_messages TEXT[],
  text_hooks TEXT[],
  cta TEXT,
  reading_level TEXT,

  UNIQUE (article_id, unpack_version)
);

CREATE UNIQUE INDEX ux_article_unpacked_current
  ON creatives.article_unpacked (article_id) WHERE is_current = TRUE;

CREATE TABLE creatives.ads_text_unpacked (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ads_text_id UUID NOT NULL REFERENCES creatives.ads_texts(id) ON DELETE CASCADE,
  unpack_version INT NOT NULL,
  model_used TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  unpacked_at TIMESTAMPTZ DEFAULT NOW(),
  is_current BOOLEAN DEFAULT TRUE,

  headline_analysis TEXT,
  tone TEXT,
  text_hook TEXT,
  key_messages TEXT[],
  product_shown TEXT[],
  cta TEXT,
  urgency_markers TEXT[],
  social_proof_markers TEXT[],

  UNIQUE (ads_text_id, unpack_version)
);

CREATE UNIQUE INDEX ux_ads_text_unpacked_current
  ON creatives.ads_text_unpacked (ads_text_id) WHERE is_current = TRUE;
```

### 4.4 Performance table (как это сработало)

```sql
CREATE TABLE creatives.usages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target_type TEXT NOT NULL CHECK (target_type IN ('video','article','ads_text')),
  target_id UUID NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN (
    'yaps','ads','adb','seeding_blogger','seeding_vk','organic_ig','internal_wb'
  )),
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  source_sheet TEXT NOT NULL,             -- audit trail

  cost_rub NUMERIC(14,2),
  reach BIGINT,
  clicks BIGINT,
  orders_count INT,
  revenue_rub NUMERIC(14,2),
  raw_metrics JSONB,                      -- исходные Sheet-поля для верификации

  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (target_type, target_id, channel, period_start, period_end, source_sheet)
);

CREATE INDEX idx_usages_target ON creatives.usages (target_type, target_id);
CREATE INDEX idx_usages_channel_period ON creatives.usages (channel, period_start);

-- Trigger: polymorphic integrity
CREATE OR REPLACE FUNCTION creatives.check_usage_target() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.target_type = 'video' AND NOT EXISTS (SELECT 1 FROM creatives.videos WHERE id = NEW.target_id) THEN
    RAISE EXCEPTION 'target_id % not found in videos', NEW.target_id;
  ELSIF NEW.target_type = 'article' AND NOT EXISTS (SELECT 1 FROM creatives.articles WHERE id = NEW.target_id) THEN
    RAISE EXCEPTION 'target_id % not found in articles', NEW.target_id;
  ELSIF NEW.target_type = 'ads_text' AND NOT EXISTS (SELECT 1 FROM creatives.ads_texts WHERE id = NEW.target_id) THEN
    RAISE EXCEPTION 'target_id % not found in ads_texts', NEW.target_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_usages_integrity
  BEFORE INSERT OR UPDATE ON creatives.usages
  FOR EACH ROW EXECUTE FUNCTION creatives.check_usage_target();
```

### 4.5 Helper views

```sql
-- Видео с реальным usage (used-in-creatives) — основной фильтр для Stages 1-3
CREATE VIEW creatives.v_used_videos AS
SELECT DISTINCT v.*
FROM creatives.videos v
WHERE v.id IN (SELECT target_id FROM creatives.usages WHERE target_type='video')
   OR v.id IN (SELECT video_ref FROM creatives.articles WHERE video_ref IS NOT NULL)
   OR v.id IN (SELECT video_ref FROM creatives.ads_texts WHERE video_ref IS NOT NULL);

-- Сводка по видео: где использовалось
CREATE VIEW creatives.v_video_usage_summary AS
SELECT
  v.id AS video_id,
  v.yadisk_path,
  v.model_id,
  v.color,
  COUNT(DISTINCT u.channel) AS channels_used,
  ARRAY_AGG(DISTINCT u.channel) AS channels,
  SUM(u.cost_rub) AS total_cost_rub,
  SUM(u.revenue_rub) AS total_revenue_rub,
  SUM(u.clicks) AS total_clicks,
  SUM(u.reach) AS total_reach
FROM creatives.videos v
LEFT JOIN creatives.usages u ON u.target_type='video' AND u.target_id = v.id
GROUP BY v.id;
```

### 4.6 Unmatched log

```sql
CREATE TABLE creatives.unmatched_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_sheet TEXT NOT NULL,
  source_row_index INT,
  raw_data JSONB NOT NULL,                -- полная строка из Sheets
  reason TEXT NOT NULL,                   -- 'video_not_found', 'model_unknown', ...
  logged_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);
```

---

## 5. Pipeline Design

### 5.1 Asset ingestion

| Скрипт | Источник | Целевая таблица | Примечания |
|---|---|---|---|
| `scripts/index_videos.py` | YaDisk `/Wookiee/Контент/**/ВИДЕО/` + `/Wookiee/Блогеры/` | `creatives.videos` | Переиспользует `YaDiskClient` из content_kb, убирает 'видео' из SKIP_PATTERNS. md5 дедупликация. Incremental. |
| `scripts/ingest_yps_articles.py` | Sheet "Статьи ЯПС" (`1h0NeYw_5Cn7mkI03QxUk_zkvJ7NGV1zFmAtXNW9euSU`) | `creatives.articles` + `creatives.campaigns` | Matching `video_ref` по "Ссылка на видео" column. |
| `scripts/ingest_ads_texts.py` | Sheet "Креативы АДС" | `creatives.ads_texts` (channel='ads') | |
| `scripts/ingest_adb_texts.py` | Sheet "Креативы АДБ" | `creatives.ads_texts` (channel='adb') | |

**Matching `video_ref`:** нормализация YaDisk URL → поиск в `videos.yadisk_public_url`. Fallback — match по имени файла (последний segment path). Не нашли → строка в `creatives.unmatched_log`.

### 5.2 Unpacking

Backend-агностичный адаптер: `unpacker_backend = claude_subscription | claude_api | gemini_api` в `config.py`. Каждый backend имеет одинаковый интерфейс `unpack(input) -> dict`.

| Скрипт | Источник | Model (default) | Output |
|---|---|---|---|
| `scripts/unpack_videos.py` | Скачивает видео → ffmpeg keyframes + whisper transcript | claude_subscription (primary), gemini-2.5-pro (fallback) | `creatives.video_unpacked` |
| `scripts/unpack_articles.py` | `articles.body_text` (+ `rendered_url` scrape если надо) | claude_subscription | `creatives.article_unpacked` |
| `scripts/unpack_ads_texts.py` | `ads_texts.body_text` | claude_subscription | `creatives.ads_text_unpacked` |

**Версионирование:** промпты в `services/creative_kb/prompts/*.md` хранятся в git. Hash промпта пишется в `unpack_version`. При изменении промпта — re-unpack создаёт новую версию, старая сохраняется.

**Идемпотентность:** unique(target_id, unpack_version). Повторный запуск при той же версии промпта — no-op.

**Rate limiting:** `INDEX_DELAY` из config (как в content_kb). Batch обработка, graceful shutdown при budget exceeded.

### 5.3 Performance ingestion

| Скрипт | Sheet | target_type | channel |
|---|---|---|---|
| `scripts/ingest_yps_daily.py` | "Отчёт ЯПС ежедневный" | article | yaps |
| `scripts/ingest_ads_daily.py` | "Отчёт АДС ежедневный" | ads_text | ads |
| `scripts/ingest_adb_daily.py` | "Отчёт АДБ ежедневный" | ads_text | adb |
| `scripts/ingest_bloggers_seeding.py` | "Маркетинг Wookiee" → "Видео посевы" | video | seeding_blogger |
| `scripts/ingest_utm_orders.py` | `public.wb_orders` × `campaigns.utm_tag` | article / ads_text | internal_wb |

Upsert по `UNIQUE (target_type, target_id, channel, period_start, period_end, source_sheet)`. Скрипт запускается ежедневно после того, как `sheets_sync` обновил исходные таблицы.

---

## 6. Service Structure

```
services/creative_kb/
├── __init__.py
├── config.py                          # YADISK_ROOT, UNPACKER_BACKEND, BUDGET_USD
├── store.py                           # DAL для creatives.* схемы
│
├── clients/
│   ├── yadisk_client.py              # reuse из content_kb
│   ├── sheets_client.py              # reuse из sheets_sync
│   ├── claude_client.py              # subscription + API унифицированный
│   ├── gemini_client.py              # через OpenRouter
│   └── whisper_client.py             # транскрипция (локально faster-whisper)
│
├── matcher.py                         # match video_ref, campaign linking
├── path_parser.py                     # reuse из content_kb
│
├── indexers/
│   ├── video_indexer.py
│   ├── yps_articles_indexer.py
│   ├── ads_texts_indexer.py
│   └── adb_texts_indexer.py
│
├── unpackers/
│   ├── base.py                        # абстрактный Unpacker + backend registry
│   ├── video_unpacker.py              # ffmpeg frames + whisper + LLM
│   ├── article_unpacker.py            # text + photo LLM
│   └── ads_text_unpacker.py           # text LLM
│
├── performance/
│   ├── yps_daily.py
│   ├── ads_daily.py
│   ├── adb_daily.py
│   ├── bloggers_seeding.py
│   └── utm_orders.py
│
├── prompts/
│   ├── video_unpack.md                # с JSON schema
│   ├── article_unpack.md
│   └── ads_text_unpack.md
│
├── scripts/                           # CLI entry points
│   ├── index_videos.py
│   ├── index_all_assets.py
│   ├── unpack_videos.py
│   ├── unpack_articles.py
│   ├── unpack_ads_texts.py
│   ├── ingest_performance.py          # orchestrator: все 5 performance-скриптов
│   ├── pilot_report.py                # сводка после Stage 1-2
│   └── reconcile.py                   # unmatched_log resolver helper
│
├── migrations/
│   └── 001_create_creatives_schema.sql
│
└── tests/
    ├── test_matcher.py
    ├── test_path_parser.py
    └── fixtures/
```

---

## 7. Operations

### 7.1 Budget management

Перед каждым LLM-вызовом:

```python
spent_usd = compute_spent_from_tool_runs(since=month_start)
if spent_usd > config.GEMINI_MONTHLY_BUDGET_USD:
    raise BudgetExceeded(f"Spent ${spent_usd:.2f} > limit ${config.GEMINI_MONTHLY_BUDGET_USD}")
```

Telegram-alert через существующий `shared/telegram_notifier.py` при 80% бюджета.

### 7.2 RLS

Все таблицы `creatives.*` с `ENABLE ROW LEVEL SECURITY`. Политики:
- `service_role` — full access
- `authenticated` — read-only
- `anon` — заблокировано (DENY policies)

Соответствует паттерну из `sku_database/README.md`.

### 7.3 Tool registry

Регистрируются три инструмента в `public.tools`:

| slug | назначение | run_command |
|---|---|---|
| `creative-kb-ingest` | индексация assets | `python -m services.creative_kb.scripts.index_all_assets` |
| `creative-kb-unpack` | распаковка контента | `python -m services.creative_kb.scripts.unpack_videos --stage pilot` |
| `creative-kb-performance` | подтягивание метрик | `python -m services.creative_kb.scripts.ingest_performance` |

Все интегрированы с `shared/tool_logger.py`.

### 7.4 Trigger

- **Asset ingestion:** manual после изменения Sheets (или cron еженедельно)
- **Unpacking:** manual batch (разовые операции)
- **Performance:** ежедневный cron через `schedule` skill (после `sheets_sync`)

### 7.5 Observability

- `shared/tool_logger.py` — все скрипты (start/finish/error/items_processed/tokens)
- `logs/creative_kb/gemini_errors.jsonl` — для retry failed LLM calls
- `creatives.unmatched_log` — строки Sheets без match
- `scripts/pilot_report.py` — summary после каждого stage

### 7.6 Secrets

Существующие `.env` переменные (ничего нового):
- `YANDEX_DISK_TOKEN`
- `GEMINI_API_KEY` (через OpenRouter)
- `SUPABASE_SERVICE_KEY`
- `OPENROUTER_API_KEY`

---

## 8. Implementation Phases

Phases для передачи в `writing-plans`:

- **P0 — Setup:** schema migration, скелет `services/creative_kb/`, регистрация в tool_logger
- **P1 — Asset ingestion:** video indexer, 3 sheets ingesters, matcher, unmatched_log
- **P2 — PoC unpack on 1 video:** видео «Полина_история про лиф» через Claude subscription (frames + whisper) → JSON, iteration промпта с пользователем до approval
- **P3 — Unpackers (articles + ads_texts):** через Claude subscription, $0
- **P4 — Stage 2 Pilot:** Wendy used-in-creatives через `v_used_videos` view, все три типа unpackers
- **P5 — Performance ingestion:** 5 performance-скриптов, utm_orders attribution
- **P6 — Pilot validation gate:** `pilot_report.py`, ручная проверка 10 видео, metrics review
- **P7 — Stage 3 Full scale:** остальные 13 моделей used-in-creatives (Gemini API)
- **P8 — Tool registry + docs:** зарегистрировать инструменты, `docs/creative-kb/README.md`

**Total MVP estimate:** ~10 рабочих дней.

---

## 9. Deferred to V2

- **Embeddings + semantic search** (аналогично content_kb pgvector)
- **Brief generator** — после 3 месяцев накопления данных
- **API интеграции** — Instagram Graph API, VK Ads API, Яндекс.Директ API
- **Auto re-unpack on prompt change** — пока только ручной trigger
- **Wendy "all YaDisk videos"** — решается после Stage 3 по реальной пользе
- **Rename физических файлов на YaDisk** — по запросу
- **Creative similarity search** ("найди видео похожие на winner X")

---

## Appendix A — Unpacking JSON Schemas

### A.1 `video_unpacked`

```json
{
  "theme": "string — тема видео (1 фраза)",
  "language": "ru | en | ...",
  "niches": ["Бизнес и Продажи", "Маркетинг и SMM", ...],
  "tags": ["Экспертное объяснение", "Сторителлинг", ...],
  "transcript": "полный транскрипт аудио",
  "transcript_segments": [
    {"start": 0.0, "end": 3.2, "text": "..."}
  ],
  "gist": "суть в 1-2 предложениях",
  "structure": [
    {"start": "0-3s", "title": "Вопрос-челлендж",
     "description": "Девушка идёт по улице, текст на экране: ..."},
    {"start": "3-18s", "title": "Разбор принципов", "description": "..."},
    {"start": "конец", "title": "Финальный панчлайн", "description": "..."}
  ],
  "visual_hook": "что цепляет глаз в первые 3 секунды",
  "text_hook": "текстовый хук / надпись на экране",
  "scenario_type": "до-после | распаковка | лайфхак | обзор | отзыв | разговорное | ...",
  "funnel_destination": "wb | ozon | instagram | сайт",
  "product_shown": ["Wendy dark_beige", ...],
  "setting": "home | street | studio | cafe | bedroom | ...",
  "mood": "sexy | cozy | sport | bold | soft | ...",
  "cta": "призыв к действию в конце",
  "creator_guess": "имя креатора (по голосу/лицу) или null"
}
```

### A.2 `article_unpacked`

```json
{
  "title_analysis": "разбор заголовка: сила, hook, угол",
  "structure": [
    {"section": "intro", "content_summary": "...", "word_count": 42},
    {"section": "problem", "content_summary": "..."},
    {"section": "solution", "content_summary": "..."},
    {"section": "cta", "content_summary": "..."}
  ],
  "tone": "экспертный | дружеский | агрессивный | ироничный | ...",
  "visual_setup": "какое фото, каков сетап (крупный план / лайфстайл / ...)",
  "product_shown": ["Wendy Bezh"],
  "key_messages": ["визуально увеличивает грудь", "бесшовный крой", ...],
  "text_hooks": ["Находка на WB!", "прямо так — с буквами — и забирай", ...],
  "cta": "Вбивай артикул ... и забирай со скидкой",
  "reading_level": "easy | medium | hard"
}
```

### A.3 `ads_text_unpacked`

```json
{
  "headline_analysis": "разбор первых двух предложений",
  "tone": "...",
  "text_hook": "первая фраза, которая цепляет",
  "key_messages": ["..."],
  "product_shown": ["..."],
  "cta": "...",
  "urgency_markers": ["прямо сейчас", "со скидкой 90%", ...],
  "social_proof_markers": ["лучший", "популярный", "отзывы", ...]
}
```

---

## Appendix B — Open Decisions

Ниже отмечено как решено и что остаётся открытым до PoC.

| # | Вопрос | Решение |
|---|---|---|
| 1 | Отдельная БД vs schema | ✅ schema `creatives` в существующем Supabase |
| 2 | Scope MVP | ✅ Вариант B — видео + статьи + тексты АДС/АДБ через Sheets (без API) |
| 3 | Распаковка статей | ✅ Да, своим шаблоном |
| 4 | Моделирование сущностей | ✅ Вариант B — specialized tables + polymorphic usages |
| 5 | Формат видео | ✅ Только vertical (Reels/TikTok) |
| 6 | Video_id / reuse | ✅ One file = one video_id, reuse через video_ref FK |
| 7 | Creator | ✅ Отдельная таблица `creators` с nullable FK |
| 8 | Versioning unpacks | ✅ Append-only (unpack_version + is_current) |
| 9 | Renaming files YaDisk | ✅ Нет. Только display_slug в БД |
| 10 | Pilot model | ✅ Wendy |
| 11 | PoC video | ✅ "Полина_история про лиф" Wendy/dark_beige |
| 12 | Budget alert | ✅ $30 (с запасом на итерации) |
| 13 | Backend LLM | ✅ Claude subscription primary, Gemini fallback (через адаптер) |
| 14 | Used-in-creatives фильтр | ✅ Default для всех stages 1-3 |
| 15 | Embedding | 🔜 V2 |
| 16 | Finalized video unpacking template | ⏳ Будет зафиксирован после PoC на «Полина_история про лиф» |
