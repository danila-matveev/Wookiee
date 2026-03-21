# Content Knowledge Base — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a vector search system for brand photos on Yandex.Disk using Gemini Embedding 2, integrated as a micro-agent into the v3 multi-agent system.

**Architecture:** Yandex Disk OAuth client crawls `/Контент/2025/`, downloads images, creates embeddings via Gemini Embedding 2 (3072 dims), stores in Supabase pgvector. Content-searcher micro-agent exposes search via MCP tools. Path metadata (model, color, SKU, category) extracted automatically.

**Tech Stack:** Python 3.9+, `yadisk` (Yandex Disk API), `google-generativeai` (Gemini Embedding 2), `psycopg2` + `pgvector` (Supabase), `Pillow` (image resize)

**Python 3.9 compatibility:** ALL files MUST start with `from __future__ import annotations` to enable `str | None` and `list[dict]` type hint syntax. This is a project requirement (see commit `07d55f0`).

**Deferred to Phase 2:** `__main__.py` (uvicorn), `app.py` (FastAPI standalone), cron job setup, OAuth refresh tokens (Variant B).

**Spec:** `docs/superpowers/specs/2026-03-21-content-knowledge-base-design.md`

**Reference code:** `services/knowledge_base/` — follow the same patterns (config, embedder, store, migrations)

---

### Task 1: Config and project scaffold

**Files:**
- Create: `services/content_kb/__init__.py`
- Create: `services/content_kb/config.py`

- [ ] **Step 1: Create `services/content_kb/__init__.py`**

```python
# empty init
```

- [ ] **Step 2: Create `services/content_kb/config.py`**

Follow the pattern from `services/knowledge_base/config.py`:

```python
"""
Content Knowledge Base configuration.

Reads from .env via shared pattern. DB connection reuses Supabase env vars.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')

# Yandex Disk
YANDEX_DISK_TOKEN: str = os.getenv('YANDEX_DISK_TOKEN', '')
YANDEX_DISK_ROOT: str = os.getenv('YANDEX_DISK_ROOT', '/Контент/2025')

# Gemini Embedding
GOOGLE_API_KEY: str = os.getenv('GOOGLE_API_KEY', '')
EMBEDDING_MODEL: str = 'gemini-embedding-2-preview'
EMBEDDING_DIMENSIONS: int = 3072  # Max for multimodal image embeddings

# Supabase connection (same as knowledge_base)
POSTGRES_HOST: str = os.getenv('POSTGRES_HOST', os.getenv('SUPABASE_HOST', 'localhost'))
POSTGRES_PORT: int = int(os.getenv('POSTGRES_PORT', os.getenv('SUPABASE_PORT', '5432')))
POSTGRES_DB: str = os.getenv('POSTGRES_DB', os.getenv('SUPABASE_DB', 'postgres'))
POSTGRES_USER: str = os.getenv('POSTGRES_USER', os.getenv('SUPABASE_USER', 'postgres'))
POSTGRES_PASSWORD: str = os.getenv('POSTGRES_PASSWORD', os.getenv('SUPABASE_PASSWORD', ''))

# Indexer settings
INDEX_DELAY: float = 1.0  # Seconds between embedding requests
MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024  # Resize images above 10MB
MAX_IMAGE_DIMENSION: int = 4096  # Max px on longest side after resize

# Skipped categories (not indexed in phase 1)
SKIP_CATEGORIES: set = {'видео', 'исходники'}
```

- [ ] **Step 3: Verify imports work**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -c "from services.content_kb import config; print('OK', config.EMBEDDING_DIMENSIONS)"`

Expected: `OK 3072`

- [ ] **Step 4: Commit**

```bash
git add services/content_kb/
git commit -m "feat(content-kb): add project scaffold and config"
```

---

### Task 2: Database migration

**Files:**
- Create: `services/content_kb/migrations/__init__.py`
- Create: `services/content_kb/migrations/001_create_content_assets.py`

- [ ] **Step 1: Create migration script**

Follow pattern from `services/knowledge_base/migrations/001_create_kb_tables.py`. The migration must:
1. Ensure `pgvector` extension exists
2. Create `content_assets` table (see spec for full schema)
3. Create btree indexes on `model_name`, `color`, `content_category`, `sku`
4. Enable RLS with policies for `postgres` (full) and `authenticated` (SELECT)
5. Create `search_content()` SQL function (IMPORTANT: include `ca.status = 'indexed'` filter — see updated spec)

Use the exact SQL from the spec's Data Model section. Connection pattern: copy from `services/knowledge_base/migrations/001_create_kb_tables.py` (`_env_first` helper, `SUPABASE_CONFIG` dict).

Add `if __name__ == "__main__": migrate()` at the bottom.

- [ ] **Step 2: Run migration**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python services/content_kb/migrations/001_create_content_assets.py`

