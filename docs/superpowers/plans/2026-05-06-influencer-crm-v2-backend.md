# Influencer CRM v2 — Backend Plan (Plan A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Исправить ETL-баг с перезаписью стадий и расширить BFF: новый эндпоинт `/bloggers/summary`, фильтр по каналу для блогеров, фильтр `q` для интеграций, поле `primary_substitute_code` в IntegrationOut.

**Architecture:** ETL-фикс в `services/sheets_etl/loader.py` + `run.py`. BFF-расширения в `shared/data_layer/influencer_crm/` (SQL) + `services/influencer_crm/` (роутеры + схемы). Нет миграций БД — данные уже в `crm.*`.

**Spec:** `docs/superpowers/specs/2026-05-06-influencer-crm-v2-design.md`

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy Core (raw `text()`), psycopg2, pgbouncer (transaction mode — все имена schema-qualified `crm.*`)

**Run tests:** `cd /Users/danilamatveev/Projects/Wookiee && python -m pytest tests/services/influencer_crm/ -v`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `services/sheets_etl/loader.py` | Add `no_update_cols` param to `upsert()` |
| Modify | `services/sheets_etl/run.py` | Pass `no_update_cols=["stage"]` for integrations |
| Modify | `shared/data_layer/influencer_crm/integrations.py` | Add `primary_substitute_code` subquery + `q` filter |
| Modify | `services/influencer_crm/schemas/integration.py` | Add `primary_substitute_code: str \| None` field |
| Modify | `services/influencer_crm/routers/integrations.py` | Add `q: str \| None` param |
| Modify | `shared/data_layer/influencer_crm/bloggers.py` | Add `channel` filter + `list_bloggers_summary()` |
| Modify | `services/influencer_crm/schemas/blogger.py` | Add `BloggerSummaryOut` |
| Modify | `services/influencer_crm/routers/bloggers.py` | Add `channel` param + `GET /bloggers/summary` |

---

## Task 1: E1 — ETL не перезаписывает вручную выставленные стадии

**Files:**
- Modify: `services/sheets_etl/loader.py:39-67`
- Modify: `services/sheets_etl/run.py` (строка с `upsert(conn, "crm.integrations", matched)`)

**Проблема:** `upsert()` обновляет все колонки при конфликте, включая `stage`. Если менеджер вручную перетащил карточку — следующий ETL сбрасывает стадию на значение из Sheets.

- [ ] **Step 1: Написать тест**

Создай `tests/services/sheets_etl/test_upsert_no_update_cols.py`:

```python
"""Test that upsert() respects no_update_cols."""
import psycopg2
import pytest
from unittest.mock import MagicMock, patch, call
from services.sheets_etl.loader import upsert


def test_upsert_excludes_no_update_cols():
    """Columns in no_update_cols must be absent from DO UPDATE SET."""
    captured_sql = []

    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def execute_values(self, sql, vals): captured_sql.append(sql)

    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: conn.cursor.return_value
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    rows = [{"sheet_row_id": "abc", "stage": "переговоры", "channel": "instagram"}]

    # Patch execute_values to capture generated SQL
    import psycopg2.extras as extras
    calls = []
    with patch.object(extras, "execute_values", lambda cur, sql, vals: calls.append(sql)):
        upsert(conn, "crm.integrations", rows, no_update_cols=["stage"])

    assert calls, "execute_values was not called"
    sql = calls[0]
    assert "stage" not in sql.split("DO UPDATE SET")[1], (
        f"'stage' must not appear in DO UPDATE SET clause, got: {sql}"
    )
    assert "channel = EXCLUDED.channel" in sql


def test_upsert_no_update_cols_default_empty():
    """Without no_update_cols, all non-conflict cols are updated."""
    rows = [{"sheet_row_id": "abc", "stage": "переговоры", "channel": "instagram"}]
    calls = []
    import psycopg2.extras as extras
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: conn.cursor.return_value
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with patch.object(extras, "execute_values", lambda cur, sql, vals: calls.append(sql)):
        upsert(conn, "crm.integrations", rows)

    assert "stage = EXCLUDED.stage" in calls[0]
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
cd /Users/danilamatveev/Projects/Wookiee
python -m pytest tests/services/sheets_etl/test_upsert_no_update_cols.py -v
```

Ожидается: FAIL — функция `upsert()` не принимает `no_update_cols`.

- [ ] **Step 3: Добавить `no_update_cols` в `upsert()`**

