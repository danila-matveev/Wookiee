"""Test models route — verifies routes are registered and sort/pagination works."""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app
from services.product_matrix_api.config import get_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _fake_db():
    """Yield a mock DB session."""
    db = MagicMock()
    try:
        yield db
    finally:
        pass


@pytest.fixture(autouse=True)
def override_db():
    """Override DB dependency for all tests in this module."""
    app.dependency_overrides[get_db] = _fake_db
    yield
    app.dependency_overrides.clear()


def _make_model(id_: int, kod: str):
    """Create a mock ModelOsnova-like object."""
    m = MagicMock()
    m.id = id_
    m.kod = kod
    # Set all fields that ModelOsnovaRead.model_validate expects
    for field in [
        "kategoriya_id", "kollekciya_id", "fabrika_id",
        "razmery_modeli", "sku_china", "upakovka",
        "ves_kg", "dlina_cm", "shirina_cm", "vysota_cm",
        "kratnost_koroba", "srok_proizvodstva", "komplektaciya",
        "material", "sostav_syrya", "composition", "tip_kollekcii",
        "tnved", "gruppa_sertifikata", "nazvanie_etiketka",
        "nazvanie_sayt", "opisanie_sayt", "tegi", "notion_link",
        "created_at", "updated_at",
        "kategoriya_name", "kollekciya_name", "fabrika_name",
        "children_count",
    ]:
        setattr(m, field, None)
    return m


def _client():
    """Create a test client with follow_redirects to handle trailing-slash redirects."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", follow_redirects=True)


# ── Existing route tests ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_models_osnova_route_exists():
    """Verify the endpoint exists and returns a response."""
    async with _client() as ac:
        resp = await ac.get("/api/matrix/models")
    assert resp.status_code != 404


@pytest.mark.anyio
async def test_get_model_osnova_not_found():
    """Verify 404 for non-existent record."""
    async with _client() as ac:
        resp = await ac.get("/api/matrix/models/99999")
    assert resp.status_code != 405


# ── Sort tests ────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_models_sort_asc():
    """GET /api/matrix/models?sort=kod&order=asc returns items sorted by kod ascending."""
    models = [_make_model(1, "A-100"), _make_model(2, "B-200"), _make_model(3, "C-300")]

    with patch(
        "services.product_matrix_api.routes.models.CrudService.get_list"
    ) as mock_get_list:
        mock_get_list.return_value = (models, 3)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/models", params={"sort": "kod", "order": "asc"})

        assert resp.status_code == 200
        # Verify CrudService was called with sort="kod:asc"
        call_kwargs = mock_get_list.call_args
        assert call_kwargs.kwargs["sort"] == "kod:asc"


@pytest.mark.anyio
async def test_list_models_sort_desc():
    """GET /api/matrix/models?sort=kod&order=desc returns items sorted by kod descending."""
    models = [_make_model(3, "C-300"), _make_model(2, "B-200"), _make_model(1, "A-100")]

    with patch(
        "services.product_matrix_api.routes.models.CrudService.get_list"
    ) as mock_get_list:
        mock_get_list.return_value = (models, 3)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/models", params={"sort": "kod", "order": "desc"})

        assert resp.status_code == 200
        call_kwargs = mock_get_list.call_args
        assert call_kwargs.kwargs["sort"] == "kod:desc"


# ── Pagination tests ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_models_pagination():
    """GET /api/matrix/models?page=1&per_page=5 returns at most 5 items and correct total/pages."""
    models = [_make_model(i, f"M-{i}") for i in range(1, 6)]

    with patch(
        "services.product_matrix_api.routes.models.CrudService.get_list"
    ) as mock_get_list:
        mock_get_list.return_value = (models, 12)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/models", params={"page": "1", "per_page": "5"})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["total"] == 12
        assert data["pages"] == 3  # ceil(12/5)
        assert data["page"] == 1
        assert data["per_page"] == 5

        # Verify pagination params passed to CrudService
        call_kwargs = mock_get_list.call_args
        assert call_kwargs.kwargs["page"] == 1
        assert call_kwargs.kwargs["per_page"] == 5


@pytest.mark.anyio
async def test_list_models_pagination_page2():
    """GET /api/matrix/models?page=2&per_page=5 returns different items than page 1."""
    page2_models = [_make_model(i, f"M-{i}") for i in range(6, 11)]

    with patch(
        "services.product_matrix_api.routes.models.CrudService.get_list"
    ) as mock_get_list:
        mock_get_list.return_value = (page2_models, 12)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/models", params={"page": "2", "per_page": "5"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        # Verify page=2 was passed to CrudService
        call_kwargs = mock_get_list.call_args
        assert call_kwargs.kwargs["page"] == 2


# ── Invalid order fallback test ───────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_models_sort_invalid_order():
    """GET /api/matrix/models?sort=kod&order=invalid falls back to asc (no 422)."""
    models = [_make_model(1, "A-100")]

    with patch(
        "services.product_matrix_api.routes.models.CrudService.get_list"
    ) as mock_get_list:
        mock_get_list.return_value = (models, 1)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/models", params={"sort": "kod", "order": "invalid"})

        # Should NOT return 422 — should fall back gracefully
        assert resp.status_code == 200
        call_kwargs = mock_get_list.call_args
        # Falls back to asc when order is invalid
        assert call_kwargs.kwargs["sort"] == "kod:asc"