Expected: Tables created successfully, no errors.

- [ ] **Step 3: Verify table exists**

Connect to Supabase and check:
```bash
python -c "
import psycopg2
from services.content_kb.config import *
conn = psycopg2.connect(host=POSTGRES_HOST, port=POSTGRES_PORT, database=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD, sslmode='require')
cur = conn.cursor()
cur.execute(\"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'content_assets' ORDER BY ordinal_position\")
for row in cur.fetchall():
    print(row)
conn.close()
"
```

- [ ] **Step 4: Commit**

```bash
git add services/content_kb/migrations/
git commit -m "feat(content-kb): add migration 001 — content_assets table + search function"
```

---

### Task 3: Path parser

**Files:**
- Create: `services/content_kb/path_parser.py`
- Create: `tests/content_kb/__init__.py`
- Create: `tests/content_kb/test_path_parser.py`

- [ ] **Step 1: Write tests for path parser**

```python
"""Tests for content_kb path_parser."""

from services.content_kb.path_parser import parse_path_metadata


def test_marketplace_full_path():
    result = parse_path_metadata(
        "/Контент/2025/5. МАРКЕТПЛЕЙСЫ/Bella/Bella-black/257144777/01.png"
    )
    assert result["year"] == 2025
    assert result["content_category"] == "маркетплейсы"
    assert result["model_name"] == "Bella"
    assert result["color"] == "black"
    assert result["sku"] == "257144777"


def test_photo_path():
    result = parse_path_metadata(
        "/Контент/2025/1. ВСЕ ФОТО/1. Готовый контент/Bella/1. Основные/Bella-black/photo.jpg"
    )
    assert result["year"] == 2025
    assert result["content_category"] == "фото"
    assert result["model_name"] == "Bella"
    assert result["color"] == "black"
    assert result["sku"] is None


def test_bloggers_path():
    result = parse_path_metadata("/Блогеры/Реклама блогеров/campaign_1/photo.jpg")
    assert result["content_category"] == "блогеры"
    assert result["model_name"] is None


def test_design_path():
    result = parse_path_metadata("/Контент/2025/4. ДИЗАЙН/banners/img.png")
    assert result["content_category"] == "дизайн"


def test_set_model():
    result = parse_path_metadata(
        "/Контент/2025/5. МАРКЕТПЛЕЙСЫ/set_Bella/set_Bella-white/123/01.png"
    )
    assert result["model_name"] == "set_Bella"
    assert result["color"] == "white"


def test_ab_test_path():
    result = parse_path_metadata(
        "/Контент/2025/7. АБ тесты /Сентябрь/Bella/variant_a.png"
    )
    assert result["content_category"] == "аб_тесты"
    assert result["model_name"] == "Bella"


def test_color_extraction_from_compound_name():
    """Bella-light_beige → model=Bella, color=light_beige"""
    result = parse_path_metadata(
        "/Контент/2025/5. МАРКЕТПЛЕЙСЫ/Bella/Bella-light_beige/123/01.png"
    )
    assert result["model_name"] == "Bella"
    assert result["color"] == "light_beige"


def test_lamoda_path():
    result = parse_path_metadata("/Контент/2025/8. LAMODA/Bella/photo.jpg")
    assert result["content_category"] == "lamoda"
    assert result["model_name"] == "Bella"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/content_kb/test_path_parser.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'services.content_kb.path_parser'`

- [ ] **Step 3: Implement path parser**

Create `services/content_kb/path_parser.py`:

The parser must:
1. Extract `year` from path (regex `\b(20\d{2})\b`)
2. Map category folder names to `content_category` using the mapping table in the spec
3. Detect `model_name` from known models list: `Alice, Audrey, Bella, Charlotte, Eva, Joy, Lana, Miafull, Moon, Ruby, Space, Valery, Vuki, Wendy` + set variants (`set_Bella`, `Set Moon`, etc.)
4. Extract `color` from compound folder names like `Bella-black` → `black`, `Bella-light_beige` → `light_beige`
5. Detect `sku` — pure numeric folder name (all digits, typically 6-12 chars)
6. Return dict with keys: `year`, `content_category`, `model_name`, `color`, `sku` (None for missing)

Important implementation details:
- Category mapping uses regex on folder names: `re.search(r'^\d+\.\s*(.+)$', folder)` to strip numbering
- Model names match case-insensitively against known list
- Color extracted by splitting `ModelName-color` pattern from folder name
- SKU is a folder name that matches `^\d{6,12}$`
- Path parsing walks path components from root to leaf

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/content_kb/test_path_parser.py -v`

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/content_kb/path_parser.py tests/content_kb/
git commit -m "feat(content-kb): add path parser with tests"
```

---

### Task 4: Yandex Disk client

**Files:**
- Create: `services/content_kb/yadisk_client.py`
- Create: `tests/content_kb/test_yadisk_client.py`

- [ ] **Step 1: Install yadisk dependency**

Run: `pip install yadisk`

Add `yadisk>=3.4.0` to `services/content_kb/requirements.txt` (create this file).

- [ ] **Step 2: Write tests (unit tests with mocked yadisk)**

```python
"""Tests for YaDisk client wrapper — unit tests with mocked yadisk."""

from unittest.mock import MagicMock, patch
from services.content_kb.yadisk_client import YaDiskClient


def test_list_images_filters_non_images():
    """Only image/* mime types should be returned."""
    client = YaDiskClient.__new__(YaDiskClient)
    client._client = MagicMock()

    mock_items = [
        MagicMock(type="file", path="/a.png", mime_type="image/png", md5="abc", size=100, name="a.png"),
        MagicMock(type="file", path="/b.docx", mime_type="application/docx", md5="def", size=200, name="b.docx"),
        MagicMock(type="dir", path="/subdir", mime_type=None, md5=None, size=None, name="subdir"),
    ]
    client._client.listdir = MagicMock(return_value=iter(mock_items))

    results = list(client._list_dir_images("/test"))
    assert len(results) == 1
    assert results[0]["path"] == "/a.png"


def test_should_skip_category():
    """Videos and sources should be skipped."""
    client = YaDiskClient.__new__(YaDiskClient)
    assert client._should_skip("/Контент/2025/2. ВИДЕО/something") is True
    assert client._should_skip("/Контент/2025/3. ИСХОДНИКИ/file.psd") is True
    assert client._should_skip("/Контент/2025/5. МАРКЕТПЛЕЙСЫ/Bella/photo.png") is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/content_kb/test_yadisk_client.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement YaDisk client**

Create `services/content_kb/yadisk_client.py`:

```python
"""
Yandex Disk OAuth client wrapper.

Provides recursive file listing, image download, and preview URL generation.
Uses yadisk library for API access.
"""

from __future__ import annotations

import logging
from typing import Iterator

import yadisk

from . import config

logger = logging.getLogger(__name__)

# Folders to skip (not indexed in phase 1)
_SKIP_PATTERNS = {'видео', 'исходники', 'разработка продукта'}