Файл: `services/sheets_etl/loader.py`, функция `upsert` (~строка 39):

```python
def upsert(conn, table: str, rows: list[dict[str, Any]],
           conflict_col: str = "sheet_row_id",
           no_update_cols: list[str] | None = None) -> int:
    """INSERT … ON CONFLICT (conflict_col) DO UPDATE for every column except
    conflict_col and those listed in no_update_cols.

    no_update_cols: columns set only on INSERT, never updated on conflict.
    Use for fields managed manually (e.g. stage in crm.integrations).
    """
    if not rows:
        return 0
    _skip = {conflict_col, *(no_update_cols or [])}
    cols = list(rows[0].keys())
    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in _skip)

    sql = (
        f'INSERT INTO {table} ({", ".join(cols)}) VALUES %s '
        f'ON CONFLICT ({conflict_col}) DO UPDATE SET {update_set}'
    )
    values = [[r[c] for c in cols] for r in rows]
    with conn.cursor() as cur:
        for i in range(0, len(values), _BATCH_SIZE):
            psycopg2.extras.execute_values(cur, sql, values[i:i + _BATCH_SIZE])
    conn.commit()
    return len(rows)
```

- [ ] **Step 4: Запустить тест — убедиться что проходит**

```bash
python -m pytest tests/services/sheets_etl/test_upsert_no_update_cols.py -v
```

Ожидается: PASS (2 tests).

- [ ] **Step 5: Добавить `no_update_cols=["stage"]` в `run_integrations()`**

Файл: `services/sheets_etl/run.py`. Найди строку:
```python
n_i = upsert(conn, "crm.integrations", matched)
```

Замени на:
```python
n_i = upsert(conn, "crm.integrations", matched, no_update_cols=["stage"])
```

- [ ] **Step 6: Запустить существующие тесты ETL**

```bash
python -m pytest tests/services/sheets_etl/ -v
```

Ожидается: все зелёные.

- [ ] **Step 7: Commit**

```bash
git add services/sheets_etl/loader.py services/sheets_etl/run.py
git add tests/services/sheets_etl/test_upsert_no_update_cols.py
git commit -m "fix(etl): preserve manually set stage on integration upsert conflict"
```

---

## Task 2: BFF — `primary_substitute_code` в `IntegrationOut`

**Files:**
- Modify: `shared/data_layer/influencer_crm/integrations.py` — `_LIST_BASE` SQL (строка ~18)
- Modify: `services/influencer_crm/schemas/integration.py` — добавить поле

**Цель:** В таблице интеграций показывать главный продвигаемый артикул (например, "WENDY_PINK"). Данные уже есть в `crm.integration_substitute_articles` + `crm.substitute_articles`.

- [ ] **Step 1: Написать тест**

Создай или расширь `tests/services/influencer_crm/test_integrations_schema.py`:

```python
"""Test that IntegrationOut includes primary_substitute_code."""
from services.influencer_crm.schemas.integration import IntegrationOut


def test_integration_out_has_primary_substitute_code():
    """primary_substitute_code must be optional string."""
    import inspect
    fields = IntegrationOut.model_fields
    assert "primary_substitute_code" in fields, (
        "IntegrationOut must have primary_substitute_code field"
    )
    field = fields["primary_substitute_code"]
    # Field must be nullable (None is valid)
    assert field.default is None or not field.is_required(), (
        "primary_substitute_code must be optional (None default)"
    )
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
python -m pytest tests/services/influencer_crm/test_integrations_schema.py::test_integration_out_has_primary_substitute_code -v
```

- [ ] **Step 3: Добавить поле в схему**

Файл: `services/influencer_crm/schemas/integration.py`. Найди класс `IntegrationOut`, добавь поле после `erid`:

```python
primary_substitute_code: str | None = None
```

- [ ] **Step 4: Добавить subquery в `_LIST_BASE`**

Файл: `shared/data_layer/influencer_crm/integrations.py`, константа `_LIST_BASE` (~строка 18). Добавь subquery в SELECT перед `FROM`:

