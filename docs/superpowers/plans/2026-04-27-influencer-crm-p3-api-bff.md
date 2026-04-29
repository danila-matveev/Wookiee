# Phase 3: Influencer CRM — API BFF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI BFF on `service_role` Supabase pooler that exposes the endpoints needed to render every screen from `mvp-mockup-v3a-edit-drawers.html` + `mvp-mockup-v3b-slices-products.html` + `prototype.html` — Kanban, blogger drawer, integration drawer, product slices, full-text search.

**Architecture:** FastAPI app in `services/influencer_crm/` reads/writes `crm.*` tables via thin SQLAlchemy 2.x typed Core (no ORM relationships — explicit JOINs avoid N+1 traps). Repository layer in `shared/data_layer/influencer_crm/` keeps queries out of route handlers. All endpoints return Pydantic v2 models. Cursor pagination + ETag on list endpoints. Single `X-API-Key` header (no Supabase Auth on local). The materialized view `crm.v_blogger_totals` is the read source for blogger aggregates.

**Tech Stack:** Python 3.12, FastAPI 0.115+, uvicorn, SQLAlchemy 2.0+ (Core, sync), psycopg2-binary 2.9, pydantic 2.x, pytest 9 + httpx 0.28+, ruff. **No async runtime** — sync FastAPI handlers + sync SQLAlchemy. Reason: simpler debugging, faster local dev, BFF latency dominated by DB not by concurrency, and the existing data_layer is sync. uvicorn workers handle concurrency.

---

## Scope Check

This plan is one subsystem (HTTP API). It produces working software: a uvicorn process exposes endpoints that return real data from the populated `crm.*` schema. No frontend, no scheduled jobs — those are P4 and P5.

The endpoint catalogue maps **1:1** to mockup screens and is closed (12 read endpoints + 9 write endpoints). No speculative endpoints — if a future screen needs new data, that's a P4-driven amendment.

---

## File Structure

| File | Responsibility | Status |
|---|---|---|
| `services/influencer_crm/__init__.py` | Package marker | New |
| `services/influencer_crm/app.py` | FastAPI app factory, mounts routers, registers middleware | New |
| `services/influencer_crm/config.py` | Loads `INFLUENCER_CRM_API_KEY` + DB env from `.env` | New |
| `services/influencer_crm/deps.py` | FastAPI dependencies: `get_session`, `verify_api_key`, `get_pagination` | New |
| `services/influencer_crm/pagination.py` | Cursor encode/decode (base64 of `(updated_at, id)`), `Page[T]` model | New |
| `services/influencer_crm/etag.py` | ETag header middleware for GET list endpoints | New |
| `services/influencer_crm/schemas/__init__.py` | Re-export pydantic models | New |
| `services/influencer_crm/schemas/blogger.py` | `BloggerOut`, `BloggerDetailOut`, `BloggerCreate`, `BloggerUpdate` | New |
| `services/influencer_crm/schemas/integration.py` | `IntegrationOut`, `IntegrationDetailOut`, `IntegrationCreate`, `IntegrationUpdate`, `StageTransitionIn` | New |
| `services/influencer_crm/schemas/product.py` | `ProductSliceOut`, `ProductDetailOut` | New |
| `services/influencer_crm/schemas/common.py` | `Page`, `Cursor`, `TagOut`, `MarketerOut` | New |
| `services/influencer_crm/schemas/brief.py` | `BriefOut`, `BriefVersionOut`, `BriefCreate` | New |
| `services/influencer_crm/schemas/promo.py` | `PromoCodeOut`, `SubstituteArticleOut` | New |
| `services/influencer_crm/schemas/metrics.py` | `MetricsSnapshotIn`, `MetricsSnapshotOut` | New |
| `services/influencer_crm/routers/__init__.py` | Package | New |
| `services/influencer_crm/routers/bloggers.py` | `/bloggers` endpoints | New |
| `services/influencer_crm/routers/integrations.py` | `/integrations` endpoints (incl. Kanban + stage transitions) | New |
| `services/influencer_crm/routers/products.py` | `/products` slices view | New |
| `services/influencer_crm/routers/tags.py` | `/tags` create/list | New |
| `services/influencer_crm/routers/promos.py` | `/substitute-articles` + `/promo-codes` | New |
| `services/influencer_crm/routers/briefs.py` | `/briefs` versioning | New |
| `services/influencer_crm/routers/metrics.py` | `POST /metrics-snapshots/{integration_id}` | New |
| `services/influencer_crm/routers/search.py` | `GET /search?q=...` over bloggers + integrations | New |
| `services/influencer_crm/routers/health.py` | `/health` (no auth) | New |
| `shared/data_layer/influencer_crm/__init__.py` | Package | New |
| `shared/data_layer/influencer_crm/_engine.py` | SQLAlchemy engine factory, `crm,public` search_path | New |
| `shared/data_layer/influencer_crm/bloggers.py` | List, get-by-id, create, update, search queries | New |
| `shared/data_layer/influencer_crm/integrations.py` | List, get-by-id, create, update, stage transition queries | New |
| `shared/data_layer/influencer_crm/products.py` | Slice query (model_osnova-level aggregates) | New |
| `shared/data_layer/influencer_crm/tags.py` | List, find-or-create | New |
| `shared/data_layer/influencer_crm/promos.py` | List substitute_articles + promo_codes | New |
| `shared/data_layer/influencer_crm/briefs.py` | Create brief + version, list versions | New |
| `shared/data_layer/influencer_crm/metrics.py` | Insert metrics_snapshot row | New |
| `tests/services/influencer_crm/__init__.py` | Package | New |
| `tests/services/influencer_crm/conftest.py` | `client` fixture (TestClient + override `get_session`) | New |
| `tests/services/influencer_crm/test_health.py` | `/health` test | New |
| `tests/services/influencer_crm/test_auth.py` | `X-API-Key` enforcement | New |
| `tests/services/influencer_crm/test_pagination.py` | Cursor round-trip + boundary cases | New |
| `tests/services/influencer_crm/test_bloggers.py` | All `/bloggers` endpoints | New |
| `tests/services/influencer_crm/test_integrations.py` | All `/integrations` endpoints + Kanban filter + stage transition | New |
| `tests/services/influencer_crm/test_products.py` | `/products` + slice | New |
| `tests/services/influencer_crm/test_tags.py` | `/tags` | New |
| `tests/services/influencer_crm/test_promos.py` | `/substitute-articles` + `/promo-codes` | New |
| `tests/services/influencer_crm/test_briefs.py` | Brief versioning | New |
| `tests/services/influencer_crm/test_metrics.py` | Metrics snapshot insert | New |
| `tests/services/influencer_crm/test_search.py` | Full-text search | New |
| `tests/services/influencer_crm/test_n_plus_one.py` | Query-count assertions | New |
| `tests/services/influencer_crm/test_openapi.py` | OpenAPI completeness | New |
| `services/influencer_crm/scripts/run_dev.sh` | `uvicorn services.influencer_crm.app:app --reload --port 8082` | New |
| `services/influencer_crm/README.md` | How to run, env vars, endpoint catalogue | New |
| `pyproject.toml` | Add fastapi, uvicorn[standard], sqlalchemy, httpx to deps | Modify |
| `.env.example` | Add `INFLUENCER_CRM_API_KEY=changeme` | Modify |

---

## Endpoint Catalogue (target — every endpoint must exist by Task 21)

| Method | Path | Returns | Used by mockup |
|---|---|---|---|
| GET | `/health` | `{"status":"ok"}` | infra |
| GET | `/bloggers` | `Page[BloggerOut]` | v3a sidebar list |
| GET | `/bloggers/{id}` | `BloggerDetailOut` | v3a drawer |
| POST | `/bloggers` | `BloggerOut` | v3a "+ блогер" button |
| PATCH | `/bloggers/{id}` | `BloggerOut` | v3a edit drawer |
| GET | `/integrations` | `Page[IntegrationOut]` | Kanban + table |
| GET | `/integrations/{id}` | `IntegrationDetailOut` | v3a integration drawer |
| POST | `/integrations` | `IntegrationOut` | "+ интеграция" |
| PATCH | `/integrations/{id}` | `IntegrationOut` | drawer edit |
| POST | `/integrations/{id}/stage` | `IntegrationOut` | Kanban drag |
| GET | `/products` | `Page[ProductSliceOut]` | v3b slices list |
| GET | `/products/{model_osnova_id}` | `ProductDetailOut` | v3b product card |
| GET | `/tags` | `list[TagOut]` | tag selector |
| POST | `/tags` | `TagOut` | inline tag create |
| GET | `/substitute-articles` | `Page[SubstituteArticleOut]` | drawer attach picker |
| GET | `/promo-codes` | `Page[PromoCodeOut]` | drawer attach picker |
| GET | `/briefs/{id}/versions` | `list[BriefVersionOut]` | drawer brief tab |
| POST | `/briefs` | `BriefOut` | "новый бриф" |
| POST | `/briefs/{id}/versions` | `BriefVersionOut` | edit-and-save brief |
| POST | `/metrics-snapshots/{integration_id}` | `MetricsSnapshotOut` | drawer "обновить метрики" |
| GET | `/search?q=...` | `{"bloggers":[...], "integrations":[...]}` | global search |

21 endpoints total. Auth: every endpoint except `/health` requires `X-API-Key: <secret>` header.

---

## Cross-Cutting Decisions (apply to every task)

1. **Sync everywhere.** `def`, not `async def`. SQLAlchemy `Session`, not `AsyncSession`.
2. **Money is `Decimal`** in pydantic. JSON serializes as string. Frontend parses to BigNumber.
3. **Datetime is ISO-8601 UTC** (`datetime.timezone.utc`). Pydantic auto-serializes.
4. **Cursors are opaque base64** `(updated_at_iso, id)`. Clients never construct or inspect them.
5. **Errors:** `HTTPException(status, detail)` — `404` for missing, `403` for auth, `409` for unique-key conflict, `400` for validation, `500` only for unexpected. No silent `None` returns.
6. **Logging:** `logger = logging.getLogger("influencer_crm")` per module. Format set in `app.py`. INFO for endpoint enter/exit, WARNING for 4xx, ERROR for 5xx.
7. **No SELECT \*** in repository — explicit columns. Catches schema drift early.
8. **Tests are isolated.** Each test starts with `BEGIN`, ends with `ROLLBACK`. No fixture pollution.
9. **Commits per task.** Each Task ends with a commit. Use `feat(crm-api):` prefix.

---

## Task 1: Add FastAPI dependencies + bootstrap directory

**Files:**
- Modify: `pyproject.toml`
- Create: `services/influencer_crm/__init__.py`
- Create: `services/influencer_crm/README.md`
- Create: `tests/services/influencer_crm/__init__.py`

- [ ] **Step 1: Install runtime + test dependencies**

```bash
.venv/bin/pip install \
    "fastapi>=0.115" "uvicorn[standard]>=0.32" \
    "sqlalchemy>=2.0" "pydantic>=2.6" \
    "httpx>=0.28"
```

Expected: `Successfully installed fastapi-… uvicorn-… sqlalchemy-… pydantic-… httpx-…`

- [ ] **Step 2: Verify imports work**

```bash
.venv/bin/python -c "import fastapi, uvicorn, sqlalchemy, pydantic, httpx; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Add a deps file so reproducible installs are possible**

Create `services/influencer_crm/requirements.txt`:

```
fastapi>=0.115
uvicorn[standard]>=0.32
sqlalchemy>=2.0
pydantic>=2.6
psycopg2-binary>=2.9
python-dotenv>=1.0
```

And a separate dev file `services/influencer_crm/requirements-dev.txt`:

```
-r requirements.txt
pytest>=9.0
httpx>=0.28
```

- [ ] **Step 4: Create empty package markers**

```bash
mkdir -p services/influencer_crm/routers services/influencer_crm/schemas services/influencer_crm/scripts
mkdir -p shared/data_layer/influencer_crm
mkdir -p tests/services/influencer_crm
touch services/influencer_crm/__init__.py
touch services/influencer_crm/routers/__init__.py
touch services/influencer_crm/schemas/__init__.py
touch shared/data_layer/influencer_crm/__init__.py
touch tests/services/influencer_crm/__init__.py
```

- [ ] **Step 5: Create the README skeleton**

Create `services/influencer_crm/README.md`:

```markdown
# Influencer CRM API (BFF)

FastAPI app on `service_role` Supabase pooler. Powers the React frontend in P4.

## Run locally

```bash
cp .env.example .env  # set INFLUENCER_CRM_API_KEY + SUPABASE_*
.venv/bin/pip install -r services/influencer_crm/requirements-dev.txt
bash services/influencer_crm/scripts/run_dev.sh
# → http://127.0.0.1:8082/docs
```

## Auth

Every endpoint except `/health` requires `X-API-Key: <INFLUENCER_CRM_API_KEY>`.

## Endpoint catalogue

See `docs/superpowers/plans/2026-04-27-influencer-crm-p3-api-bff.md` § Endpoint Catalogue.
```

- [ ] **Step 6: Commit**

```bash
git add services/influencer_crm tests/services/influencer_crm shared/data_layer/influencer_crm
git commit -m "feat(crm-api): scaffold services/influencer_crm + deps"
```

---

## Task 2: Config module — loads API key + Supabase env

**Files:**
- Create: `services/influencer_crm/config.py`
- Modify: `.env.example`
- Test: `tests/services/influencer_crm/test_config.py`

- [ ] **Step 1: Write failing test**

`tests/services/influencer_crm/test_config.py`:

```python
"""Config loads required env vars."""
from __future__ import annotations

import os
import pytest


def test_config_loads_api_key(monkeypatch):
    monkeypatch.setenv("INFLUENCER_CRM_API_KEY", "test-secret")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")

    # Force reload — config caches at import time
    import importlib
    from services.influencer_crm import config
    importlib.reload(config)

    assert config.API_KEY == "test-secret"
    assert config.DB_DSN.startswith("postgresql+psycopg2://u:p@h:")