class YaDiskClient:
    """Wrapper around yadisk.Client for content indexing."""

    def __init__(self, token: str | None = None):
        self._client = yadisk.Client(token=token or config.YANDEX_DISK_TOKEN)
        if not self._client.check_token():
            raise ValueError("Invalid Yandex Disk OAuth token")
        logger.info("YaDiskClient initialized, token valid")

    def _should_skip(self, path: str) -> bool:
        """Check if path belongs to a skipped category."""
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in _SKIP_PATTERNS)

    def _list_dir_images(self, path: str) -> list[dict]:
        """List image files in a single directory (non-recursive)."""
        results = []
        for item in self._client.listdir(path):
            if item.type == "file" and item.mime_type and item.mime_type.startswith("image/"):
                results.append({
                    "path": item.path,
                    "name": item.name,
                    "mime_type": item.mime_type,
                    "md5": item.md5,
                    "size": item.size,
                })
        return results

    def list_images_recursive(self, root: str | None = None) -> Iterator[dict]:
        """Recursively list all image files under root."""
        root = root or config.YANDEX_DISK_ROOT
        dirs_to_visit = [root]

        while dirs_to_visit:
            current = dirs_to_visit.pop(0)
            if self._should_skip(current):
                logger.debug("Skipping: %s", current)
                continue

            logger.info("Scanning: %s", current)
            try:
                for item in self._client.listdir(current):
                    if item.type == "dir":
                        dirs_to_visit.append(item.path)
                    elif item.type == "file" and item.mime_type and item.mime_type.startswith("image/"):
                        yield {
                            "path": item.path,
                            "name": item.name,
                            "mime_type": item.mime_type,
                            "md5": item.md5,
                            "size": item.size,
                        }
            except Exception as e:
                logger.warning("Error listing %s: %s", current, e)

    def download_bytes(self, path: str) -> bytes:
        """Download file content as bytes."""
        import io
        buf = io.BytesIO()
        self._client.download(path, buf)
        buf.seek(0)
        return buf.read()

    def get_preview_url(self, path: str, size: str = "L") -> str | None:
        """Get preview URL for a file. Returns None if not available."""
        try:
            meta = self._client.get_meta(path, fields=["preview"])
            return getattr(meta, 'preview', None)
        except Exception:
            return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/content_kb/test_yadisk_client.py -v`

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add services/content_kb/yadisk_client.py services/content_kb/requirements.txt tests/content_kb/test_yadisk_client.py
git commit -m "feat(content-kb): add Yandex Disk client with recursive listing"
```

---

### Task 5: Image embedder

**Files:**
- Create: `services/content_kb/embedder.py`

- [ ] **Step 1: Implement image embedder**

Adapt pattern from `services/knowledge_base/embedder.py` but for images:

```python
"""
Gemini Embedding 2 client for images.

Uses google-generativeai SDK with gemini-embedding-2-preview model.
Embeds images natively (multimodal) with retry and rate limiting.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import google.generativeai as genai

from . import config

logger = logging.getLogger(__name__)

MAX_RETRIES = 8
BASE_BACKOFF = 15
MAX_BACKOFF = 300


class ImageEmbedder:
    """Gemini Embedding 2 for image embeddings."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
    ):
        self.api_key = api_key or config.GOOGLE_API_KEY
        self.model = model or config.EMBEDDING_MODEL
        self.dimensions = dimensions or config.EMBEDDING_DIMENSIONS
        self._request_count = 0
        self._last_reset = time.time()

        genai.configure(api_key=self.api_key)
        logger.info("ImageEmbedder: model=%s, dims=%d", self.model, self.dimensions)

    async def _call_with_retry(self, func, *args, **kwargs):
        """Call with exponential backoff on 429."""
        for attempt in range(MAX_RETRIES):
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    wait = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                    logger.warning("Rate limited (attempt %d/%d), waiting %ds...",
                                   attempt + 1, MAX_RETRIES, wait)
                    await asyncio.sleep(wait)
                    self._request_count = 0
                    self._last_reset = time.time()
                else:
                    raise
        raise RuntimeError(f"Max retries ({MAX_RETRIES}) exceeded")

    async def _rate_limit(self):
        """Proactive rate limiter."""
        now = time.time()
        if now - self._last_reset > 60:
            self._request_count = 0
            self._last_reset = now

        if self._request_count >= 80:
            wait = 60 - (now - self._last_reset) + 1
            if wait > 0:
                logger.info("Rate limit pause: sleeping %.0fs", wait)
                await asyncio.sleep(wait)
                self._request_count = 0
                self._last_reset = time.time()

    async def embed_image(self, image_bytes: bytes, mime_type: str = "image/png") -> list[float]:
        """Embed a single image. Returns vector of `self.dimensions` floats."""
        await self._rate_limit()

        # Use genai.types for inline data
        from google.generativeai import types
        part = types.BlobDict(mime_type=mime_type, data=image_bytes)

        result = await self._call_with_retry(
            genai.embed_content,
            model=f"models/{self.model}",
            content=part,
            output_dimensionality=self.dimensions,
        )
        self._request_count += 1
        return result["embedding"]

    async def embed_query(self, query: str) -> list[float]:
        """Embed a text query for searching against image embeddings."""
        await self._rate_limit()

        result = await self._call_with_retry(
            genai.embed_content,
            model=f"models/{self.model}",
            content=query,
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=self.dimensions,
        )
        self._request_count += 1
        return result["embedding"]
```