```python
_LIST_BASE = """
SELECT i.id, i.blogger_id, i.marketer_id, i.brief_id,
       i.publish_date, i.channel, i.ad_format, i.marketplace,
       i.stage, i.outcome, i.is_barter,
       i.cost_placement, i.cost_delivery, i.cost_goods, i.total_cost,
       i.erid,
       i.theme, i.audience_age, i.subscribers, i.min_reach, i.engagement_rate,
       i.plan_cpm, i.plan_ctr, i.plan_clicks, i.plan_cpc,
       i.fact_views, i.fact_cpm, i.fact_clicks, i.fact_ctr, i.fact_cpc,
       i.fact_carts, i.cr_to_cart, i.fact_orders, i.cr_to_order, i.fact_revenue,
       i.created_at, i.updated_at,
       b.display_handle AS blogger_handle,
       m.name AS marketer_name,
       (SELECT sa.code
        FROM crm.integration_substitute_articles isa
        JOIN crm.substitute_articles sa ON sa.id = isa.substitute_article_id
        WHERE isa.integration_id = i.id
        ORDER BY isa.display_order
        LIMIT 1) AS primary_substitute_code
FROM crm.integrations i
JOIN crm.bloggers b ON b.id = i.blogger_id
LEFT JOIN crm.marketers m ON m.id = i.marketer_id
WHERE i.archived_at IS NULL
"""
```

- [ ] **Step 5: Запустить тест — убедиться что проходит**

```bash
python -m pytest tests/services/influencer_crm/test_integrations_schema.py::test_integration_out_has_primary_substitute_code -v
```

- [ ] **Step 6: Запустить все тесты BFF**

```bash
python -m pytest tests/services/influencer_crm/ -v
```

Ожидается: все зелёные.

- [ ] **Step 7: Commit**

```bash
git add shared/data_layer/influencer_crm/integrations.py
git add services/influencer_crm/schemas/integration.py
git commit -m "feat(bff): add primary_substitute_code to IntegrationOut list"
```

---

## Task 3: BFF — фильтр `q` для интеграций + фильтр `channel` для блогеров

**Files:**
- Modify: `shared/data_layer/influencer_crm/integrations.py` — добавить `q` param в `list_integrations()`
- Modify: `services/influencer_crm/routers/integrations.py` — добавить `q` query param
- Modify: `shared/data_layer/influencer_crm/bloggers.py` — добавить `channel` param в `list_bloggers()`
- Modify: `services/influencer_crm/routers/bloggers.py` — добавить `channel` query param

- [ ] **Step 1: Написать тест для q-фильтра интеграций**

Файл `tests/services/influencer_crm/test_integrations_filters.py`:

```python
"""Test q-filter for integrations list."""
from unittest.mock import MagicMock, patch
from shared.data_layer.influencer_crm.integrations import list_integrations


def _make_session(rows):
    session = MagicMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    session.execute.return_value = result
    return session


def test_q_filter_adds_where_clause():
    """When q is provided, SQL must filter by blogger_handle ILIKE."""
    session = _make_session([])
    list_integrations(session, q="wendy", limit=10)
    call_args = session.execute.call_args
    sql = str(call_args[0][0])
    assert "ILIKE" in sql or "ilike" in sql.lower() or "LOWER" in sql, (
        "q filter must use case-insensitive LIKE on blogger_handle"
    )


def test_q_filter_not_added_when_none():
    """When q is None, SQL must not contain blogger_handle filter."""
    session = _make_session([])
    list_integrations(session, limit=10)
    call_args = session.execute.call_args
    sql = str(call_args[0][0])
    assert "blogger_handle" not in sql or "ILIKE" not in sql
```

- [ ] **Step 2: Запустить — убедиться что падает**

```bash
python -m pytest tests/services/influencer_crm/test_integrations_filters.py -v
```

- [ ] **Step 3: Добавить `q` в `list_integrations()`**

Файл: `shared/data_layer/influencer_crm/integrations.py`, функция `list_integrations()`:

Добавить параметр:
```python
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
    q: str | None = None,          # <-- новый параметр
) -> tuple[list[IntegrationOut], str | None]:
```

В блок фильтров добавить после `blogger_id`:
```python
if q:
    where.append("AND LOWER(b.display_handle) LIKE LOWER(:q_pattern)")
    params["q_pattern"] = f"%{q}%"
```

- [ ] **Step 4: Добавить `q` в роутер интеграций**

Файл: `services/influencer_crm/routers/integrations.py`. В функцию-хэндлер `list_integrations_endpoint` (или как она называется) добавить:

```python
q: str | None = Query(default=None, description="Поиск по хэндлу блогера"),
```