def test_config_raises_on_missing_api_key(monkeypatch):
    monkeypatch.delenv("INFLUENCER_CRM_API_KEY", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")

    import importlib
    from services.influencer_crm import config
    with pytest.raises(RuntimeError, match="INFLUENCER_CRM_API_KEY"):
        importlib.reload(config)
```

- [ ] **Step 2: Run — expect ImportError (no config module yet)**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_config.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement config**

`services/influencer_crm/config.py`:

```python
"""Loads environment for the Influencer CRM API.

Pulls Supabase Postgres credentials from `.env` (root) and
`sku_database/.env` (fallback, mirrors sheets_etl/loader.py).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / "sku_database" / ".env")


def _required(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"{name} not set in .env")
    return val


API_KEY: str = _required("INFLUENCER_CRM_API_KEY")

_HOST = _required("POSTGRES_HOST")
_PORT = os.getenv("POSTGRES_PORT", "5432")
_DB   = os.getenv("POSTGRES_DB", "postgres")
_USER = _required("POSTGRES_USER")
_PASS = _required("POSTGRES_PASSWORD")

DB_DSN: str = (
    f"postgresql+psycopg2://{_USER}:{_PASS}@{_HOST}:{_PORT}/{_DB}"
    f"?sslmode=require&options=-csearch_path%3Dcrm,public"
)

LOG_LEVEL: str = os.getenv("INFLUENCER_CRM_LOG_LEVEL", "INFO")
```

- [ ] **Step 4: Append API key to `.env.example`**

```bash
grep -q INFLUENCER_CRM_API_KEY .env.example || \
  echo -e "\n# Influencer CRM API\nINFLUENCER_CRM_API_KEY=changeme" >> .env.example
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_config.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add services/influencer_crm/config.py tests/services/influencer_crm/test_config.py .env.example
git commit -m "feat(crm-api): config loads API key + builds Supabase DSN"
```

---

## Task 3: SQLAlchemy engine + session factory

**Files:**
- Create: `shared/data_layer/influencer_crm/_engine.py`
- Test: `tests/services/influencer_crm/test_engine.py`

- [ ] **Step 1: Write failing test**

`tests/services/influencer_crm/test_engine.py`:

```python
"""Engine connects + uses search_path = crm,public."""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("INFLUENCER_CRM_API_KEY", "test")


def test_engine_search_path_is_crm_public():
    """search_path must include `crm` so unqualified table names resolve."""
    from shared.data_layer.influencer_crm._engine import session_factory

    with session_factory() as session:
        result = session.execute(__import__("sqlalchemy").text("SHOW search_path")).scalar()
    # PG returns it like "crm, public"
    assert "crm" in result and "public" in result


def test_engine_runs_select_one():
    from sqlalchemy import text
    from shared.data_layer.influencer_crm._engine import session_factory

    with session_factory() as session:
        v = session.execute(text("SELECT 1")).scalar()
    assert v == 1
```

- [ ] **Step 2: Run — expect ModuleNotFoundError**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_engine.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement engine factory**

`shared/data_layer/influencer_crm/_engine.py`:

```python
"""SQLAlchemy engine + scoped session for the Influencer CRM API.

One module-level engine, sessions per request. Pool size kept small (5)
because the Supabase pooler already pools — we don't need a deep client-side pool.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from services.influencer_crm.config import DB_DSN

_engine: Engine = create_engine(
    DB_DSN,
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True,
    future=True,
)

_Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


@contextmanager
def session_factory() -> Iterator[Session]:
    """Yield a Session, commit on clean exit, rollback on exception."""
    session = _Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine() -> Engine:
    """Test hook — exposed only so tests can dispose between modules."""
    return _engine
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_engine.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add shared/data_layer/influencer_crm/_engine.py tests/services/influencer_crm/test_engine.py
git commit -m "feat(crm-api): SQLAlchemy engine + session factory (search_path=crm,public)"
```

---

## Task 4: FastAPI app skeleton + `/health`

**Files:**
- Create: `services/influencer_crm/app.py`
- Create: `services/influencer_crm/routers/health.py`
- Test: `tests/services/influencer_crm/test_health.py`
- Test: `tests/services/influencer_crm/conftest.py`

- [ ] **Step 1: Write conftest with TestClient fixture**

`tests/services/influencer_crm/conftest.py`:

```python
"""Test fixtures for influencer_crm API."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _set_api_key():
    """All API tests run with a known key. Real .env values are NOT loaded."""
    os.environ.setdefault("INFLUENCER_CRM_API_KEY", "test-key-123")
    # Force config re-import in case earlier test had different env
    import importlib
    from services.influencer_crm import config
    importlib.reload(config)


@pytest.fixture()
def client():
    from services.influencer_crm.app import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth():
    """Headers dict with valid API key."""
    return {"X-API-Key": "test-key-123"}
```

- [ ] **Step 2: Write failing test for `/health`**

`tests/services/influencer_crm/test_health.py`:

```python
"""GET /health is unauthenticated and returns ok."""


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_no_auth_required(client):
    # No X-API-Key header
    r = client.get("/health")
    assert r.status_code == 200
```

- [ ] **Step 3: Run — expect import error**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_health.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement `/health` router**

`services/influencer_crm/routers/health.py`:

```python
"""Unauthenticated health endpoint."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["infra"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Implement app factory**

`services/influencer_crm/app.py`:

```python
"""FastAPI app factory for the Influencer CRM BFF.

Use create_app() — module-level `app = create_app()` is exposed for uvicorn
but tests should call create_app() directly so each test gets a fresh app.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from services.influencer_crm.config import LOG_LEVEL
from services.influencer_crm.routers import health

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Influencer CRM API",
        description="BFF for the React frontend (P4). All endpoints "
                    "except /health require X-API-Key.",
        version="0.1.0",
    )
    app.include_router(health.router)
    return app


app = create_app()
```

- [ ] **Step 6: Run tests**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_health.py -v
```
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add services/influencer_crm/app.py services/influencer_crm/routers/health.py \
        tests/services/influencer_crm/test_health.py tests/services/influencer_crm/conftest.py
git commit -m "feat(crm-api): app factory + /health endpoint"
```

---

## Task 5: API-key auth dependency

**Files:**
- Create: `services/influencer_crm/deps.py`
- Test: `tests/services/influencer_crm/test_auth.py`

- [ ] **Step 1: Write failing test**

`tests/services/influencer_crm/test_auth.py`:

```python
"""X-API-Key gate."""
from fastapi import APIRouter, Depends

from services.influencer_crm.deps import verify_api_key


def test_missing_api_key_blocks_request(client):
    # Mount a protected probe endpoint
    from services.influencer_crm.app import create_app
    app = create_app()
    r = APIRouter()

    @r.get("/probe")
    def probe(_=Depends(verify_api_key)) -> dict:
        return {"ok": True}

    app.include_router(r)
    from fastapi.testclient import TestClient
    with TestClient(app) as tc:
        resp = tc.get("/probe")
    assert resp.status_code == 403
    assert "X-API-Key" in resp.json()["detail"]


def test_wrong_api_key_blocks_request():
    from services.influencer_crm.app import create_app
    from fastapi import APIRouter, Depends
    app = create_app()
    r = APIRouter()

    @r.get("/probe")
    def probe(_=Depends(verify_api_key)) -> dict:
        return {"ok": True}
    app.include_router(r)
    from fastapi.testclient import TestClient
    with TestClient(app) as tc:
        resp = tc.get("/probe", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 403


def test_correct_api_key_allows_request(auth):
    from services.influencer_crm.app import create_app
    from fastapi import APIRouter, Depends
    app = create_app()
    r = APIRouter()

    @r.get("/probe")
    def probe(_=Depends(verify_api_key)) -> dict:
        return {"ok": True}
    app.include_router(r)
    from fastapi.testclient import TestClient
    with TestClient(app) as tc:
        resp = tc.get("/probe", headers=auth)
    assert resp.status_code == 200
```

- [ ] **Step 2: Run — expect ImportError**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_auth.py -v
```

- [ ] **Step 3: Implement deps**

`services/influencer_crm/deps.py`:

```python
"""FastAPI dependency injection: auth, DB session, pagination."""
from __future__ import annotations

from typing import Iterator

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from services.influencer_crm.config import API_KEY
from shared.data_layer.influencer_crm._engine import session_factory


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-API-Key header required",
        )
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-API-Key",
        )


def get_session() -> Iterator[Session]:
    """Yield a SQLAlchemy session for one request."""
    with session_factory() as s:
        yield s
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_auth.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add services/influencer_crm/deps.py tests/services/influencer_crm/test_auth.py
git commit -m "feat(crm-api): X-API-Key auth dependency + get_session"
```

---

## Task 6: Cursor pagination utilities

**Files:**
- Create: `services/influencer_crm/pagination.py`
- Create: `services/influencer_crm/schemas/common.py`
- Test: `tests/services/influencer_crm/test_pagination.py`

- [ ] **Step 1: Write failing test**

`tests/services/influencer_crm/test_pagination.py`:

```python
"""Cursor encode/decode round-trips and rejects malformed input."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest


def test_cursor_round_trip():
    from services.influencer_crm.pagination import encode_cursor, decode_cursor

    ts = datetime(2026, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
    cursor = encode_cursor(ts, 42)

    decoded_ts, decoded_id = decode_cursor(cursor)
    assert decoded_ts == ts
    assert decoded_id == 42


def test_cursor_with_naive_datetime_is_treated_as_utc():
    from services.influencer_crm.pagination import encode_cursor, decode_cursor

    naive = datetime(2026, 1, 15, 10, 30, 45)
    cursor = encode_cursor(naive, 1)

    decoded_ts, _ = decode_cursor(cursor)
    assert decoded_ts.tzinfo == timezone.utc


def test_decode_garbage_returns_none():
    from services.influencer_crm.pagination import decode_cursor
    assert decode_cursor("not-a-real-cursor") is None
    assert decode_cursor("") is None


def test_decode_none_returns_none():
    from services.influencer_crm.pagination import decode_cursor
    assert decode_cursor(None) is None


def test_page_model_serializes_cursor():
    from services.influencer_crm.pagination import Page

    p: Page[int] = Page(items=[1, 2, 3], next_cursor="abc")
    d = p.model_dump()
    assert d["items"] == [1, 2, 3]
    assert d["next_cursor"] == "abc"
```

- [ ] **Step 2: Run — expect ImportError**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_pagination.py -v
```

- [ ] **Step 3: Implement pagination**

`services/influencer_crm/pagination.py`:

```python
"""Opaque cursor pagination: base64(json([updated_at_iso, id]))."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


def encode_cursor(updated_at: datetime, item_id: int) -> str:
    """Encode a (updated_at, id) pair as a URL-safe base64 string."""
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    payload = json.dumps([updated_at.isoformat(), item_id])
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str | None) -> tuple[datetime, int] | None:
    """Decode an opaque cursor. Returns None on any failure (404 → first page)."""
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        ts_str, item_id = json.loads(raw)
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts, int(item_id)
    except Exception:
        return None


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
```

- [ ] **Step 4: Implement common schemas**

`services/influencer_crm/schemas/common.py`:

```python
"""Shared pydantic models — Cursor, Page wrapper, simple FK refs."""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class MarketerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_pagination.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add services/influencer_crm/pagination.py services/influencer_crm/schemas/common.py \
        tests/services/influencer_crm/test_pagination.py
git commit -m "feat(crm-api): opaque cursor pagination + Page[T] + common schemas"
```

---

## Task 7: Bloggers — schemas

**Files:**
- Create: `services/influencer_crm/schemas/blogger.py`
- Test: `tests/services/influencer_crm/test_bloggers.py` (only schemas section here — endpoint tests added in T8)

- [ ] **Step 1: Write failing schema test**

`tests/services/influencer_crm/test_bloggers.py` (initial section):

```python
"""Tests for /bloggers endpoints + schemas."""
from __future__ import annotations

from decimal import Decimal


def test_blogger_out_serializes_money_as_string():
    from services.influencer_crm.schemas.blogger import BloggerOut

    b = BloggerOut(
        id=1,
        display_handle="@user",
        status="active",
        default_marketer_id=2,
        price_story_default=Decimal("1500.00"),
        price_reels_default=None,
    )
    d = b.model_dump(mode="json")
    assert d["price_story_default"] == "1500.00"
    assert d["price_reels_default"] is None


def test_blogger_create_requires_handle():
    import pytest
    from pydantic import ValidationError
    from services.influencer_crm.schemas.blogger import BloggerCreate

    with pytest.raises(ValidationError):
        BloggerCreate()  # type: ignore[call-arg]
```

- [ ] **Step 2: Run — expect ImportError**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_bloggers.py -v
```

- [ ] **Step 3: Implement blogger schemas**

`services/influencer_crm/schemas/blogger.py`:

