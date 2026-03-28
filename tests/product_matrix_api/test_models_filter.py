# tests/product_matrix_api/test_models_filter.py
"""Route-level tests for FILT-01 (status_id) and FILT-02 (multi-select params)."""
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


def _make_model(id_: int, kod: str):
    m = MagicMock()
    m.id = id_
    m.kod = kod
    for field in [
        "kategoriya_id", "kollekciya_id", "fabrika_id", "status_id",
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
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", follow_redirects=True)


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_filter_by_status_id():
    """GET /api/matrix/models?status_id=1 passes status_id=1 (int) in filters to get_list."""
    models = [_make_model(1, "M-001")]

    with patch(
        "services.product_matrix_api.routes.models.CrudService.get_list"
    ) as mock_get_list:
        mock_get_list.return_value = (models, 1)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/models", params={"status_id": "1"})

    assert resp.status_code == 200
    call_kwargs = mock_get_list.call_args.kwargs
    assert "filters" in call_kwargs
    assert call_kwargs["filters"].get("status_id") == 1


@pytest.mark.anyio
async def test_filter_by_kategoriya_multi():
    """GET /api/matrix/models?kategoriya_id=1,5 passes kategoriya_id=[1,5] (list) in filters."""
    models = [_make_model(1, "M-001"), _make_model(2, "M-002")]

    with patch(
        "services.product_matrix_api.routes.models.CrudService.get_list"
    ) as mock_get_list:
        mock_get_list.return_value = (models, 2)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/models", params={"kategoriya_id": "1,5"})

    assert resp.status_code == 200
    call_kwargs = mock_get_list.call_args.kwargs
    assert call_kwargs["filters"].get("kategoriya_id") == [1, 5]


@pytest.mark.anyio
async def test_filter_by_kategoriya_single():
    """GET /api/matrix/models?kategoriya_id=3 passes kategoriya_id=3 (int scalar) in filters."""
    models = [_make_model(1, "M-001")]

    with patch(
        "services.product_matrix_api.routes.models.CrudService.get_list"
    ) as mock_get_list:
        mock_get_list.return_value = (models, 1)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/models", params={"kategoriya_id": "3"})

    assert resp.status_code == 200
    call_kwargs = mock_get_list.call_args.kwargs
    assert call_kwargs["filters"].get("kategoriya_id") == 3


@pytest.mark.anyio
async def test_no_filters_passes_empty_or_no_filters():
    """GET /api/matrix/models with no filter params passes empty filters dict."""
    models = [_make_model(1, "M-001")]

    with patch(
        "services.product_matrix_api.routes.models.CrudService.get_list"
    ) as mock_get_list:
        mock_get_list.return_value = (models, 1)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/models")

    assert resp.status_code == 200
    call_kwargs = mock_get_list.call_args.kwargs
    # filters should be empty dict (no active params)
    assert call_kwargs.get("filters", {}) == {}


@pytest.mark.anyio
async def test_filter_by_fabrika_id():
    """GET /api/matrix/models?fabrika_id=2 passes fabrika_id=2 in filters."""
    models = [_make_model(1, "M-001")]

    with patch(
        "services.product_matrix_api.routes.models.CrudService.get_list"
    ) as mock_get_list:
        mock_get_list.return_value = (models, 1)
        async with _client() as ac:
            resp = await ac.get("/api/matrix/models", params={"fabrika_id": "2"})

    assert resp.status_code == 200
    call_kwargs = mock_get_list.call_args.kwargs
    assert call_kwargs["filters"].get("fabrika_id") == 2