И передать в data layer:
```python
items, next_cursor = data_layer.list_integrations(
    session,
    stage_in=stage_in,
    marketplace=marketplace,
    marketer_id=marketer_id,
    blogger_id=blogger_id,
    date_from=date_from,
    date_to=date_to,
    q=q,              # <-- добавить
    cursor=cursor,
    limit=limit,
)
```

- [ ] **Step 5: Добавить `channel` в `list_bloggers()`**

Файл: `shared/data_layer/influencer_crm/bloggers.py`, функция `list_bloggers()`.

Добавить параметр:
```python
def list_bloggers(
    session: Session,
    *,
    limit: int = 50,
    cursor: str | None = None,
    status: str | None = None,
    marketer_id: int | None = None,
    q: str | None = None,
    channel: str | None = None,    # <-- новый параметр
) -> tuple[list[BloggerOut], str | None]:
```

В `_LIST_SQL` добавить `{channel_filter}` в WHERE:
```sql
_LIST_SQL = """
SELECT b.id, b.display_handle, b.real_name, b.status,
       b.default_marketer_id,
       b.price_story_default, b.price_reels_default,
       b.created_at, b.updated_at
FROM crm.bloggers b
WHERE b.archived_at IS NULL
  {status_filter}
  {marketer_filter}
  {channel_filter}
  {cursor_filter}
ORDER BY b.updated_at DESC, b.id DESC
LIMIT :limit
"""
```

В теле функции добавить:
```python
channel_filter = ""
if channel:
    channel_filter = (
        "AND b.id IN ("
        "  SELECT blogger_id FROM crm.blogger_channels"
        "  WHERE channel = :channel"
        ")"
    )
    params["channel"] = channel
```

И передать в `sql = _LIST_SQL.format(..., channel_filter=channel_filter)`.

- [ ] **Step 6: Добавить `channel` в роутер блогеров**

Файл: `services/influencer_crm/routers/bloggers.py`. В хэндлер списка блогеров добавить:

```python
channel: str | None = Query(default=None, description="Фильтр по платформе (instagram/telegram/...)"),
```

Передать в data layer: `channel=channel`.

- [ ] **Step 7: Запустить тест — убедиться что проходит**

```bash
python -m pytest tests/services/influencer_crm/test_integrations_filters.py -v
python -m pytest tests/services/influencer_crm/ -v
```

- [ ] **Step 8: Commit**

```bash
git add shared/data_layer/influencer_crm/integrations.py
git add services/influencer_crm/routers/integrations.py
git add shared/data_layer/influencer_crm/bloggers.py
git add services/influencer_crm/routers/bloggers.py
git add tests/services/influencer_crm/test_integrations_filters.py
git commit -m "feat(bff): add q filter to integrations + channel filter to bloggers"
```

---

## Task 4: BFF — `GET /bloggers/summary` эндпоинт

**Files:**
- Modify: `services/influencer_crm/schemas/blogger.py` — добавить `BloggerSummaryOut`
- Modify: `shared/data_layer/influencer_crm/bloggers.py` — добавить `list_bloggers_summary()`
- Modify: `services/influencer_crm/routers/bloggers.py` — добавить маршрут

**Цель:** Эндпоинт для таблицы блогеров — возвращает список с каналами и агрегированными метриками (взвешенный CPM, кол-во интеграций, сумма расходов). Используется только фронтом в table-view.

**Важно:** маршрут `/bloggers/summary` регистрируется ДО `/bloggers/{id}`, иначе FastAPI распарсит "summary" как integer id и вернёт 422.

- [ ] **Step 1: Написать тест схемы**

Добавь в `tests/services/influencer_crm/test_bloggers_schema.py`:

```python
"""Test BloggerSummaryOut schema."""
from services.influencer_crm.schemas.blogger import BloggerSummaryOut


def test_blogger_summary_out_has_required_fields():
    required = {
        "id", "display_handle", "status",
        "channels", "integrations_count", "integrations_done",
        "total_spent", "avg_cpm_fact",
    }
    actual = set(BloggerSummaryOut.model_fields.keys())
    missing = required - actual
    assert not missing, f"BloggerSummaryOut missing fields: {missing}"


def test_blogger_summary_channels_default_empty_list():
    b = BloggerSummaryOut(
        id=1, display_handle="@test", real_name=None, status="active",
        default_marketer_id=None, price_story_default=None,
        price_reels_default=None, created_at=None, updated_at=None,
        channels=[], integrations_count=0, integrations_done=0,
        last_integration_at=None, total_spent="0",
        avg_cpm_fact=None,
    )
    assert b.channels == []
```