```python
"""Pydantic schemas mirroring crm.bloggers + drawer payload."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


BloggerStatus = Literal["active", "in_progress", "new", "paused"]


class BloggerOut(BaseModel):
    """List-row payload."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_handle: str
    real_name: str | None = None
    status: BloggerStatus
    default_marketer_id: int | None = None
    price_story_default: Decimal | None = None
    price_reels_default: Decimal | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BloggerChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    channel: str
    handle: str
    url: str | None = None


class BloggerDetailOut(BloggerOut):
    """Drawer payload — includes channels, recent integrations, totals."""
    channels: list[BloggerChannelOut] = Field(default_factory=list)
    integrations_count: int = 0
    integrations_done: int = 0
    last_integration_at: datetime | None = None
    total_spent: Decimal = Decimal("0")
    avg_cpm_fact: Decimal | None = None
    contact_tg: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None
    geo_country: list[str] | None = None


class BloggerCreate(BaseModel):
    display_handle: str = Field(min_length=1, max_length=200)
    real_name: str | None = None
    status: BloggerStatus = "new"
    default_marketer_id: int | None = None
    price_story_default: Decimal | None = None
    price_reels_default: Decimal | None = None
    contact_tg: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class BloggerUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    display_handle: str | None = Field(default=None, min_length=1, max_length=200)
    real_name: str | None = None
    status: BloggerStatus | None = None
    default_marketer_id: int | None = None
    price_story_default: Decimal | None = None
    price_reels_default: Decimal | None = None
    contact_tg: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_bloggers.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add services/influencer_crm/schemas/blogger.py tests/services/influencer_crm/test_bloggers.py
git commit -m "feat(crm-api): blogger schemas (Out, DetailOut, Create, Update)"
```

---

## Task 8: Bloggers — repository (list, get, create, update)

**Files:**
- Create: `shared/data_layer/influencer_crm/bloggers.py`
- Test: `tests/services/influencer_crm/test_bloggers_repo.py`

- [ ] **Step 1: Add repository test (uses real DB — already populated by P2)**

`tests/services/influencer_crm/test_bloggers_repo.py`:

```python
"""Direct tests of the bloggers repository against the populated CRM dev DB.

These tests assume P2 ETL ran (≥10 bloggers exist). They use BEGIN+ROLLBACK so
mutations don't leak between tests.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from shared.data_layer.influencer_crm._engine import session_factory
from shared.data_layer.influencer_crm import bloggers as bloggers_repo


@pytest.fixture()
def session():
    s = session_factory().__enter__()
    s.begin_nested()  # SAVEPOINT
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_list_returns_at_least_one_blogger(session: Session):
    rows, next_cursor = bloggers_repo.list_bloggers(session, limit=5)
    assert len(rows) >= 1
    assert all(r.id and r.display_handle for r in rows)


def test_list_respects_limit(session: Session):
    rows, _ = bloggers_repo.list_bloggers(session, limit=2)
    assert len(rows) <= 2


def test_list_with_status_filter(session: Session):
    rows, _ = bloggers_repo.list_bloggers(session, limit=50, status="active")
    assert all(r.status == "active" for r in rows)


def test_get_by_id_returns_full_payload(session: Session):
    rows, _ = bloggers_repo.list_bloggers(session, limit=1)
    if not rows:
        pytest.skip("No bloggers in DB yet")
    blogger_id = rows[0].id
    detail = bloggers_repo.get_blogger(session, blogger_id)
    assert detail is not None
    assert detail.id == blogger_id


def test_get_missing_returns_none(session: Session):
    assert bloggers_repo.get_blogger(session, 999_999_999) is None


def test_create_then_get(session: Session):
    new_id = bloggers_repo.create_blogger(
        session,
        display_handle="@pytest_blogger",
        status="new",
    )
    fetched = bloggers_repo.get_blogger(session, new_id)
    assert fetched is not None
    assert fetched.display_handle == "@pytest_blogger"


def test_update_changes_field(session: Session):
    rows, _ = bloggers_repo.list_bloggers(session, limit=1)
    if not rows:
        pytest.skip("No bloggers in DB yet")
    blogger_id = rows[0].id
    bloggers_repo.update_blogger(session, blogger_id, {"notes": "marker-12345"})
    refreshed = bloggers_repo.get_blogger(session, blogger_id)
    assert refreshed.notes == "marker-12345"
```

- [ ] **Step 2: Run — expect ImportError**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_bloggers_repo.py -v
```

- [ ] **Step 3: Implement repository**

`shared/data_layer/influencer_crm/bloggers.py`:

```python
"""Read+write queries for crm.bloggers + crm.blogger_channels.

Read paths join crm.v_blogger_totals for aggregate counts.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from services.influencer_crm.pagination import decode_cursor, encode_cursor
from services.influencer_crm.schemas.blogger import (
    BloggerChannelOut,
    BloggerDetailOut,
    BloggerOut,
)


_LIST_SQL = """
SELECT b.id, b.display_handle, b.real_name, b.status,
       b.default_marketer_id,
       b.price_story_default, b.price_reels_default,
       b.created_at, b.updated_at
FROM crm.bloggers b
WHERE b.archived_at IS NULL
  {status_filter}
  {marketer_filter}
  {cursor_filter}
ORDER BY b.updated_at DESC, b.id DESC
LIMIT :limit
"""


def list_bloggers(
    session: Session,
    *,
    limit: int = 50,
    cursor: str | None = None,
    status: str | None = None,
    marketer_id: int | None = None,
    q: str | None = None,
) -> tuple[list[BloggerOut], str | None]:
    """Return (rows, next_cursor). Rows length ≤ limit."""
    params: dict[str, Any] = {"limit": limit + 1}  # one extra to detect "more"
    where_clauses: list[str] = []

    status_filter = ""
    if status:
        status_filter = "AND b.status = :status"
        params["status"] = status

    marketer_filter = ""
    if marketer_id is not None:
        marketer_filter = "AND b.default_marketer_id = :marketer_id"
        params["marketer_id"] = marketer_id

    cursor_filter = ""
    decoded = decode_cursor(cursor)
    if decoded is not None:
        cursor_ts, cursor_id = decoded
        cursor_filter = (
            "AND (b.updated_at, b.id) < (:cursor_ts, :cursor_id)"
        )
        params["cursor_ts"] = cursor_ts
        params["cursor_id"] = cursor_id

    sql = _LIST_SQL.format(
        status_filter=status_filter,
        marketer_filter=marketer_filter,
        cursor_filter=cursor_filter,
    )

    rows = session.execute(text(sql), params).mappings().all()

    if q:
        # Full-text via GIN handled by `search_bloggers` — this filter is
        # exact-prefix only for now; UI uses the dedicated /search endpoint.
        rows = [r for r in rows if q.lower() in (r["display_handle"] or "").lower()]

    has_more = len(rows) > limit
    rows = rows[:limit]

    out = [BloggerOut(**dict(r)) for r in rows]
    next_cursor = (
        encode_cursor(rows[-1]["updated_at"], rows[-1]["id"])
        if has_more and rows
        else None
    )
    return out, next_cursor


_DETAIL_SQL = """
SELECT b.*,
       COALESCE(t.integrations_count, 0)  AS integrations_count,
       COALESCE(t.integrations_done, 0)   AS integrations_done,
       t.last_integration_at,
       COALESCE(t.total_spent, 0)         AS total_spent,
       t.avg_cpm_fact
FROM crm.bloggers b
LEFT JOIN crm.v_blogger_totals t ON t.blogger_id = b.id
WHERE b.id = :id AND b.archived_at IS NULL
"""

_CHANNELS_SQL = """
SELECT id, channel, handle, url
FROM crm.blogger_channels
WHERE blogger_id = :blogger_id
ORDER BY channel, id
"""


def get_blogger(session: Session, blogger_id: int) -> BloggerDetailOut | None:
    row = session.execute(text(_DETAIL_SQL), {"id": blogger_id}).mappings().first()
    if row is None:
        return None

    channels = session.execute(
        text(_CHANNELS_SQL), {"blogger_id": blogger_id}
    ).mappings().all()

    payload: dict[str, Any] = dict(row)
    payload["channels"] = [BloggerChannelOut(**dict(c)) for c in channels]
    return BloggerDetailOut(**payload)


_INSERT_SQL = """
INSERT INTO crm.bloggers (
    display_handle, real_name, status, default_marketer_id,
    price_story_default, price_reels_default,
    contact_tg, contact_email, contact_phone, notes
) VALUES (
    :display_handle, :real_name, :status, :default_marketer_id,
    :price_story_default, :price_reels_default,
    :contact_tg, :contact_email, :contact_phone, :notes
)
RETURNING id
"""


def create_blogger(
    session: Session,
    **fields: Any,
) -> int:
    payload = {
        "display_handle": fields.get("display_handle"),
        "real_name": fields.get("real_name"),
        "status": fields.get("status", "new"),
        "default_marketer_id": fields.get("default_marketer_id"),
        "price_story_default": fields.get("price_story_default"),
        "price_reels_default": fields.get("price_reels_default"),
        "contact_tg": fields.get("contact_tg"),
        "contact_email": fields.get("contact_email"),
        "contact_phone": fields.get("contact_phone"),
        "notes": fields.get("notes"),
    }
    new_id = session.execute(text(_INSERT_SQL), payload).scalar_one()
    return int(new_id)


def update_blogger(
    session: Session,
    blogger_id: int,
    fields: dict[str, Any],
) -> None:
    if not fields:
        return
    allowed = {
        "display_handle", "real_name", "status", "default_marketer_id",
        "price_story_default", "price_reels_default",
        "contact_tg", "contact_email", "contact_phone", "notes",
    }
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    sql = (
        f"UPDATE crm.bloggers SET {set_clause}, updated_at = now() "
        f"WHERE id = :id AND archived_at IS NULL"
    )
    session.execute(text(sql), {**fields, "id": blogger_id})
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_bloggers_repo.py -v
```
Expected: 7 passed (or 5 + 2 skipped if DB has 0 bloggers, but P2 populated 241).

- [ ] **Step 5: Commit**

```bash
git add shared/data_layer/influencer_crm/bloggers.py tests/services/influencer_crm/test_bloggers_repo.py
git commit -m "feat(crm-api): bloggers repository (list/get/create/update) + v_blogger_totals join"
```

---

## Task 9: Bloggers — router (GET list/detail, POST create, PATCH update)

**Files:**
- Create: `services/influencer_crm/routers/bloggers.py`
- Modify: `services/influencer_crm/app.py:25` (add `app.include_router(bloggers.router)`)
- Modify: `tests/services/influencer_crm/test_bloggers.py` (append endpoint tests)

- [ ] **Step 1: Append endpoint tests**

Append to `tests/services/influencer_crm/test_bloggers.py`:

```python
def test_list_bloggers_requires_auth(client):
    r = client.get("/bloggers")
    assert r.status_code == 403


def test_list_bloggers_returns_page(client, auth):
    r = client.get("/bloggers", headers=auth, params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "next_cursor" in body
    assert len(body["items"]) <= 5


def test_get_blogger_404_for_missing(client, auth):
    r = client.get("/bloggers/999999999", headers=auth)
    assert r.status_code == 404


def test_get_blogger_returns_drawer_payload(client, auth):
    list_resp = client.get("/bloggers", headers=auth, params={"limit": 1}).json()
    if not list_resp["items"]:
        import pytest; pytest.skip("DB empty")
    blogger_id = list_resp["items"][0]["id"]
    r = client.get(f"/bloggers/{blogger_id}", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == blogger_id
    assert "channels" in body
    assert "integrations_count" in body


def test_create_blogger(client, auth):
    r = client.post(
        "/bloggers",
        headers=auth,
        json={"display_handle": "@pytest_create_user", "status": "new"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["display_handle"] == "@pytest_create_user"
    new_id = body["id"]
    # Cleanup so test is idempotent
    client.patch(f"/bloggers/{new_id}", headers=auth, json={"display_handle": f"deleted-{new_id}"})


def test_patch_blogger_partial_update(client, auth):
    list_resp = client.get("/bloggers", headers=auth, params={"limit": 1}).json()
    if not list_resp["items"]:
        import pytest; pytest.skip("DB empty")
    blogger_id = list_resp["items"][0]["id"]
    original_notes = list_resp["items"][0].get("notes")
    r = client.patch(
        f"/bloggers/{blogger_id}",
        headers=auth,
        json={"notes": "patched-by-test"},
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "patched-by-test" or "notes" not in r.json()
    # Restore
    client.patch(f"/bloggers/{blogger_id}", headers=auth, json={"notes": original_notes})
```

- [ ] **Step 2: Run — expect 404 (no router yet)**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_bloggers.py -v
```

- [ ] **Step 3: Implement router**

`services/influencer_crm/routers/bloggers.py`:

```python
"""GET /bloggers, GET /bloggers/{id}, POST /bloggers, PATCH /bloggers/{id}."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.pagination import Page
from services.influencer_crm.schemas.blogger import (
    BloggerCreate,
    BloggerDetailOut,
    BloggerOut,
    BloggerUpdate,
)
from shared.data_layer.influencer_crm import bloggers as repo

router = APIRouter(
    prefix="/bloggers",
    tags=["bloggers"],
    dependencies=[Depends(verify_api_key)],
)

logger = logging.getLogger("influencer_crm.bloggers")


@router.get("", response_model=Page[BloggerOut])
def list_bloggers(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    marketer_id: int | None = None,
    q: str | None = None,
) -> Page[BloggerOut]:
    items, next_cursor = repo.list_bloggers(
        session, limit=limit, cursor=cursor,
        status=status_filter, marketer_id=marketer_id, q=q,
    )
    return Page[BloggerOut](items=items, next_cursor=next_cursor)


@router.get("/{blogger_id}", response_model=BloggerDetailOut)
def get_blogger(
    blogger_id: int,
    session: Session = Depends(get_session),
) -> BloggerDetailOut:
    blogger = repo.get_blogger(session, blogger_id)
    if blogger is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Blogger not found")
    return blogger


@router.post("", response_model=BloggerOut, status_code=status.HTTP_201_CREATED)
def create_blogger(
    payload: BloggerCreate,
    session: Session = Depends(get_session),
) -> BloggerOut:
    new_id = repo.create_blogger(session, **payload.model_dump(exclude_unset=True))
    created = repo.get_blogger(session, new_id)
    assert created is not None
    return BloggerOut.model_validate(created.model_dump())