Key difference from text embedder: `embed_image` uses `types.BlobDict` instead of string content. No `task_type` for images (not supported for image input). `embed_query` uses text with `RETRIEVAL_QUERY` — same embedding space.

- [ ] **Step 2: Commit**

```bash
git add services/content_kb/embedder.py
git commit -m "feat(content-kb): add image embedder (Gemini Embedding 2)"
```

---

### Task 6: Content store (pgvector CRUD)

**Files:**
- Create: `services/content_kb/store.py`
- Create: `tests/content_kb/test_store.py`

- [ ] **Step 1: Write store tests**

Tests that don't require DB connection (data classes, query building):

```python
"""Tests for ContentStore data classes."""

from services.content_kb.store import ContentAsset


def test_content_asset_creation():
    asset = ContentAsset(
        disk_path="/test/path.png",
        file_name="path.png",
        mime_type="image/png",
        file_size=1000,
        md5="abc123",
        embedding=[0.1] * 3072,
        year=2025,
        content_category="маркетплейсы",
        model_name="Bella",
        color="black",
        sku="257144777",
    )
    assert asset.disk_path == "/test/path.png"
    assert len(asset.embedding) == 3072
    assert asset.status == "indexed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/content_kb/test_store.py -v`

Expected: FAIL

- [ ] **Step 3: Implement ContentStore**

Create `services/content_kb/store.py`. Follow pattern from `services/knowledge_base/store.py`:

The store must have:
- `ContentAsset` dataclass: all table fields
- `SearchResult` dataclass: search output
- `ContentStore` class with methods:
  - `__init__()` — connection params from config
  - `_get_conn()` — psycopg2 + register_vector
  - `insert(asset: ContentAsset) -> int` — INSERT, return id
  - `update_path(md5: str, new_path: str, metadata: dict)` — for moved files
  - `mark_failed(disk_path: str, error: str)` — UPDATE status='failed'
  - `mark_deleted(paths: list[str])` — UPDATE status='deleted'
  - `get_indexed_files() -> dict[str, str]` — {md5: disk_path} for incremental check
  - `search(query_embedding, limit, model_name, color, category, sku, min_similarity) -> list[SearchResult]` — calls search_content() SQL function
  - `get_stats() -> dict` — counts by category, model
  - `list_content(model_name, color, category, sku, limit, offset) -> list[dict]` — metadata-only listing

Connection uses same Supabase env vars as knowledge_base. `register_vector(conn)` required for pgvector.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/content_kb/test_store.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/content_kb/store.py tests/content_kb/test_store.py
git commit -m "feat(content-kb): add ContentStore with pgvector CRUD"
```

---

### Task 7: Indexer pipeline

**Files:**
- Create: `services/content_kb/indexer.py`
- Create: `services/content_kb/scripts/__init__.py`
- Create: `services/content_kb/scripts/index_all.py`

- [ ] **Step 1: Implement indexer**

Create `services/content_kb/indexer.py`:

```python
"""
Content indexing pipeline.

Crawls Yandex Disk, downloads images, creates embeddings, stores in pgvector.
Incremental: skips already-indexed files, handles moves and deletes.
"""

from __future__ import annotations

import asyncio
import logging
import time
from io import BytesIO

from PIL import Image

from . import config
from .embedder import ImageEmbedder
from .path_parser import parse_path_metadata
from .store import ContentAsset, ContentStore
from .yadisk_client import YaDiskClient

logger = logging.getLogger(__name__)


def resize_image(image_bytes: bytes, max_dimension: int = 4096) -> bytes:
    """Resize image if largest side exceeds max_dimension."""
    img = Image.open(BytesIO(image_bytes))
    if max(img.size) <= max_dimension:
        return image_bytes

    old_size = img.size
    ratio = max_dimension / max(img.size)
    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
    img = img.resize(new_size, Image.LANCZOS)

    buf = BytesIO()
    fmt = "PNG" if img.mode == "RGBA" else "JPEG"
    img.save(buf, format=fmt, quality=85)
    buf.seek(0)
    logger.info("Resized %dx%d → %dx%d", *old_size, *new_size)
    return buf.read()