- [ ] **Step 2: Запустить — убедиться что падает**

```bash
python -m pytest tests/services/influencer_crm/test_bloggers_schema.py -v
```

- [ ] **Step 3: Добавить `BloggerSummaryOut` в схему**

Файл: `services/influencer_crm/schemas/blogger.py`. Добавь после существующих классов:

```python
class ChannelBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    channel: str
    handle: str
    url: str | None = None


class BloggerSummaryOut(BaseModel):
    """Enriched blogger row for table view — includes channels + aggregate metrics."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_handle: str
    real_name: str | None = None
    status: str
    default_marketer_id: int | None = None
    price_story_default: str | None = None
    price_reels_default: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    channels: list[ChannelBrief] = []
    integrations_count: int = 0
    integrations_done: int = 0
    last_integration_at: str | None = None
    total_spent: str = "0"
    avg_cpm_fact: str | None = None


class BloggerSummaryPage(BaseModel):
    items: list[BloggerSummaryOut]
    total: int
```

- [ ] **Step 4: Добавить `list_bloggers_summary()` в data layer**

Файл: `shared/data_layer/influencer_crm/bloggers.py`. Добавь в конец файла:

```python
_SUMMARY_SQL = """
SELECT
    b.id, b.display_handle, b.real_name, b.status,
    b.default_marketer_id, b.price_story_default, b.price_reels_default,
    b.created_at::text, b.updated_at::text,
    COALESCE(
        json_agg(
            DISTINCT jsonb_build_object(
                'id',      bc.id,
                'channel', bc.channel,
                'handle',  bc.handle,
                'url',     bc.url
            )
        ) FILTER (WHERE bc.id IS NOT NULL),
        '[]'::json
    ) AS channels,
    COALESCE(t.integrations_count, 0)  AS integrations_count,
    COALESCE(t.integrations_done, 0)   AS integrations_done,
    t.last_integration_at::text        AS last_integration_at,
    COALESCE(t.total_spent::text, '0') AS total_spent,
    CASE
        WHEN SUM(i.fact_views) > 0
        THEN ROUND(
            SUM(i.total_cost::numeric) / NULLIF(SUM(i.fact_views), 0) * 1000,
            2
        )::text
        ELSE NULL
    END AS avg_cpm_fact
FROM crm.bloggers b
LEFT JOIN crm.blogger_channels bc      ON bc.blogger_id = b.id
LEFT JOIN crm.v_blogger_totals t       ON t.blogger_id  = b.id
LEFT JOIN crm.integrations i           ON i.blogger_id  = b.id
                                       AND i.archived_at IS NULL
WHERE b.archived_at IS NULL
  {status_filter}
  {q_filter}
  {channel_filter}
GROUP BY b.id, t.integrations_count, t.integrations_done,
         t.last_integration_at, t.total_spent
ORDER BY b.updated_at DESC, b.id DESC
LIMIT :limit OFFSET :offset
"""

_SUMMARY_COUNT_SQL = """
SELECT COUNT(DISTINCT b.id)
FROM crm.bloggers b
LEFT JOIN crm.blogger_channels bc ON bc.blogger_id = b.id
WHERE b.archived_at IS NULL
  {status_filter}
  {q_filter}
  {channel_filter}
"""


def list_bloggers_summary(
    session: Session,
    *,
    limit: int = 200,
    offset: int = 0,
    status: str | None = None,
    q: str | None = None,
    channel: str | None = None,
) -> tuple[list["BloggerSummaryOut"], int]:
    """Return (rows, total_count) for table view.

    Uses offset pagination (not cursor) because table supports sorting/jumping.
    Limit capped at 500 to prevent OOM as dataset grows.
    """
    from services.influencer_crm.schemas.blogger import BloggerSummaryOut, ChannelBrief
    import json

    limit = min(limit, 500)
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    status_filter = ""
    if status:
        status_filter = "AND b.status = :status"
        params["status"] = status

    q_filter = ""
    if q:
        q_filter = "AND LOWER(b.display_handle) LIKE LOWER(:q_pattern)"
        params["q_pattern"] = f"%{q}%"

    channel_filter = ""
    if channel:
        channel_filter = (
            "AND b.id IN ("
            "  SELECT blogger_id FROM crm.blogger_channels WHERE channel = :channel"
            ")"
        )
        params["channel"] = channel

    fmt = dict(
        status_filter=status_filter,
        q_filter=q_filter,
        channel_filter=channel_filter,
    )
    rows = session.execute(
        text(_SUMMARY_SQL.format(**fmt)), params
    ).mappings().all()

    total_row = session.execute(
        text(_SUMMARY_COUNT_SQL.format(**fmt)),
        {k: v for k, v in params.items() if k not in ("limit", "offset")},
    ).scalar()
    total = total_row or 0

    items = []
    for r in rows:
        channels_raw = r["channels"]
        if isinstance(channels_raw, str):
            channels_raw = json.loads(channels_raw)
        channels = [ChannelBrief(**c) for c in (channels_raw or [])]
        items.append(BloggerSummaryOut(
            **{k: v for k, v in dict(r).items() if k != "channels"},
            channels=channels,
        ))
    return items, total
```