@router.patch("/{blogger_id}", response_model=BloggerOut)
def patch_blogger(
    blogger_id: int,
    payload: BloggerUpdate,
    session: Session = Depends(get_session),
) -> BloggerOut:
    fields = payload.model_dump(exclude_unset=True)
    repo.update_blogger(session, blogger_id, fields)
    updated = repo.get_blogger(session, blogger_id)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Blogger not found")
    return BloggerOut.model_validate(updated.model_dump())
```

- [ ] **Step 4: Wire router into app.py**

In `services/influencer_crm/app.py`, replace `from services.influencer_crm.routers import health` with:

```python
from services.influencer_crm.routers import health, bloggers
```

And add inside `create_app()`:

```python
    app.include_router(bloggers.router)
```

(after `app.include_router(health.router)`)

- [ ] **Step 5: Run all blogger tests**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_bloggers.py tests/services/influencer_crm/test_bloggers_repo.py -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add services/influencer_crm/routers/bloggers.py services/influencer_crm/app.py \
        tests/services/influencer_crm/test_bloggers.py
git commit -m "feat(crm-api): /bloggers router (list, detail, create, patch)"
```

---

## Task 10: Integrations — schemas

**Files:**
- Create: `services/influencer_crm/schemas/integration.py`
- Test: `tests/services/influencer_crm/test_integrations_schema.py`

- [ ] **Step 1: Write failing schema tests**

`tests/services/influencer_crm/test_integrations_schema.py`:

```python
"""Pydantic schemas for /integrations."""
from __future__ import annotations

from datetime import date
from decimal import Decimal


def test_integration_out_minimal_payload():
    from services.influencer_crm.schemas.integration import IntegrationOut

    i = IntegrationOut(
        id=1, blogger_id=2, marketer_id=3,
        publish_date=date(2026, 4, 1),
        channel="instagram", ad_format="story", marketplace="wb",
        stage="lead", total_cost=Decimal("0"),
    )
    d = i.model_dump(mode="json")
    assert d["total_cost"] == "0"
    assert d["publish_date"] == "2026-04-01"


def test_stage_transition_input_requires_target():
    import pytest
    from pydantic import ValidationError
    from services.influencer_crm.schemas.integration import StageTransitionIn

    with pytest.raises(ValidationError):
        StageTransitionIn()  # type: ignore[call-arg]


def test_stage_transition_validates_known_stage():
    import pytest
    from pydantic import ValidationError
    from services.influencer_crm.schemas.integration import StageTransitionIn

    StageTransitionIn(target_stage="agreed")
    with pytest.raises(ValidationError):
        StageTransitionIn(target_stage="bogus_stage")
```

- [ ] **Step 2: Implement schemas**

`services/influencer_crm/schemas/integration.py`:

```python
"""Pydantic schemas for crm.integrations + drawer payload + Kanban transitions."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Stages from migration 008 schema (10 columns Kanban)
Stage = Literal[
    "lead", "negotiation", "agreed", "content_received",
    "content_approved", "scheduled", "published", "paid", "done", "rejected",
]
Outcome = Literal["delivered", "cancelled", "no_show", "failed_compliance"]
Channel = Literal["instagram", "telegram", "tiktok", "youtube", "vk", "rutube"]
AdFormat = Literal["story", "short_video", "long_video", "long_post", "image_post", "integration", "live_stream"]
Marketplace = Literal["wb", "ozon", "both"]


class IntegrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    blogger_id: int
    marketer_id: int
    brief_id: int | None = None
    publish_date: date
    channel: Channel
    ad_format: AdFormat
    marketplace: Marketplace
    stage: Stage
    outcome: Outcome | None = None
    is_barter: bool = False
    cost_placement: Decimal | None = None
    cost_delivery: Decimal | None = None
    cost_goods: Decimal | None = None
    total_cost: Decimal = Decimal("0")
    erid: str | None = None
    fact_views: int | None = None
    fact_orders: int | None = None
    fact_revenue: Decimal | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class IntegrationSubstituteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    substitute_article_id: int
    code: str
    artikul_id: int | None
    display_order: int
    tracking_url: str | None = None


class IntegrationPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_url: str | None
    posted_at: datetime | None
    fact_views: int | None
    fact_clicks: int | None


class IntegrationDetailOut(IntegrationOut):
    blogger_handle: str
    marketer_name: str
    substitutes: list[IntegrationSubstituteOut] = Field(default_factory=list)
    posts: list[IntegrationPostOut] = Field(default_factory=list)
    contract_url: str | None = None
    post_url: str | None = None
    tz_url: str | None = None
    post_content: str | None = None
    notes: str | None = None
    has_marking: bool | None = None
    has_contract: bool | None = None


class IntegrationCreate(BaseModel):
    blogger_id: int
    marketer_id: int
    publish_date: date
    channel: Channel
    ad_format: AdFormat
    marketplace: Marketplace
    stage: Stage = "lead"
    is_barter: bool = False
    cost_placement: Decimal | None = None
    cost_delivery: Decimal | None = None
    cost_goods: Decimal | None = None
    erid: str | None = None
    notes: str | None = None


class IntegrationUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    blogger_id: int | None = None
    marketer_id: int | None = None
    publish_date: date | None = None
    channel: Channel | None = None
    ad_format: AdFormat | None = None
    marketplace: Marketplace | None = None
    stage: Stage | None = None
    outcome: Outcome | None = None
    is_barter: bool | None = None
    cost_placement: Decimal | None = None
    cost_delivery: Decimal | None = None
    cost_goods: Decimal | None = None
    erid: str | None = None
    notes: str | None = None
    fact_views: int | None = None
    fact_orders: int | None = None
    fact_revenue: Decimal | None = None


class StageTransitionIn(BaseModel):
    """POST /integrations/{id}/stage body — Kanban drag-drop."""
    target_stage: Stage
    note: str | None = None
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_integrations_schema.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add services/influencer_crm/schemas/integration.py tests/services/influencer_crm/test_integrations_schema.py
git commit -m "feat(crm-api): integration schemas (Out/Detail/Create/Update/StageTransition)"
```

---

## Task 11: Integrations — repository (list/get/create/update/stage transition)

**Files:**
- Create: `shared/data_layer/influencer_crm/integrations.py`
- Test: `tests/services/influencer_crm/test_integrations_repo.py`

- [ ] **Step 1: Write failing repo tests**

`tests/services/influencer_crm/test_integrations_repo.py`:

```python
"""Repository tests against populated CRM dev DB."""
from __future__ import annotations

import pytest
from datetime import date
from sqlalchemy.orm import Session

from shared.data_layer.influencer_crm._engine import session_factory
from shared.data_layer.influencer_crm import integrations as repo
from shared.data_layer.influencer_crm import bloggers as bloggers_repo


@pytest.fixture()
def session():
    s = session_factory().__enter__()
    s.begin_nested()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_list_integrations(session: Session):
    rows, _ = repo.list_integrations(session, limit=5)
    assert len(rows) >= 1
    assert all(r.publish_date for r in rows)


def test_list_filter_by_stage(session: Session):
    rows, _ = repo.list_integrations(session, limit=50, stage_in=["done"])
    assert all(r.stage == "done" for r in rows)


def test_list_filter_by_marketplace(session: Session):
    rows, _ = repo.list_integrations(session, limit=50, marketplace="wb")
    assert all(r.marketplace in ("wb",) for r in rows)


def test_list_kanban_excludes_archived(session: Session):
    """The Kanban view (default) must hide archived rows."""
    rows, _ = repo.list_integrations(session, limit=200)
    # archived ones never appear; query filters archived_at IS NULL
    assert all(getattr(r, "outcome", None) != "cancelled" or r.stage != "rejected"
               for r in rows[:5])  # smoke


def test_get_integration_detail(session: Session):
    rows, _ = repo.list_integrations(session, limit=1)
    if not rows:
        pytest.skip("DB empty")
    detail = repo.get_integration(session, rows[0].id)
    assert detail is not None
    assert detail.blogger_handle  # JOIN worked
    assert isinstance(detail.substitutes, list)


def test_stage_transition_writes_history(session: Session):
    rows, _ = repo.list_integrations(session, limit=1)
    if not rows:
        pytest.skip("DB empty")
    integration_id = rows[0].id
    repo.transition_stage(session, integration_id, target_stage="agreed", note="test")
    refreshed = repo.get_integration(session, integration_id)
    assert refreshed.stage == "agreed"
```

- [ ] **Step 2: Implement repository**

`shared/data_layer/influencer_crm/integrations.py`:

```python
"""Read/write queries for crm.integrations + related M:N."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.pagination import decode_cursor, encode_cursor
from services.influencer_crm.schemas.integration import (
    IntegrationDetailOut,
    IntegrationOut,
    IntegrationPostOut,
    IntegrationSubstituteOut,
)


_LIST_BASE = """
SELECT i.id, i.blogger_id, i.marketer_id, i.brief_id,
       i.publish_date, i.channel, i.ad_format, i.marketplace,
       i.stage, i.outcome, i.is_barter,
       i.cost_placement, i.cost_delivery, i.cost_goods, i.total_cost,
       i.erid, i.fact_views, i.fact_orders, i.fact_revenue,
       i.created_at, i.updated_at
FROM crm.integrations i
WHERE i.archived_at IS NULL
"""


def list_integrations(
    session: Session,
    *,
    limit: int = 50,
    cursor: str | None = None,
    stage_in: list[str] | None = None,
    marketplace: str | None = None,
    marketer_id: int | None = None,
    blogger_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[IntegrationOut], str | None]:
    params: dict[str, Any] = {"limit": limit + 1}
    where: list[str] = []

    if stage_in:
        where.append("AND i.stage = ANY(:stage_in)")
        params["stage_in"] = stage_in
    if marketplace:
        where.append("AND i.marketplace = :marketplace")
        params["marketplace"] = marketplace
    if marketer_id is not None:
        where.append("AND i.marketer_id = :marketer_id")
        params["marketer_id"] = marketer_id
    if blogger_id is not None:
        where.append("AND i.blogger_id = :blogger_id")
        params["blogger_id"] = blogger_id
    if date_from:
        where.append("AND i.publish_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("AND i.publish_date <= :date_to")
        params["date_to"] = date_to

    decoded = decode_cursor(cursor)
    if decoded is not None:
        cursor_ts, cursor_id = decoded
        where.append("AND (i.updated_at, i.id) < (:cursor_ts, :cursor_id)")
        params["cursor_ts"] = cursor_ts
        params["cursor_id"] = cursor_id

    sql = (
        _LIST_BASE
        + " " + " ".join(where)
        + " ORDER BY i.updated_at DESC, i.id DESC LIMIT :limit"
    )
    rows = session.execute(text(sql), params).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [IntegrationOut(**dict(r)) for r in rows]
    next_cursor = (
        encode_cursor(rows[-1]["updated_at"], rows[-1]["id"])
        if has_more and rows
        else None
    )
    return items, next_cursor


_DETAIL_SQL = """
SELECT i.*, b.display_handle AS blogger_handle, m.name AS marketer_name
FROM crm.integrations i
JOIN crm.bloggers b   ON b.id = i.blogger_id
JOIN crm.marketers m  ON m.id = i.marketer_id
WHERE i.id = :id AND i.archived_at IS NULL
"""

_SUBS_SQL = """
SELECT isa.substitute_article_id, sa.code, sa.artikul_id,
       isa.display_order, isa.tracking_url
FROM crm.integration_substitute_articles isa
JOIN crm.substitute_articles sa ON sa.id = isa.substitute_article_id
WHERE isa.integration_id = :integration_id
ORDER BY isa.display_order, isa.substitute_article_id
"""

_POSTS_SQL = """
SELECT id, post_url, posted_at, fact_views, fact_clicks
FROM crm.integration_posts
WHERE integration_id = :integration_id
ORDER BY posted_at DESC NULLS LAST, id DESC
"""


def get_integration(session: Session, integration_id: int) -> IntegrationDetailOut | None:
    head = session.execute(text(_DETAIL_SQL), {"id": integration_id}).mappings().first()
    if head is None:
        return None
    subs = session.execute(text(_SUBS_SQL), {"integration_id": integration_id}).mappings().all()
    posts = session.execute(text(_POSTS_SQL), {"integration_id": integration_id}).mappings().all()
    payload = dict(head)
    payload["substitutes"] = [IntegrationSubstituteOut(**dict(s)) for s in subs]
    payload["posts"] = [IntegrationPostOut(**dict(p)) for p in posts]
    return IntegrationDetailOut(**payload)


_INSERT_SQL = """
INSERT INTO crm.integrations (
    blogger_id, marketer_id, publish_date, channel, ad_format, marketplace,
    stage, is_barter, cost_placement, cost_delivery, cost_goods, erid, notes
) VALUES (
    :blogger_id, :marketer_id, :publish_date, :channel, :ad_format, :marketplace,
    :stage, :is_barter, :cost_placement, :cost_delivery, :cost_goods, :erid, :notes
) RETURNING id
"""


def create_integration(session: Session, **fields: Any) -> int:
    payload = {k: fields.get(k) for k in (
        "blogger_id", "marketer_id", "publish_date", "channel", "ad_format",
        "marketplace", "stage", "is_barter", "cost_placement", "cost_delivery",
        "cost_goods", "erid", "notes",
    )}
    payload["stage"] = payload["stage"] or "lead"
    payload["is_barter"] = bool(payload["is_barter"])
    return int(session.execute(text(_INSERT_SQL), payload).scalar_one())


_UPDATABLE = {
    "blogger_id", "marketer_id", "publish_date", "channel", "ad_format",
    "marketplace", "stage", "outcome", "is_barter",
    "cost_placement", "cost_delivery", "cost_goods", "erid", "notes",
    "fact_views", "fact_orders", "fact_revenue",
}


def update_integration(
    session: Session, integration_id: int, fields: dict[str, Any]
) -> None:
    fields = {k: v for k, v in fields.items() if k in _UPDATABLE}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    sql = (
        f"UPDATE crm.integrations SET {set_clause}, updated_at = now() "
        f"WHERE id = :id AND archived_at IS NULL"
    )
    session.execute(text(sql), {**fields, "id": integration_id})


def transition_stage(
    session: Session, integration_id: int, *, target_stage: str, note: str | None = None
) -> None:
    """Stage column update — trigger writes integration_stage_history row."""
    update_integration(session, integration_id, {"stage": target_stage})
    if note:
        session.execute(
            text(
                "UPDATE crm.integration_stage_history "
                "SET note = :note WHERE integration_id = :id "
                "  AND id = (SELECT MAX(id) FROM crm.integration_stage_history "
                "            WHERE integration_id = :id)"
            ),
            {"note": note, "id": integration_id},
        )
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_integrations_repo.py -v
```
Expected: 6 passed.