async def index_all(root: str | None = None, dry_run: bool = False):
    """Main indexing pipeline."""
    client = YaDiskClient()
    embedder = ImageEmbedder()
    store = ContentStore()

    # Load existing indexed files: {md5: disk_path}
    existing = store.get_indexed_files()
    logger.info("Already indexed: %d files", len(existing))

    # Scan disk
    disk_files = {}  # {md5: file_info}
    indexed_count = 0
    skipped_count = 0
    failed_count = 0
    moved_count = 0

    for file_info in client.list_images_recursive(root):
        md5 = file_info["md5"]
        disk_files[md5] = file_info

        # Already indexed, same path → skip
        if md5 in existing and existing[md5] == file_info["path"]:
            skipped_count += 1
            continue

        # Already indexed, different path → moved
        if md5 in existing and existing[md5] != file_info["path"]:
            metadata = parse_path_metadata(file_info["path"])
            if not dry_run:
                store.update_path(md5, file_info["path"], metadata)
            moved_count += 1
            logger.info("Moved: %s → %s", existing[md5], file_info["path"])
            continue

        # New file → index
        if dry_run:
            logger.info("[DRY RUN] Would index: %s", file_info["path"])
            indexed_count += 1
            continue

        try:
            image_bytes = client.download_bytes(file_info["path"])

            if len(image_bytes) > config.MAX_IMAGE_SIZE_BYTES:
                image_bytes = resize_image(image_bytes, config.MAX_IMAGE_DIMENSION)

            metadata = parse_path_metadata(file_info["path"])
            embedding = await embedder.embed_image(
                image_bytes, mime_type=file_info["mime_type"]
            )

            asset = ContentAsset(
                disk_path=file_info["path"],
                file_name=file_info["name"],
                mime_type=file_info["mime_type"],
                file_size=file_info["size"],
                md5=md5,
                embedding=embedding,
                year=metadata.get("year", 2025),
                content_category=metadata.get("content_category"),
                model_name=metadata.get("model_name"),
                color=metadata.get("color"),
                sku=metadata.get("sku"),
            )
            store.insert(asset)
            indexed_count += 1
            logger.info("Indexed [%d]: %s", indexed_count, file_info["path"])

        except Exception as e:
            store.mark_failed(file_info["path"], str(e))
            failed_count += 1
            logger.warning("Failed: %s — %s", file_info["path"], e)

        await asyncio.sleep(config.INDEX_DELAY)

    # Mark deleted files
    deleted_paths = [
        path for md5, path in existing.items()
        if md5 not in disk_files
    ]
    if deleted_paths and not dry_run:
        store.mark_deleted(deleted_paths)

    logger.info(
        "Indexing complete: indexed=%d, skipped=%d, moved=%d, failed=%d, deleted=%d",
        indexed_count, skipped_count, moved_count, failed_count, len(deleted_paths),
    )
    return {
        "indexed": indexed_count,
        "skipped": skipped_count,
        "moved": moved_count,
        "failed": failed_count,
        "deleted": len(deleted_paths),
    }
