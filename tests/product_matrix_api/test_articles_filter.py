# tests/product_matrix_api/test_articles_filter.py
"""Route-level tests for FILT-03: articles drill-down by model_osnova_id."""
import pytest
from unittest.mock import patch, MagicMock

from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app
from services.product_matrix_api.config import get_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _fake_db():
    db = MagicMock()
    db.get.return_value = None
    try:
        yield db
    finally:
        pass


@pytest.fixture(autouse=True)
def override_db():
    app.dependency_overrides[get_db] = _fake_db
    yield
    app.dependency_overrides.clear()


def _make_article(id_: int, artikul: str):
    a = MagicMock()
    a.id = id_
    a.artikul = artikul
    for field in [
        "model_id", "cvet_id", "status_id", "nomenklatura_wb",
        "artikul_ozon", "created_at", "updated_at",
        "model_name", "cvet_name", "status_name", "tovary_count",
    ]:
        setattr(a, field, None)
    return a


def _client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", follow_redirects=True)


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_filter_by_model_osnova_id():
    """GET /api/matrix/articles?model_osnova_id=7 resolves child model IDs and passes model_id list."""
    articles = [_make_article(1, "art-001"), _make_article(2, "art-002")]

    # Mock the DB execute for subquery + get_list
    with patch(
        "services.product_matrix_api.routes.articles.CrudService.get_list"
    ) as mock_get_list, patch(
        "services.product_matrix_api.routes.articles.get_model_ids_for_osnova"
    ) as mock_subquery:
        mock_subquery.return_value = [10, 11, 12]
        mock_get_list.return_value = (articles, 2)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/articles", params={"model_osnova_id": "7"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    # Verify get_list was called with model_id list filter
    call_kwargs = mock_get_list.call_args.kwargs
    assert call_kwargs["filters"].get("model_id") == [10, 11, 12]


@pytest.mark.anyio
async def test_filter_by_model_osnova_id_no_children():
    """GET /api/matrix/articles?model_osnova_id=999 with no children returns empty response."""
    with patch(
        "services.product_matrix_api.routes.articles.get_model_ids_for_osnova"
    ) as mock_subquery:
        mock_subquery.return_value = []
        async with _client() as ac:
            resp = await ac.get("/api/matrix/articles", params={"model_osnova_id": "999"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.anyio
async def test_filter_articles_by_status_id():
    """GET /api/matrix/articles?status_id=2 passes status_id=2 in filters."""
    articles = [_make_article(1, "art-001")]

    with patch(
        "services.product_matrix_api.routes.articles.CrudService.get_list"
    ) as mock_get_list:
        mock_get_list.return_value = (articles, 1)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/articles", params={"status_id": "2"})

    assert resp.status_code == 200
    call_kwargs = mock_get_list.call_args.kwargs
    assert call_kwargs["filters"].get("status_id") == 2


@pytest.mark.anyio
async def test_filter_articles_no_model_osnova_uses_direct_filters():
    """GET /api/matrix/articles without model_osnova_id uses direct model_id filter."""
    articles = [_make_article(1, "art-001")]

    with patch(
        "services.product_matrix_api.routes.articles.CrudService.get_list"
    ) as mock_get_list:
        mock_get_list.return_value = (articles, 1)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/articles", params={"model_id": "5"})

    assert resp.status_code == 200
    call_kwargs = mock_get_list.call_args.kwargs
    assert call_kwargs["filters"].get("model_id") == 5