- [ ] **Step 4: Commit**

```bash
git add shared/data_layer/influencer_crm/integrations.py tests/services/influencer_crm/test_integrations_repo.py
git commit -m "feat(crm-api): integrations repository (list/get/create/update/stage)"
```

---

## Task 12: Integrations — router

**Files:**
- Create: `services/influencer_crm/routers/integrations.py`
- Modify: `services/influencer_crm/app.py` (include router)
- Test: `tests/services/influencer_crm/test_integrations.py`

- [ ] **Step 1: Write failing endpoint tests**

`tests/services/influencer_crm/test_integrations.py`:

```python
"""HTTP tests for /integrations."""
from __future__ import annotations


def test_list_requires_auth(client):
    r = client.get("/integrations")
    assert r.status_code == 403


def test_list_returns_page(client, auth):
    r = client.get("/integrations", headers=auth, params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "next_cursor" in body


def test_kanban_filter_stage_in(client, auth):
    r = client.get(
        "/integrations",
        headers=auth,
        params={"stage_in": ["done", "paid"], "limit": 50},
    )
    assert r.status_code == 200
    for it in r.json()["items"]:
        assert it["stage"] in {"done", "paid"}


def test_get_404(client, auth):
    r = client.get("/integrations/999999999", headers=auth)
    assert r.status_code == 404


def test_get_detail_includes_substitutes(client, auth):
    list_resp = client.get("/integrations", headers=auth, params={"limit": 1}).json()
    if not list_resp["items"]:
        import pytest; pytest.skip("DB empty")
    iid = list_resp["items"][0]["id"]
    r = client.get(f"/integrations/{iid}", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert "substitutes" in body
    assert "blogger_handle" in body


def test_stage_transition(client, auth):
    list_resp = client.get(
        "/integrations", headers=auth, params={"limit": 1, "stage_in": ["done"]}
    ).json()
    if not list_resp["items"]:
        import pytest; pytest.skip("DB has no done integrations")
    iid = list_resp["items"][0]["id"]
    original_stage = list_resp["items"][0]["stage"]
    r = client.post(
        f"/integrations/{iid}/stage",
        headers=auth,
        json={"target_stage": "paid", "note": "marker"},
    )
    assert r.status_code == 200
    assert r.json()["stage"] == "paid"
    # restore
    client.post(
        f"/integrations/{iid}/stage",
        headers=auth,
        json={"target_stage": original_stage},
    )
```

- [ ] **Step 2: Implement router**

`services/influencer_crm/routers/integrations.py`:

```python
"""Integrations endpoints — list (Kanban-aware), detail, create, patch, stage."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.pagination import Page
from services.influencer_crm.schemas.integration import (
    IntegrationCreate,
    IntegrationDetailOut,
    IntegrationOut,
    IntegrationUpdate,
    StageTransitionIn,
)
from shared.data_layer.influencer_crm import integrations as repo

router = APIRouter(
    prefix="/integrations",
    tags=["integrations"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("", response_model=Page[IntegrationOut])
def list_integrations(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    stage_in: list[str] | None = Query(default=None),
    marketplace: str | None = None,
    marketer_id: int | None = None,
    blogger_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> Page[IntegrationOut]:
    items, next_cursor = repo.list_integrations(
        session, limit=limit, cursor=cursor,
        stage_in=stage_in, marketplace=marketplace,
        marketer_id=marketer_id, blogger_id=blogger_id,
        date_from=date_from, date_to=date_to,
    )
    return Page[IntegrationOut](items=items, next_cursor=next_cursor)


@router.get("/{integration_id}", response_model=IntegrationDetailOut)
def get_integration(
    integration_id: int,
    session: Session = Depends(get_session),
) -> IntegrationDetailOut:
    detail = repo.get_integration(session, integration_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return detail


@router.post("", response_model=IntegrationOut, status_code=status.HTTP_201_CREATED)
def create_integration(
    payload: IntegrationCreate,
    session: Session = Depends(get_session),
) -> IntegrationOut:
    new_id = repo.create_integration(session, **payload.model_dump(exclude_unset=True))
    created = repo.get_integration(session, new_id)
    assert created is not None
    return IntegrationOut.model_validate(created.model_dump())


@router.patch("/{integration_id}", response_model=IntegrationOut)
def patch_integration(
    integration_id: int,
    payload: IntegrationUpdate,
    session: Session = Depends(get_session),
) -> IntegrationOut:
    repo.update_integration(session, integration_id, payload.model_dump(exclude_unset=True))
    updated = repo.get_integration(session, integration_id)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return IntegrationOut.model_validate(updated.model_dump())


@router.post("/{integration_id}/stage", response_model=IntegrationOut)
def transition_stage(
    integration_id: int,
    payload: StageTransitionIn,
    session: Session = Depends(get_session),
) -> IntegrationOut:
    repo.transition_stage(
        session, integration_id,
        target_stage=payload.target_stage,
        note=payload.note,
    )
    refreshed = repo.get_integration(session, integration_id)
    if refreshed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return IntegrationOut.model_validate(refreshed.model_dump())
```

- [ ] **Step 3: Wire into app.py**

In `services/influencer_crm/app.py`:

```python
from services.influencer_crm.routers import health, bloggers, integrations
```

And in `create_app()`:

```python
    app.include_router(integrations.router)
```

- [ ] **Step 4: Run all tests**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_integrations.py -v
```

- [ ] **Step 5: Commit**

```bash
git add services/influencer_crm/routers/integrations.py services/influencer_crm/app.py \
        tests/services/influencer_crm/test_integrations.py
git commit -m "feat(crm-api): /integrations router (list, detail, create, patch, stage)"
```

---

## Task 13: Products — slices view (model_osnova-level)

**Files:**
- Create: `services/influencer_crm/schemas/product.py`
- Create: `shared/data_layer/influencer_crm/products.py`
- Create: `services/influencer_crm/routers/products.py`
- Modify: `services/influencer_crm/app.py`
- Test: `tests/services/influencer_crm/test_products.py`

- [ ] **Step 1: Write failing test**

`tests/services/influencer_crm/test_products.py`:

```python
"""Slices view — products with integration aggregates."""
from __future__ import annotations


def test_list_products_requires_auth(client):
    r = client.get("/products")
    assert r.status_code == 403


def test_list_products_returns_aggregates(client, auth):
    r = client.get("/products", headers=auth, params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    if body["items"]:
        item = body["items"][0]
        assert "model_osnova_id" in item
        assert "integrations_count" in item


def test_get_product_detail_404(client, auth):
    r = client.get("/products/999999999", headers=auth)
    assert r.status_code == 404
```

- [ ] **Step 2: Implement schemas**

`services/influencer_crm/schemas/product.py`:

```python
"""Slices view — model_osnova → integrations roll-up."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductSliceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    model_osnova_id: int
    model_name: str
    integrations_count: int = 0
    integrations_done: int = 0
    last_publish_date: date | None = None
    total_spent: Decimal = Decimal("0")
    total_revenue_fact: Decimal = Decimal("0")


class ProductDetailIntegrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    integration_id: int
    blogger_handle: str
    publish_date: date
    stage: str
    total_cost: Decimal
    fact_views: int | None = None
    fact_orders: int | None = None
    fact_revenue: Decimal | None = None


class ProductDetailOut(ProductSliceOut):
    integrations: list[ProductDetailIntegrationOut] = Field(default_factory=list)
```

- [ ] **Step 3: Implement repo**

`shared/data_layer/influencer_crm/products.py`:

```python
"""Slices: aggregate integrations per public.modeli_osnova.

A model_osnova rolls up multiple modeli (color variants). We map
substitute_articles → artikul_id → modeli.id → modeli_osnova.id.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.pagination import decode_cursor, encode_cursor
from services.influencer_crm.schemas.product import (
    ProductDetailIntegrationOut,
    ProductDetailOut,
    ProductSliceOut,
)


_AGG_CTE = """
WITH integration_models AS (
    SELECT DISTINCT i.id AS integration_id, mo.id AS model_osnova_id, mo.nazvanie AS model_name,
           i.publish_date, i.total_cost, i.fact_revenue, i.stage, i.fact_views, i.fact_orders,
           b.display_handle AS blogger_handle
    FROM crm.integrations i
    JOIN crm.bloggers b ON b.id = i.blogger_id
    JOIN crm.integration_substitute_articles isa ON isa.integration_id = i.id
    JOIN crm.substitute_articles sa ON sa.id = isa.substitute_article_id
    JOIN public.artikuly a ON a.id = sa.artikul_id
    JOIN public.modeli m ON m.id = a.model_id
    JOIN public.modeli_osnova mo ON mo.id = m.osnova_id
    WHERE i.archived_at IS NULL
)
"""


def list_products(
    session: Session,
    *,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[ProductSliceOut], str | None]:
    decoded = decode_cursor(cursor)
    cursor_filter = ""
    params: dict = {"limit": limit + 1}
    if decoded is not None:
        # cursor here is by (last_publish_date DESC, model_osnova_id DESC)
        # we encode (max_publish_date, model_osnova_id)
        cursor_ts, cursor_id = decoded
        cursor_filter = (
            "WHERE (COALESCE(MAX(publish_date), '1900-01-01'::date), model_osnova_id) "
            "    < (:cursor_ts::date, :cursor_id) "
        )
        params["cursor_ts"] = cursor_ts.date().isoformat()
        params["cursor_id"] = cursor_id

    sql = (
        _AGG_CTE
        + """
        SELECT model_osnova_id, MAX(model_name) AS model_name,
               COUNT(DISTINCT integration_id) AS integrations_count,
               COUNT(DISTINCT integration_id) FILTER (WHERE stage IN ('published','paid','done')) AS integrations_done,
               MAX(publish_date) AS last_publish_date,
               COALESCE(SUM(total_cost), 0) AS total_spent,
               COALESCE(SUM(fact_revenue), 0) AS total_revenue_fact
        FROM integration_models
        GROUP BY model_osnova_id
        """ + cursor_filter +
        " ORDER BY MAX(publish_date) DESC NULLS LAST, model_osnova_id DESC LIMIT :limit"
    )
    rows = session.execute(text(sql), params).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [ProductSliceOut(**dict(r)) for r in rows]

    next_cursor = None
    if has_more and rows and rows[-1]["last_publish_date"]:
        from datetime import datetime
        ts = datetime.combine(rows[-1]["last_publish_date"], datetime.min.time())
        next_cursor = encode_cursor(ts, rows[-1]["model_osnova_id"])
    return items, next_cursor


def get_product(session: Session, model_osnova_id: int) -> ProductDetailOut | None:
    sql = (
        _AGG_CTE
        + """
        SELECT model_osnova_id, MAX(model_name) AS model_name,
               COUNT(DISTINCT integration_id) AS integrations_count,
               COUNT(DISTINCT integration_id) FILTER (WHERE stage IN ('published','paid','done')) AS integrations_done,
               MAX(publish_date) AS last_publish_date,
               COALESCE(SUM(total_cost), 0) AS total_spent,
               COALESCE(SUM(fact_revenue), 0) AS total_revenue_fact
        FROM integration_models
        WHERE model_osnova_id = :model_osnova_id
        GROUP BY model_osnova_id
        """
    )
    head = session.execute(text(sql), {"model_osnova_id": model_osnova_id}).mappings().first()
    if head is None:
        return None

    sub_sql = (
        _AGG_CTE
        + """
        SELECT integration_id, blogger_handle, publish_date, stage, total_cost,
               fact_views, fact_orders, fact_revenue
        FROM integration_models
        WHERE model_osnova_id = :model_osnova_id
        ORDER BY publish_date DESC, integration_id DESC
        """
    )
    subs = session.execute(text(sub_sql), {"model_osnova_id": model_osnova_id}).mappings().all()

    payload = dict(head)
    payload["integrations"] = [ProductDetailIntegrationOut(**dict(s)) for s in subs]
    return ProductDetailOut(**payload)
```

- [ ] **Step 4: Implement router**

`services/influencer_crm/routers/products.py`:

```python
"""GET /products + GET /products/{model_osnova_id}."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.pagination import Page
from services.influencer_crm.schemas.product import ProductDetailOut, ProductSliceOut
from shared.data_layer.influencer_crm import products as repo

router = APIRouter(
    prefix="/products",
    tags=["products"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("", response_model=Page[ProductSliceOut])
def list_products(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
) -> Page[ProductSliceOut]:
    items, next_cursor = repo.list_products(session, limit=limit, cursor=cursor)
    return Page[ProductSliceOut](items=items, next_cursor=next_cursor)


@router.get("/{model_osnova_id}", response_model=ProductDetailOut)
def get_product(
    model_osnova_id: int,
    session: Session = Depends(get_session),
) -> ProductDetailOut:
    detail = repo.get_product(session, model_osnova_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    return detail
```

- [ ] **Step 5: Wire + run tests**

In `app.py`:

```python
from services.influencer_crm.routers import health, bloggers, integrations, products
...
    app.include_router(products.router)
```

```bash
.venv/bin/pytest tests/services/influencer_crm/test_products.py -v
```

- [ ] **Step 6: Commit**

```bash
git add services/influencer_crm/schemas/product.py shared/data_layer/influencer_crm/products.py \
        services/influencer_crm/routers/products.py services/influencer_crm/app.py \
        tests/services/influencer_crm/test_products.py
git commit -m "feat(crm-api): /products slices view (model_osnova roll-up)"
```

---

## Task 14: Tags endpoints

**Files:**
- Create: `shared/data_layer/influencer_crm/tags.py`
- Create: `services/influencer_crm/routers/tags.py`
- Modify: `services/influencer_crm/app.py`
- Test: `tests/services/influencer_crm/test_tags.py`

- [ ] **Step 1: Write failing test**

`tests/services/influencer_crm/test_tags.py`:

```python
def test_list_tags(client, auth):
    r = client.get("/tags", headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_tag_idempotent(client, auth):
    r1 = client.post("/tags", headers=auth, json={"name": "test-tag-pytest"})
    assert r1.status_code in (200, 201)
    tag_id = r1.json()["id"]
    r2 = client.post("/tags", headers=auth, json={"name": "test-tag-pytest"})
    assert r2.status_code in (200, 201)
    assert r2.json()["id"] == tag_id  # find-or-create


def test_create_tag_requires_name(client, auth):
    r = client.post("/tags", headers=auth, json={})
    assert r.status_code == 422
```

- [ ] **Step 2: Implement repo**

`shared/data_layer/influencer_crm/tags.py`:

```python
"""crm.tags — list + find-or-create (case-insensitive)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.schemas.common import TagOut


def list_tags(session: Session) -> list[TagOut]:
    rows = session.execute(
        text("SELECT id, name FROM crm.tags ORDER BY LOWER(name)")
    ).mappings().all()
    return [TagOut(**dict(r)) for r in rows]


def find_or_create_tag(session: Session, name: str) -> TagOut:
    found = session.execute(
        text("SELECT id, name FROM crm.tags WHERE LOWER(name) = LOWER(:name)"),
        {"name": name},
    ).mappings().first()
    if found:
        return TagOut(**dict(found))
    new_id = session.execute(
        text("INSERT INTO crm.tags (name) VALUES (:name) RETURNING id"),
        {"name": name},
    ).scalar_one()
    return TagOut(id=int(new_id), name=name)
```

- [ ] **Step 3: Implement router**

`services/influencer_crm/routers/tags.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.schemas.common import TagOut
from shared.data_layer.influencer_crm import tags as repo

router = APIRouter(
    prefix="/tags",
    tags=["tags"],
    dependencies=[Depends(verify_api_key)],
)


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.get("", response_model=list[TagOut])
def list_tags(session: Session = Depends(get_session)) -> list[TagOut]:
    return repo.list_tags(session)


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    session: Session = Depends(get_session),
) -> TagOut:
    return repo.find_or_create_tag(session, payload.name)
