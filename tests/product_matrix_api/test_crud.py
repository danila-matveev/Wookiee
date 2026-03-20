# tests/product_matrix_api/test_crud.py
"""Test CRUD service with a mock DB session."""
from services.product_matrix_api.services.crud import CrudService


class FakeModel:
    """Mimics a SQLAlchemy model for testing."""
    __tablename__ = "fake_table"
    id = None
    kod = None

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_paginate_params():
    offset, limit = CrudService._paginate(page=2, per_page=50)
    assert offset == 50
    assert limit == 50


def test_paginate_page_1():
    offset, limit = CrudService._paginate(page=1, per_page=25)
    assert offset == 0
    assert limit == 25
