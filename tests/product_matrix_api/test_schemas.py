import pytest
from pydantic import ValidationError

from services.product_matrix_api.models.schemas import (
    ModelOsnovaRead,
    ModelOsnovaCreate,
    ModelOsnovaUpdate,
    ModelRead,
    PaginatedResponse,
)


def test_model_osnova_create_valid():
    data = ModelOsnovaCreate(kod="TestModel", kategoriya_id=1)
    assert data.kod == "TestModel"


def test_model_osnova_create_missing_kod():
    with pytest.raises(ValidationError):
        ModelOsnovaCreate()


def test_model_osnova_update_partial():
    data = ModelOsnovaUpdate(material="Хлопок 95%")
    assert data.material == "Хлопок 95%"
    assert data.kod is None


def test_model_osnova_read():
    data = ModelOsnovaRead(
        id=1, kod="Vuki", kategoriya_id=1,
        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    )
    assert data.id == 1


def test_model_read_with_osnova():
    data = ModelRead(
        id=1, kod="Vuki-IP", nazvanie="Vuki ИП",
        model_osnova_id=1, importer_id=1, status_id=1,
        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    )
    assert data.model_osnova_id == 1


def test_paginated_response():
    resp = PaginatedResponse(
        items=[{"id": 1}], total=100, page=1, per_page=50, pages=2,
    )
    assert resp.pages == 2