```

- [ ] **Step 2: Create `services/content_kb/scripts/index_all.py`**

```python
#!/usr/bin/env python3
"""Run full content indexing pipeline."""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    from services.content_kb.indexer import index_all

    dry_run = "--dry-run" in sys.argv
    root = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            root = arg

    result = await index_all(root=root, dry_run=dry_run)
    print(f"\nResults: {result}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Add Pillow to requirements**

Add `Pillow>=10.0.0` to `services/content_kb/requirements.txt`.

- [ ] **Step 4: Test dry-run (requires YANDEX_DISK_TOKEN in .env)**

Run: `python -m services.content_kb.scripts.index_all --dry-run`

Expected: Lists files it would index without actually downloading or embedding.

- [ ] **Step 5: Commit**

```bash
git add services/content_kb/indexer.py services/content_kb/scripts/ services/content_kb/requirements.txt
git commit -m "feat(content-kb): add indexer pipeline with incremental sync"
```

---

### Task 8: Search module

**Files:**
- Create: `services/content_kb/search.py`

- [ ] **Step 1: Implement search**

```python
"""
Content search: embed text query → pgvector similarity search → preview URLs.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .embedder import ImageEmbedder
from .store import ContentStore
from .yadisk_client import YaDiskClient

logger = logging.getLogger(__name__)

# Singletons (initialized on first use)
_embedder: ImageEmbedder | None = None
_store: ContentStore | None = None
_yadisk: YaDiskClient | None = None


def _get_embedder() -> ImageEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = ImageEmbedder()
    return _embedder


def _get_store() -> ContentStore:
    global _store
    if _store is None:
        _store = ContentStore()
    return _store


def _get_yadisk() -> YaDiskClient:
    global _yadisk
    if _yadisk is None:
        _yadisk = YaDiskClient()
    return _yadisk


async def search_content(
    query: str,
    limit: int = 10,
    model_name: str | None = None,
    color: str | None = None,
    category: str | None = None,
    sku: str | None = None,
    min_similarity: float = 0.3,
    include_preview: bool = True,
) -> dict:
    """Search content by text query + metadata filters."""
    embedder = _get_embedder()
    store = _get_store()

    query_embedding = await embedder.embed_query(query)

    results = store.search(
        query_embedding=query_embedding,
        limit=limit,
        model_name=model_name,
        color=color,
        category=category,
        sku=sku,
        min_similarity=min_similarity,
    )

    items = []
    for r in results:
        item = {
            "disk_path": r.disk_path,
            "file_name": r.file_name,
            "similarity": round(r.similarity, 4),
            "model_name": r.model_name,
            "color": r.color,
            "category": r.content_category,
            "sku": r.sku,
        }

        if include_preview:
            item["preview_url"] = None  # Populated below

        items.append(item)

    # Generate preview URLs in parallel
    if include_preview and items:
        yadisk_client = _get_yadisk()
        preview_tasks = [
            asyncio.to_thread(yadisk_client.get_preview_url, item["disk_path"])
            for item in items
        ]
        previews = await asyncio.gather(*preview_tasks, return_exceptions=True)
        for item, preview in zip(items, previews):
            if isinstance(preview, str):
                item["preview_url"] = preview

    return {"total": len(items), "results": items}
```

- [ ] **Step 2: Create CLI search script**

Create `services/content_kb/scripts/search_cli.py`:

```python
#!/usr/bin/env python3
"""CLI for testing content search."""

import asyncio
import json
import sys
import logging

logging.basicConfig(level=logging.INFO)


async def main():
    from services.content_kb.search import search_content

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "каталожное фото Bella"
    print(f"Searching: {query}\n")

    result = await search_content(query, limit=5, include_preview=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Commit**

```bash
git add services/content_kb/search.py services/content_kb/scripts/search_cli.py
git commit -m "feat(content-kb): add search module with preview URL generation"
```

---

### Task 9: Micro-agent definition

**Files:**
- Create: `agents/v3/agents/content-searcher.md`

- [ ] **Step 1: Create micro-agent MD file**

Copy the exact content from the spec's "Micro-Agent: content-searcher" section into `agents/v3/agents/content-searcher.md`.

- [ ] **Step 2: Commit**

```bash
git add agents/v3/agents/content-searcher.md
git commit -m "feat(content-kb): add content-searcher micro-agent definition"
```

---

### Task 10: MCP server tools

**Files:**
- Create: `services/content_kb/mcp_server.py`

- [ ] **Step 1: Implement MCP tools**

Follow pattern from `services/knowledge_base/tools.py`. Define tool definitions and executors for:

1. `search_content` — wraps `search.search_content()`
2. `list_content` — wraps `store.list_content()`
3. `get_content_stats` — wraps `store.get_stats()`

Each tool definition is a dict with `name`, `description`, `parameters` (JSON Schema), following the MCP tool format used in the existing codebase.

The executor function takes `(tool_name: str, args: dict) -> dict` and routes to the appropriate function.

- [ ] **Step 2: Commit**

```bash
git add services/content_kb/mcp_server.py
git commit -m "feat(content-kb): add MCP server tools (search, list, stats)"
```

---

### Task 11: Integration test — end-to-end flow

**Files:**
- Create: `tests/content_kb/test_integration.py`

**Prerequisite:** `YANDEX_DISK_TOKEN` and `GOOGLE_API_KEY` in `.env`, migration 001 applied.

- [ ] **Step 1: Write integration test**

```python
"""
Integration test: index a few real images → search → verify results.

Requires:
- YANDEX_DISK_TOKEN in .env
- GOOGLE_API_KEY in .env
- Migration 001 applied

Run: pytest tests/content_kb/test_integration.py -v -s
"""

import asyncio
import pytest
from services.content_kb.config import YANDEX_DISK_TOKEN, GOOGLE_API_KEY

pytestmark = pytest.mark.skipif(
    not YANDEX_DISK_TOKEN or not GOOGLE_API_KEY,
    reason="Requires YANDEX_DISK_TOKEN and GOOGLE_API_KEY",
)


@pytest.mark.asyncio
async def test_index_and_search_single_folder():
    """Index a small folder and search for images."""
    from services.content_kb.indexer import index_all
    from services.content_kb.search import search_content

    # Index just one small folder (few files)
    result = await index_all(
        root="/Контент/2025/5. МАРКЕТПЛЕЙСЫ/Bella/Bella-black/257144777"
    )
    assert result["indexed"] > 0 or result["skipped"] > 0

    # Search
    search_result = await search_content(
        "каталожное фото нижнего белья",
        limit=3,
        include_preview=False,
    )
    assert search_result["total"] > 0
    assert search_result["results"][0]["similarity"] > 0.0


@pytest.mark.asyncio
async def test_search_with_filter():
    """Search with metadata filter."""
    from services.content_kb.search import search_content

    result = await search_content(
        "фото",
        model_name="Bella",
        color="black",
        limit=5,
        include_preview=False,
    )
    for item in result["results"]:
        assert item["model_name"].lower() == "bella"
        assert item["color"].lower() == "black"
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest tests/content_kb/test_integration.py -v -s`

Expected: Tests pass (may take ~30 seconds for embedding calls).

- [ ] **Step 3: Commit**

```bash
git add tests/content_kb/test_integration.py
git commit -m "test(content-kb): add integration test — index + search"
```

---

### Task 12: Requirements and documentation

**Files:**
- Modify: `services/content_kb/requirements.txt`
- Modify: `docs/index.md` — add Content KB reference

- [ ] **Step 1: Finalize requirements.txt**

```
yadisk>=3.4.0
google-generativeai>=0.8.0
pgvector>=0.3.0
psycopg2-binary>=2.9.0
python-dotenv>=1.0.0
Pillow>=10.0.0
```

- [ ] **Step 2: Add Content KB to docs/index.md**

Add a section about Content KB service pointing to the spec and how to run:
- Index: `python -m services.content_kb.scripts.index_all`
- Search CLI: `python -m services.content_kb.scripts.search_cli "query"`
- Integration test: `pytest tests/content_kb/ -v`

- [ ] **Step 3: Commit**

```bash
git add services/content_kb/requirements.txt docs/index.md
git commit -m "docs(content-kb): add requirements and index.md reference"
```

---

## Summary

| Task | What | Est. Steps |
|------|------|-----------|
| 1 | Config + scaffold | 4 |
| 2 | DB migration | 4 |
| 3 | Path parser + tests | 5 |
| 4 | Yandex Disk client + tests | 6 |
| 5 | Image embedder | 2 |
| 6 | Content store + tests | 5 |
| 7 | Indexer pipeline | 5 |
| 8 | Search module + CLI | 3 |
| 9 | Micro-agent MD | 2 |
| 10 | MCP server tools | 2 |
| 11 | Integration test | 3 |
| 12 | Requirements + docs | 3 |

**Total: 12 tasks, ~44 steps**

**After completing all tasks:**
1. Get `YANDEX_DISK_TOKEN` (follow OAuth setup in spec)
2. Run migration: `python services/content_kb/migrations/001_create_content_assets.py`
3. Run full index: `python -m services.content_kb.scripts.index_all`
4. Test search: `python -m services.content_kb.scripts.search_cli "каталожное фото Bella чёрный"`