- [ ] **Step 5: Добавить маршрут `GET /bloggers/summary`**

Файл: `services/influencer_crm/routers/bloggers.py`. Добавь ПЕРЕД существующим `@router.get("/{blogger_id}")`:

```python
from services.influencer_crm.schemas.blogger import BloggerSummaryPage


@router.get("/summary", response_model=BloggerSummaryPage)
def get_bloggers_summary(
    status: str | None = None,
    q: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    limit: int = Query(default=200, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    _: None = Depends(verify_api_key),
):
    """Enriched blogger list for table view.

    Returns channels[] + aggregate metrics (weighted avg_cpm_fact).
    Separate from GET /bloggers to preserve its lightweight list shape.
    """
    from shared.data_layer.influencer_crm import bloggers as dl
    items, total = dl.list_bloggers_summary(
        session, limit=limit, offset=offset, status=status, q=q, channel=channel
    )
    return BloggerSummaryPage(items=items, total=total)
```

- [ ] **Step 6: Запустить тесты схемы**

```bash
python -m pytest tests/services/influencer_crm/test_bloggers_schema.py -v
```

- [ ] **Step 7: Запустить все тесты**

```bash
python -m pytest tests/services/influencer_crm/ tests/services/sheets_etl/ -v
```

Ожидается: все зелёные.

- [ ] **Step 8: Commit**

```bash
git add services/influencer_crm/schemas/blogger.py
git add shared/data_layer/influencer_crm/bloggers.py
git add services/influencer_crm/routers/bloggers.py
git add tests/services/influencer_crm/test_bloggers_schema.py
git commit -m "feat(bff): add GET /bloggers/summary with channels + weighted avg_cpm_fact"
```

---

## Task 5: Deploy BFF на сервер

**Условие:** все задачи T1–T4 завершены, на ветке есть коммиты, PR смержен в `main`.

- [ ] **Step 1: Убедиться что тесты зелёные локально**

```bash
python -m pytest tests/services/influencer_crm/ tests/services/sheets_etl/ -v
```

- [ ] **Step 2: Задеплоить на сервер**

```bash
ssh timeweb
cd /home/danila/projects/wookiee && git pull origin main
cd deploy
docker compose build influencer-crm-api
docker compose up -d --force-recreate influencer-crm-api
```

- [ ] **Step 3: Проверить health**

```bash
curl -s https://crm.matveevdanila.com/api/health | python3 -m json.tool
```

Ожидается: `{"status": "ok"}` (или аналогичный ответ).

- [ ] **Step 4: Smoke-test новых эндпоинтов**

```bash
# primary_substitute_code в интеграциях
curl -s -H "X-API-Key: $CRM_KEY" \
  "https://crm.matveevdanila.com/api/integrations?limit=5" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print([i.get('primary_substitute_code') for i in d['items'][:3]])"

# q-фильтр для интеграций
curl -s -H "X-API-Key: $CRM_KEY" \
  "https://crm.matveevdanila.com/api/integrations?q=wendy&limit=5" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['items'][0]['blogger_handle'] if d['items'] else 'empty')"

# bloggers/summary
curl -s -H "X-API-Key: $CRM_KEY" \
  "https://crm.matveevdanila.com/api/bloggers/summary?limit=3" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print([(b['display_handle'], b['channels']) for b in d['items'][:2]])"
```

Ожидается: данные без ошибок 500.

- [ ] **Step 5: Commit деплой-заметки (опционально)**

```bash
# На сервере — ничего не коммитить. Деплой завершён.
```