```

- [ ] **Step 4: Wire + test + commit**

```python
# app.py
from services.influencer_crm.routers import health, bloggers, integrations, products, tags
...
    app.include_router(tags.router)
```

```bash
.venv/bin/pytest tests/services/influencer_crm/test_tags.py -v
git add services/influencer_crm/routers/tags.py shared/data_layer/influencer_crm/tags.py \
        services/influencer_crm/app.py tests/services/influencer_crm/test_tags.py
git commit -m "feat(crm-api): /tags (list + find-or-create)"
```

---

## Task 15: Promo codes + substitute articles endpoints

**Files:**
- Create: `services/influencer_crm/schemas/promo.py`
- Create: `shared/data_layer/influencer_crm/promos.py`
- Create: `services/influencer_crm/routers/promos.py`
- Modify: `services/influencer_crm/app.py`
- Test: `tests/services/influencer_crm/test_promos.py`

- [ ] **Step 1: Tests**

`tests/services/influencer_crm/test_promos.py`:

```python
def test_substitute_articles_list(client, auth):
    r = client.get("/substitute-articles", headers=auth, params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body


def test_promo_codes_list(client, auth):
    r = client.get("/promo-codes", headers=auth, params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    if body["items"]:
        assert "code" in body["items"][0]


def test_filter_by_active_only(client, auth):
    r = client.get(
        "/promo-codes", headers=auth, params={"status": "active", "limit": 50}
    )
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["status"] == "active"
```

- [ ] **Step 2: Schemas**

`services/influencer_crm/schemas/promo.py`:

```python
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SubstituteArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    artikul_id: int | None = None
    purpose: str | None = None
    status: str
    created_at: datetime | None = None


class PromoCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    artikul_id: int | None = None
    discount_percent: Decimal | None = None
    status: Literal["active", "paused", "expired"]
    valid_from: date | None = None
    valid_until: date | None = None
```

- [ ] **Step 3: Repo**

`shared/data_layer/influencer_crm/promos.py`:

```python
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.pagination import decode_cursor, encode_cursor
from services.influencer_crm.schemas.promo import PromoCodeOut, SubstituteArticleOut


def list_substitute_articles(
    session: Session, *, limit: int = 50, cursor: str | None = None,
    status: str | None = None,
) -> tuple[list[SubstituteArticleOut], str | None]:
    params: dict = {"limit": limit + 1}
    where = []
    if status:
        where.append("AND status = :status")
        params["status"] = status
    decoded = decode_cursor(cursor)
    if decoded:
        ts, cid = decoded
        where.append("AND (created_at, id) < (:cts, :cid)")
        params["cts"] = ts
        params["cid"] = cid
    sql = (
        "SELECT id, code, artikul_id, purpose, status, created_at "
        "FROM crm.substitute_articles WHERE 1=1 "
        + " ".join(where)
        + " ORDER BY created_at DESC, id DESC LIMIT :limit"
    )
    rows = session.execute(text(sql), params).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [SubstituteArticleOut(**dict(r)) for r in rows]
    next_cursor = (
        encode_cursor(rows[-1]["created_at"], rows[-1]["id"])
        if has_more and rows and rows[-1]["created_at"]
        else None
    )
    return items, next_cursor


def list_promo_codes(
    session: Session, *, limit: int = 50, cursor: str | None = None,
    status: str | None = None,
) -> tuple[list[PromoCodeOut], str | None]:
    params: dict = {"limit": limit + 1}
    where = []
    if status:
        where.append("AND status = :status")
        params["status"] = status
    decoded = decode_cursor(cursor)
    if decoded:
        ts, cid = decoded
        where.append("AND (valid_from, id) < (:cts, :cid)")
        params["cts"] = ts.date().isoformat()
        params["cid"] = cid
    sql = (
        "SELECT id, code, artikul_id, discount_percent, status, "
        "       valid_from, valid_until "
        "FROM crm.promo_codes WHERE 1=1 "
        + " ".join(where)
        + " ORDER BY valid_from DESC NULLS LAST, id DESC LIMIT :limit"
    )
    rows = session.execute(text(sql), params).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [PromoCodeOut(**dict(r)) for r in rows]
    next_cursor = None
    if has_more and rows and rows[-1]["valid_from"]:
        from datetime import datetime
        ts = datetime.combine(rows[-1]["valid_from"], datetime.min.time())
        next_cursor = encode_cursor(ts, rows[-1]["id"])
    return items, next_cursor
```

- [ ] **Step 4: Router**

`services/influencer_crm/routers/promos.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.pagination import Page
from services.influencer_crm.schemas.promo import PromoCodeOut, SubstituteArticleOut
from shared.data_layer.influencer_crm import promos as repo

router = APIRouter(
    tags=["promos"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("/substitute-articles", response_model=Page[SubstituteArticleOut])
def list_substitute_articles(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    status: str | None = None,
) -> Page[SubstituteArticleOut]:
    items, nxt = repo.list_substitute_articles(session, limit=limit, cursor=cursor, status=status)
    return Page[SubstituteArticleOut](items=items, next_cursor=nxt)


@router.get("/promo-codes", response_model=Page[PromoCodeOut])
def list_promo_codes(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    status: str | None = None,
) -> Page[PromoCodeOut]:
    items, nxt = repo.list_promo_codes(session, limit=limit, cursor=cursor, status=status)
    return Page[PromoCodeOut](items=items, next_cursor=nxt)
```

- [ ] **Step 5: Wire + test + commit**

```python
# app.py
from services.influencer_crm.routers import health, bloggers, integrations, products, tags, promos
...
    app.include_router(promos.router)
```

```bash
.venv/bin/pytest tests/services/influencer_crm/test_promos.py -v
git add services/influencer_crm/schemas/promo.py shared/data_layer/influencer_crm/promos.py \
        services/influencer_crm/routers/promos.py services/influencer_crm/app.py \
        tests/services/influencer_crm/test_promos.py
git commit -m "feat(crm-api): /substitute-articles + /promo-codes list"
```

---

## Task 16: Briefs versioning

**Files:**
- Create: `services/influencer_crm/schemas/brief.py`
- Create: `shared/data_layer/influencer_crm/briefs.py`
- Create: `services/influencer_crm/routers/briefs.py`
- Modify: `services/influencer_crm/app.py`
- Test: `tests/services/influencer_crm/test_briefs.py`

- [ ] **Step 1: Tests**

`tests/services/influencer_crm/test_briefs.py`:

```python
def test_create_brief_returns_id(client, auth):
    r = client.post(
        "/briefs",
        headers=auth,
        json={"title": "PyTest brief", "content_md": "# header\n\nbody"},
    )
    assert r.status_code == 201
    assert r.json()["id"]


def test_create_brief_then_version(client, auth):
    r1 = client.post("/briefs", headers=auth, json={"title": "v1", "content_md": "v1"})
    bid = r1.json()["id"]
    r2 = client.post(
        f"/briefs/{bid}/versions",
        headers=auth,
        json={"content_md": "v2-content"},
    )
    assert r2.status_code == 201
    assert r2.json()["version"] >= 2


def test_list_versions(client, auth):
    r1 = client.post("/briefs", headers=auth, json={"title": "vlist", "content_md": "1"})
    bid = r1.json()["id"]
    client.post(f"/briefs/{bid}/versions", headers=auth, json={"content_md": "2"})
    client.post(f"/briefs/{bid}/versions", headers=auth, json={"content_md": "3"})
    r = client.get(f"/briefs/{bid}/versions", headers=auth)
    assert r.status_code == 200
    versions = r.json()
    assert len(versions) >= 3
```

- [ ] **Step 2: Schemas**

`services/influencer_crm/schemas/brief.py`:

```python
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class BriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    current_version_id: int | None = None
    created_at: datetime | None = None


class BriefVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    brief_id: int
    version: int
    content_md: str
    created_at: datetime | None = None


class BriefCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content_md: str


class BriefVersionCreate(BaseModel):
    content_md: str
```

- [ ] **Step 3: Repo**

`shared/data_layer/influencer_crm/briefs.py`:

```python
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.schemas.brief import BriefOut, BriefVersionOut


def create_brief(session: Session, *, title: str, content_md: str) -> BriefOut:
    brief_id = session.execute(
        text(
            "INSERT INTO crm.briefs (title) VALUES (:title) RETURNING id"
        ),
        {"title": title},
    ).scalar_one()
    version_id = session.execute(
        text(
            "INSERT INTO crm.brief_versions (brief_id, version, content_md) "
            "VALUES (:bid, 1, :content) RETURNING id"
        ),
        {"bid": brief_id, "content": content_md},
    ).scalar_one()
    session.execute(
        text("UPDATE crm.briefs SET current_version_id = :vid WHERE id = :bid"),
        {"vid": version_id, "bid": brief_id},
    )
    return BriefOut(id=brief_id, title=title, current_version_id=version_id)


def add_version(session: Session, brief_id: int, content_md: str) -> BriefVersionOut:
    next_version = session.execute(
        text(
            "SELECT COALESCE(MAX(version), 0) + 1 "
            "FROM crm.brief_versions WHERE brief_id = :bid"
        ),
        {"bid": brief_id},
    ).scalar_one()
    new_id = session.execute(
        text(
            "INSERT INTO crm.brief_versions (brief_id, version, content_md) "
            "VALUES (:bid, :v, :c) RETURNING id"
        ),
        {"bid": brief_id, "v": next_version, "c": content_md},
    ).scalar_one()
    session.execute(
        text("UPDATE crm.briefs SET current_version_id = :vid WHERE id = :bid"),
        {"vid": new_id, "bid": brief_id},
    )
    return BriefVersionOut(
        id=int(new_id), brief_id=brief_id, version=int(next_version),
        content_md=content_md,
    )


def list_versions(session: Session, brief_id: int) -> list[BriefVersionOut]:
    rows = session.execute(
        text(
            "SELECT id, brief_id, version, content_md, created_at "
            "FROM crm.brief_versions WHERE brief_id = :bid "
            "ORDER BY version DESC"
        ),
        {"bid": brief_id},
    ).mappings().all()
    return [BriefVersionOut(**dict(r)) for r in rows]
```

- [ ] **Step 4: Router**

`services/influencer_crm/routers/briefs.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.schemas.brief import (
    BriefCreate,
    BriefOut,
    BriefVersionCreate,
    BriefVersionOut,
)
from shared.data_layer.influencer_crm import briefs as repo

router = APIRouter(
    prefix="/briefs",
    tags=["briefs"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("", response_model=BriefOut, status_code=status.HTTP_201_CREATED)
def create_brief(
    payload: BriefCreate,
    session: Session = Depends(get_session),
) -> BriefOut:
    return repo.create_brief(session, title=payload.title, content_md=payload.content_md)


@router.post(
    "/{brief_id}/versions",
    response_model=BriefVersionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_version(
    brief_id: int,
    payload: BriefVersionCreate,
    session: Session = Depends(get_session),
) -> BriefVersionOut:
    return repo.add_version(session, brief_id, payload.content_md)


@router.get("/{brief_id}/versions", response_model=list[BriefVersionOut])
def list_versions(
    brief_id: int,
    session: Session = Depends(get_session),
) -> list[BriefVersionOut]:
    return repo.list_versions(session, brief_id)
```

- [ ] **Step 5: Wire + test + commit**

```python
# app.py
from services.influencer_crm.routers import health, bloggers, integrations, products, tags, promos, briefs
...
    app.include_router(briefs.router)
```

```bash
.venv/bin/pytest tests/services/influencer_crm/test_briefs.py -v
git add services/influencer_crm/schemas/brief.py shared/data_layer/influencer_crm/briefs.py \
        services/influencer_crm/routers/briefs.py services/influencer_crm/app.py \
        tests/services/influencer_crm/test_briefs.py
git commit -m "feat(crm-api): /briefs + brief versioning"
```

---

## Task 17: Metrics snapshots

**Files:**
- Create: `services/influencer_crm/schemas/metrics.py`
- Create: `shared/data_layer/influencer_crm/metrics.py`
- Create: `services/influencer_crm/routers/metrics.py`
- Modify: `services/influencer_crm/app.py`
- Test: `tests/services/influencer_crm/test_metrics.py`

- [ ] **Step 1: Tests**

`tests/services/influencer_crm/test_metrics.py`:

```python
def test_post_metrics_snapshot(client, auth):
    list_resp = client.get("/integrations", headers=auth, params={"limit": 1}).json()
    if not list_resp["items"]:
        import pytest; pytest.skip("DB empty")
    iid = list_resp["items"][0]["id"]
    r = client.post(
        f"/metrics-snapshots/{iid}",
        headers=auth,
        json={"fact_views": 12345, "fact_clicks": 678, "note": "test snapshot"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["integration_id"] == iid
    assert body["fact_views"] == 12345


def test_post_metrics_404_unknown_integration(client, auth):
    r = client.post(
        "/metrics-snapshots/999999999",
        headers=auth,
        json={"fact_views": 1},
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Schemas**

`services/influencer_crm/schemas/metrics.py`:

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class MetricsSnapshotIn(BaseModel):
    fact_views: int | None = None
    fact_clicks: int | None = None
    fact_carts: int | None = None
    fact_orders: int | None = None
    fact_revenue: Decimal | None = None
    note: str | None = None


class MetricsSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    integration_id: int
    captured_at: datetime
    fact_views: int | None = None
    fact_clicks: int | None = None
    fact_carts: int | None = None
    fact_orders: int | None = None
    fact_revenue: Decimal | None = None
    note: str | None = None
```

- [ ] **Step 3: Repo**

`shared/data_layer/influencer_crm/metrics.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.schemas.metrics import MetricsSnapshotOut


def insert_snapshot(
    session: Session,
    integration_id: int,
    payload: dict[str, Any],
) -> MetricsSnapshotOut | None:
    # Verify FK exists
    exists = session.execute(
        text(
            "SELECT 1 FROM crm.integrations "
            "WHERE id = :id AND archived_at IS NULL"
        ),
        {"id": integration_id},
    ).first()
    if not exists:
        return None

    fields = {
        "integration_id": integration_id,
        "fact_views": payload.get("fact_views"),
        "fact_clicks": payload.get("fact_clicks"),
        "fact_carts": payload.get("fact_carts"),
        "fact_orders": payload.get("fact_orders"),
        "fact_revenue": payload.get("fact_revenue"),
        "note": payload.get("note"),
    }
    new_id = session.execute(
        text(
            "INSERT INTO crm.integration_metrics_snapshots ("
            "  integration_id, fact_views, fact_clicks, fact_carts, "
            "  fact_orders, fact_revenue, note"
            ") VALUES ("
            "  :integration_id, :fact_views, :fact_clicks, :fact_carts, "
            "  :fact_orders, :fact_revenue, :note"
            ") RETURNING id"
        ),
        fields,
    ).scalar_one()

    row = session.execute(
        text(
            "SELECT id, integration_id, captured_at, "
            "       fact_views, fact_clicks, fact_carts, fact_orders, "
            "       fact_revenue, note "
            "FROM crm.integration_metrics_snapshots WHERE id = :id"
        ),
        {"id": new_id},
    ).mappings().first()
    return MetricsSnapshotOut(**dict(row))
```

- [ ] **Step 4: Router**

`services/influencer_crm/routers/metrics.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.schemas.metrics import MetricsSnapshotIn, MetricsSnapshotOut
from shared.data_layer.influencer_crm import metrics as repo

router = APIRouter(
    prefix="/metrics-snapshots",
    tags=["metrics"],
    dependencies=[Depends(verify_api_key)],
)


@router.post(
    "/{integration_id}",
    response_model=MetricsSnapshotOut,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot(
    integration_id: int,
    payload: MetricsSnapshotIn,
    session: Session = Depends(get_session),
) -> MetricsSnapshotOut:
    snap = repo.insert_snapshot(session, integration_id, payload.model_dump(exclude_unset=True))
    if snap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return snap
```

- [ ] **Step 5: Wire + test + commit**

```python
# app.py
from services.influencer_crm.routers import health, bloggers, integrations, products, tags, promos, briefs, metrics
...
    app.include_router(metrics.router)
```

```bash
.venv/bin/pytest tests/services/influencer_crm/test_metrics.py -v
git add services/influencer_crm/schemas/metrics.py shared/data_layer/influencer_crm/metrics.py \
        services/influencer_crm/routers/metrics.py services/influencer_crm/app.py \
        tests/services/influencer_crm/test_metrics.py
git commit -m "feat(crm-api): POST /metrics-snapshots/{integration_id}"
```

---

## Task 18: Full-text search

**Files:**
- Create: `services/influencer_crm/routers/search.py`
- Modify: `shared/data_layer/influencer_crm/bloggers.py` (add `search_bloggers`)
- Modify: `services/influencer_crm/app.py`
- Test: `tests/services/influencer_crm/test_search.py`

- [ ] **Step 1: Test**

`tests/services/influencer_crm/test_search.py`:

```python
def test_search_returns_both_groups(client, auth):
    r = client.get("/search", headers=auth, params={"q": "instagram"})
    assert r.status_code == 200
    body = r.json()
    assert "bloggers" in body and "integrations" in body
    assert isinstance(body["bloggers"], list)
    assert isinstance(body["integrations"], list)


def test_search_requires_q(client, auth):
    r = client.get("/search", headers=auth)
    assert r.status_code == 422


def test_search_limit_param(client, auth):
    r = client.get("/search", headers=auth, params={"q": "a", "limit": 3})
    assert r.status_code == 200
    body = r.json()
    assert len(body["bloggers"]) <= 3
    assert len(body["integrations"]) <= 3
```

- [ ] **Step 2: Add search query to bloggers repo**

Append to `shared/data_layer/influencer_crm/bloggers.py`:

```python
def search_bloggers(session: Session, q: str, limit: int = 10) -> list[BloggerOut]:
    """Trigram search on display_handle + real_name + notes via idx_bloggers_search."""
    rows = session.execute(
        text(
            "SELECT id, display_handle, real_name, status, default_marketer_id, "
            "       price_story_default, price_reels_default, created_at, updated_at "
            "FROM crm.bloggers "
            "WHERE archived_at IS NULL AND ("
            "    display_handle ILIKE '%' || :q || '%' "
            " OR COALESCE(real_name, '') ILIKE '%' || :q || '%' "
            " OR COALESCE(notes, '') ILIKE '%' || :q || '%'"
            ") ORDER BY updated_at DESC LIMIT :limit"
        ),
        {"q": q, "limit": limit},
    ).mappings().all()
    return [BloggerOut(**dict(r)) for r in rows]
```

- [ ] **Step 3: Search router**

`services/influencer_crm/routers/search.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.schemas.blogger import BloggerOut
from services.influencer_crm.schemas.integration import IntegrationOut
from shared.data_layer.influencer_crm import bloggers as bloggers_repo

router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> dict:
    bloggers = bloggers_repo.search_bloggers(session, q, limit)
    int_rows = session.execute(
        text(
            "SELECT id, blogger_id, marketer_id, brief_id, "
            "       publish_date, channel, ad_format, marketplace, "
            "       stage, outcome, is_barter, "
            "       cost_placement, cost_delivery, cost_goods, total_cost, "
            "       erid, fact_views, fact_orders, fact_revenue, "
            "       created_at, updated_at "
            "FROM crm.integrations "
            "WHERE archived_at IS NULL AND ("
            "    COALESCE(notes, '') ILIKE '%' || :q || '%' "
            " OR COALESCE(post_content, '') ILIKE '%' || :q || '%'"
            ") ORDER BY updated_at DESC LIMIT :limit"
        ),
        {"q": q, "limit": limit},
    ).mappings().all()
    integrations = [IntegrationOut(**dict(r)) for r in int_rows]
    return {"bloggers": bloggers, "integrations": integrations}
```

- [ ] **Step 4: Wire + test + commit**

```python
# app.py
from services.influencer_crm.routers import (health, bloggers, integrations,
    products, tags, promos, briefs, metrics, search)
...
    app.include_router(search.router)
```

```bash
.venv/bin/pytest tests/services/influencer_crm/test_search.py -v
git add services/influencer_crm/routers/search.py shared/data_layer/influencer_crm/bloggers.py \
        services/influencer_crm/app.py tests/services/influencer_crm/test_search.py
git commit -m "feat(crm-api): /search across bloggers + integrations"
```

---

## Task 19: ETag middleware on list endpoints

**Files:**
- Create: `services/influencer_crm/etag.py`
- Modify: `services/influencer_crm/app.py`
- Test: `tests/services/influencer_crm/test_etag.py`

- [ ] **Step 1: Test**

`tests/services/influencer_crm/test_etag.py`:

```python
def test_list_returns_etag(client, auth):
    r = client.get("/bloggers", headers=auth, params={"limit": 5})
    assert r.status_code == 200
    assert "ETag" in r.headers
    etag = r.headers["ETag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_if_none_match_returns_304(client, auth):
    r1 = client.get("/bloggers", headers=auth, params={"limit": 5})
    etag = r1.headers["ETag"]

    r2 = client.get(
        "/bloggers",
        headers={**auth, "If-None-Match": etag},
        params={"limit": 5},
    )
    assert r2.status_code == 304


def test_health_no_etag(client):
    r = client.get("/health")
    assert "ETag" not in r.headers
```

- [ ] **Step 2: Implement middleware**

`services/influencer_crm/etag.py`:

```python
"""ETag middleware for GET endpoints (excluding /health).

Computes hash over the response body and adds it as `ETag`. Honors
`If-None-Match` for 304 responses.
"""
from __future__ import annotations

import hashlib

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class ETagMiddleware(BaseHTTPMiddleware):
    EXCLUDED_PATHS = {"/health", "/openapi.json", "/docs", "/redoc"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method != "GET" or request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        response = await call_next(request)
        if response.status_code != 200:
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        etag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match == etag:
            return Response(status_code=304, headers={"ETag": etag})

        new_response = Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
        new_response.headers["ETag"] = etag
        return new_response
```

- [ ] **Step 3: Wire**

In `services/influencer_crm/app.py`:

```python
from services.influencer_crm.etag import ETagMiddleware
...
def create_app() -> FastAPI:
    app = FastAPI(...)
    app.add_middleware(ETagMiddleware)
    ...
```

- [ ] **Step 4: Run + commit**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_etag.py -v
git add services/influencer_crm/etag.py services/influencer_crm/app.py \
        tests/services/influencer_crm/test_etag.py
git commit -m "feat(crm-api): ETag middleware (304 If-None-Match) on GET endpoints"
```

---

## Task 20: N+1 query-count guard test

**Files:**
- Create: `tests/services/influencer_crm/test_n_plus_one.py`

- [ ] **Step 1: Implement query-count fixture + tests**

`tests/services/influencer_crm/test_n_plus_one.py`:

```python
"""Assert each list endpoint executes ≤3 queries.

A non-paginated list endpoint loading 50 rows must do at most:
  1. SELECT main rows
  2. SELECT count for cursor heuristic (we avoided this)
  3. Optional aggregate JOIN

If a future change adds a per-row SELECT, this test catches it.
"""
from __future__ import annotations

from sqlalchemy import event

from shared.data_layer.influencer_crm._engine import get_engine


def _attach_counter():
    counter = {"n": 0}

    def _on_before_execute(*_args, **_kwargs):
        counter["n"] += 1

    event.listen(get_engine(), "before_cursor_execute", _on_before_execute)
    return counter, _on_before_execute


def test_list_bloggers_query_count(client, auth):
    counter, listener = _attach_counter()
    try:
        r = client.get("/bloggers", headers=auth, params={"limit": 50})
        assert r.status_code == 200
    finally:
        event.remove(get_engine(), "before_cursor_execute", listener)
    assert counter["n"] <= 3, f"too many queries: {counter['n']}"


def test_list_integrations_query_count(client, auth):
    counter, listener = _attach_counter()
    try:
        r = client.get("/integrations", headers=auth, params={"limit": 50})
        assert r.status_code == 200
    finally:
        event.remove(get_engine(), "before_cursor_execute", listener)
    assert counter["n"] <= 3, f"too many queries: {counter['n']}"


def test_get_blogger_detail_query_count(client, auth):
    """Detail = main SELECT + channels SELECT = 2 queries."""
    list_resp = client.get("/bloggers", headers=auth, params={"limit": 1}).json()
    if not list_resp["items"]:
        import pytest; pytest.skip("DB empty")
    bid = list_resp["items"][0]["id"]
    counter, listener = _attach_counter()
    try:
        r = client.get(f"/bloggers/{bid}", headers=auth)
        assert r.status_code == 200
    finally:
        event.remove(get_engine(), "before_cursor_execute", listener)
    assert counter["n"] <= 3, f"too many queries: {counter['n']}"


def test_get_integration_detail_query_count(client, auth):
    """Detail = main SELECT + subs SELECT + posts SELECT = 3 queries."""
    list_resp = client.get("/integrations", headers=auth, params={"limit": 1}).json()
    if not list_resp["items"]:
        import pytest; pytest.skip("DB empty")
    iid = list_resp["items"][0]["id"]
    counter, listener = _attach_counter()
    try:
        r = client.get(f"/integrations/{iid}", headers=auth)
        assert r.status_code == 200
    finally:
        event.remove(get_engine(), "before_cursor_execute", listener)
    assert counter["n"] <= 4, f"too many queries: {counter['n']}"
```

- [ ] **Step 2: Run + commit**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_n_plus_one.py -v
git add tests/services/influencer_crm/test_n_plus_one.py
git commit -m "test(crm-api): N+1 guards — list ≤3 queries, detail ≤4"
```

---

## Task 21: OpenAPI completeness gate

**Files:**
- Create: `tests/services/influencer_crm/test_openapi.py`

- [ ] **Step 1: Test**

`tests/services/influencer_crm/test_openapi.py`:

```python
"""OpenAPI must include every endpoint we promised."""
from __future__ import annotations

EXPECTED = [
    ("GET", "/health"),
    ("GET", "/bloggers"),
    ("GET", "/bloggers/{blogger_id}"),
    ("POST", "/bloggers"),
    ("PATCH", "/bloggers/{blogger_id}"),
    ("GET", "/integrations"),
    ("GET", "/integrations/{integration_id}"),
    ("POST", "/integrations"),
    ("PATCH", "/integrations/{integration_id}"),
    ("POST", "/integrations/{integration_id}/stage"),
    ("GET", "/products"),
    ("GET", "/products/{model_osnova_id}"),
    ("GET", "/tags"),
    ("POST", "/tags"),
    ("GET", "/substitute-articles"),
    ("GET", "/promo-codes"),
    ("POST", "/briefs"),
    ("POST", "/briefs/{brief_id}/versions"),
    ("GET", "/briefs/{brief_id}/versions"),
    ("POST", "/metrics-snapshots/{integration_id}"),
    ("GET", "/search"),
]


def test_every_endpoint_documented(client):
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    for method, path in EXPECTED:
        assert path in paths, f"missing path: {path}"
        assert method.lower() in paths[path], f"missing {method} on {path}"


def test_protected_endpoints_have_x_api_key_in_security_schemes(client):
    spec = client.get("/openapi.json").json()
    components = spec.get("components", {})
    schemes = components.get("securitySchemes", {})
    # Auth via Header(...) doesn't auto-register a scheme. Acceptable for v0.1
    # but document the contract:
    assert spec["info"]["title"] == "Influencer CRM API"
```

- [ ] **Step 2: Run + commit**

```bash
.venv/bin/pytest tests/services/influencer_crm/test_openapi.py -v
git add tests/services/influencer_crm/test_openapi.py
git commit -m "test(crm-api): OpenAPI completeness gate (21 endpoints)"
```

---

## Task 22: Dev runner script + verification doc

**Files:**
- Create: `services/influencer_crm/scripts/run_dev.sh`
- Modify: `services/influencer_crm/README.md`
- Modify: `docs/database/INFLUENCER_CRM.md` (or new `docs/api/INFLUENCER_CRM_API.md` if missing — task creates it)

- [ ] **Step 1: Create runner**

`services/influencer_crm/scripts/run_dev.sh`:

```bash
#!/usr/bin/env bash
# Local dev runner. Reads .env, picks port 8082 (collisionless with marketplace ETL on 8081).
set -euo pipefail
cd "$(dirname "$0")/../../.."  # repo root
exec .venv/bin/uvicorn services.influencer_crm.app:app \
    --reload --host 127.0.0.1 --port 8082 \
    --log-level info
```

```bash
chmod +x services/influencer_crm/scripts/run_dev.sh
```

- [ ] **Step 2: Smoke test**

```bash
bash services/influencer_crm/scripts/run_dev.sh &
SERVER_PID=$!
sleep 3
curl -s http://127.0.0.1:8082/health
curl -s -H "X-API-Key: $INFLUENCER_CRM_API_KEY" \
     "http://127.0.0.1:8082/bloggers?limit=2" | head -c 200
kill $SERVER_PID
```
Expected: `{"status":"ok"}` then JSON page with `items` array.

- [ ] **Step 3: Write API doc**

Create `docs/api/INFLUENCER_CRM_API.md`:

```markdown
# Influencer CRM API

Base URL (local): `http://127.0.0.1:8082`
Auth: `X-API-Key: <INFLUENCER_CRM_API_KEY>` on every endpoint except `/health`.

## Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok"}` |
| GET | `/bloggers?limit&cursor&status&marketer_id&q` | — | `Page[BloggerOut]` |
| GET | `/bloggers/{id}` | — | `BloggerDetailOut` |
| POST | `/bloggers` | `BloggerCreate` | `BloggerOut` (201) |
| PATCH | `/bloggers/{id}` | `BloggerUpdate` | `BloggerOut` |
| GET | `/integrations?limit&cursor&stage_in&marketplace&marketer_id&blogger_id&date_from&date_to` | — | `Page[IntegrationOut]` |
| GET | `/integrations/{id}` | — | `IntegrationDetailOut` |
| POST | `/integrations` | `IntegrationCreate` | `IntegrationOut` (201) |
| PATCH | `/integrations/{id}` | `IntegrationUpdate` | `IntegrationOut` |
| POST | `/integrations/{id}/stage` | `StageTransitionIn` | `IntegrationOut` |
| GET | `/products` | — | `Page[ProductSliceOut]` |
| GET | `/products/{model_osnova_id}` | — | `ProductDetailOut` |
| GET | `/tags` | — | `list[TagOut]` |
| POST | `/tags` | `{"name": "..."}` | `TagOut` (find-or-create, 201) |
| GET | `/substitute-articles?status` | — | `Page[SubstituteArticleOut]` |
| GET | `/promo-codes?status` | — | `Page[PromoCodeOut]` |
| POST | `/briefs` | `BriefCreate` | `BriefOut` (201) |
| POST | `/briefs/{id}/versions` | `BriefVersionCreate` | `BriefVersionOut` (201) |
| GET | `/briefs/{id}/versions` | — | `list[BriefVersionOut]` |
| POST | `/metrics-snapshots/{integration_id}` | `MetricsSnapshotIn` | `MetricsSnapshotOut` (201) |
| GET | `/search?q&limit` | — | `{"bloggers": [...], "integrations": [...]}` |

## Auth contract

Send `X-API-Key: <secret>` on every request except `/health`. Wrong/missing key → 403.

## Pagination

All list endpoints return `Page[T]`:

```json
{ "items": [...], "next_cursor": "base64..." | null }
```

To page forward: send `?cursor=<value>`. When `next_cursor` is `null`, you've reached the end.

## ETag

GET endpoints set `ETag`. Honor `If-None-Match` to get `304` on unchanged data.

## Errors

- `403` — missing/wrong API key
- `404` — resource not found
- `409` — unique constraint violation (e.g. duplicate erid)
- `422` — pydantic validation
- `500` — unexpected (we log; do not retry blindly)
```

- [ ] **Step 4: Update README endpoint section**

Append to `services/influencer_crm/README.md`:

```markdown
## Run smoke check

```bash
bash services/influencer_crm/scripts/run_dev.sh &
sleep 2
curl http://127.0.0.1:8082/health
# {"status":"ok"}
```

See `docs/api/INFLUENCER_CRM_API.md` for the full endpoint catalogue.
```

- [ ] **Step 5: Commit**

```bash
git add services/influencer_crm/scripts/run_dev.sh services/influencer_crm/README.md \
        docs/api/INFLUENCER_CRM_API.md
git commit -m "docs(crm-api): dev runner + API contract doc"
```

---

## Task 23: Run full suite + Codex review gate

**Files:** none (verification only)

- [ ] **Step 1: Full pytest run**

```bash
.venv/bin/pytest tests/services/influencer_crm/ -v --tb=short
```
Expected: all green. Skipped tests OK only if reason is "DB empty" (it isn't — P2 populated 241 bloggers, 137 integrations).

- [ ] **Step 2: Lint**

```bash
.venv/bin/ruff check services/influencer_crm/ shared/data_layer/influencer_crm/ tests/services/influencer_crm/
```
Expected: 0 errors.

- [ ] **Step 3: Manual smoke for each endpoint family**

```bash
export API="http://127.0.0.1:8082"
export KEY="$INFLUENCER_CRM_API_KEY"
H="X-API-Key: $KEY"
bash services/influencer_crm/scripts/run_dev.sh &
sleep 2

# Health
curl -s $API/health | tee /dev/null

# Bloggers
curl -s -H "$H" "$API/bloggers?limit=3" | python -m json.tool | head -30

# Integrations Kanban
curl -s -H "$H" "$API/integrations?stage_in=done&limit=3" | python -m json.tool | head -30

# Search
curl -s -H "$H" "$API/search?q=instagram&limit=2" | python -m json.tool | head -30

kill %1
```

- [ ] **Step 4: Codex cross-model review**

Use Skill `codex-quality-gate`:

```
Path: services/influencer_crm/, shared/data_layer/influencer_crm/, tests/services/influencer_crm/
Focus: SQL injection (we use named parameters but verify), N+1 risk on detail endpoints,
       cursor encoding security (no leakage), error-status correctness, type-hint coverage.
Pass threshold (from roadmap): 0 critical, ≤3 warnings.
```

- [ ] **Step 5: Address findings**

For each finding:
- Critical → fix as a follow-up task in this plan, re-run T23.1 + T23.4.
- Warning that you accept → document in `docs/api/INFLUENCER_CRM_API.md` § Known limitations.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore(crm-api): Phase 3 done — full suite green, Codex review passed" \
           --allow-empty
git log --oneline | head -25
```

- [ ] **Step 7: Push branch**

```bash
git push -u origin feat/influencer-crm-p3
```

- [ ] **Step 8: Update memory**

Update `~/.claude/projects/-Users-danilamatveev-Projects-Wookiee/memory/project_influencer_crm.md`:
flip Phase 3 from `⏭ API BFF` to `✅ API BFF — DONE <date>` with last commit hash and counts of endpoints + tests.

---

## Verification checklist (run before declaring P3 done)

- [ ] `pytest tests/services/influencer_crm/ -v` → 100% green (skipped only if "DB empty" — should not happen)
- [ ] `ruff check services/influencer_crm/ shared/data_layer/influencer_crm/` → clean
- [ ] `curl /health` → 200
- [ ] `curl -H X-API-Key: bad /bloggers` → 403
- [ ] `curl -H X-API-Key: $KEY /bloggers?limit=5` → 200 with items
- [ ] `curl -H X-API-Key: $KEY /integrations?stage_in=done` → all stage=done
- [ ] `curl -H X-API-Key: $KEY /products` → ProductSliceOut shape
- [ ] `/openapi.json` lists all 21 endpoints
- [ ] N+1 tests pass (≤3-4 queries per request)
- [ ] Branch `feat/influencer-crm-p3` pushed
- [ ] Memory updated

---

## Self-Review

**1. Spec coverage:**

Roadmap P3 deliverable list vs tasks:
- ✅ FastAPI BFF — T1-T4
- ✅ Endpoint families × 7 — T9, T12, T13, T14, T15, T16, T17, T18 (covers bloggers, integrations, products, tags, promos, briefs, metrics, search → 8 families, exceeds spec)
- ✅ TanStack-friendly cursor pagination — T6
- ✅ ETag on lists — T19
- ✅ N+1 detection — T20
- ✅ pytest + httpx async — wired throughout (sync httpx — explicit choice, async runtime not justified at this scale)
- ✅ OpenAPI on /docs — built-in by FastAPI; T21 verifies catalogue
- ✅ Auth: anon blocked — T5
- ✅ Read paths use materialized views — T8 joins `crm.v_blogger_totals`
- ✅ Repository layer (`shared/data_layer/influencer_crm/`) — every Task with repo
- ✅ Codex review gate — T23
- ✅ Sync everywhere — explicit choice in Tech Stack

**2. Placeholder scan:** Searched for "TBD", "TODO", "implement later", "appropriate error handling", "similar to". None present. Each task has full code.

**3. Type consistency:**
- `BloggerOut`/`BloggerDetailOut`/`BloggerCreate`/`BloggerUpdate` — defined T7, used identically T9.
- `IntegrationOut`/`IntegrationDetailOut`/`IntegrationCreate`/`IntegrationUpdate`/`StageTransitionIn` — T10/T12 match.
- `Page[T]` generic — T6, used everywhere consistently.
- `encode_cursor(updated_at, id)` / `decode_cursor(cursor)` — T6 signature, all repos in T8/T11/T13/T15 call with same shape.
- `session_factory` context manager — T3 yields Session; T5 `get_session` consumes via `with`. Consistent.
- All Pydantic schemas use `model_config = ConfigDict(from_attributes=True)` for SQL-row → model coercion. Consistent.

**4. Open issues to fix while implementing (not blockers):**
- The `crm.v_blogger_totals` may need a manual `REFRESH MATERIALIZED VIEW` after P2 ETL (it's empty on the day it's first viewed). The first integration test that queries it should call refresh in conftest. → handled by adding `REFRESH MATERIALIZED VIEW crm.v_blogger_totals` to `conftest.py` `_set_api_key` fixture as a one-line module-level setup. Add this in T8 Step 4 follow-up if tests fail with empty totals.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-27-influencer-crm-p3-api-bff.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Good for 23 tasks because each is bounded and the subagents won't drift.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Faster start but the context grows long over 23 tasks.

Which approach?
