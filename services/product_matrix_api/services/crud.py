# services/product_matrix_api/services/crud.py
"""Generic CRUD operations for all product matrix entities.

Uses existing SQLAlchemy models from sku_database/database/models.py.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Type, TypeVar

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

logger = logging.getLogger("product_matrix_api.crud")

T = TypeVar("T")


class CrudService:
    """Generic CRUD operations against SQLAlchemy models."""

    @staticmethod
    def _paginate(page: int, per_page: int) -> tuple[int, int]:
        """Return (offset, limit) for pagination."""
        offset = (page - 1) * per_page
        return offset, per_page

    @staticmethod
    def _build_filters(model: Type[T], filters: dict[str, Any]) -> list:
        """Convert {field: value} dict to SQLAlchemy filter conditions."""
        conditions = []
        mapper = inspect(model) if hasattr(model, "__mapper__") else None
        if not mapper:
            return conditions
        col_names = {c.key for c in mapper.column_attrs}
        for field, value in filters.items():
            if field in col_names and value is not None:
                conditions.append(getattr(model, field) == value)
        return conditions

    @staticmethod
    def get_list(
        db: Session,
        model: Type[T],
        *,
        page: int = 1,
        per_page: int = 50,
        filters: Optional[dict[str, Any]] = None,
        sort: Optional[str] = None,
    ) -> tuple[list[T], int]:
        """Fetch paginated list of records. Returns (items, total_count)."""
        query = select(model)

        if filters:
            for cond in CrudService._build_filters(model, filters):
                query = query.where(cond)

        # Sort
        if sort:
            field, _, direction = sort.partition(":")
            col = getattr(model, field, None)
            if col is not None:
                query = query.order_by(col.desc() if direction == "desc" else col.asc())

        # Count
        count_q = select(func.count()).select_from(query.subquery())
        total = db.execute(count_q).scalar() or 0

        # Paginate
        offset, limit = CrudService._paginate(page, per_page)
        query = query.offset(offset).limit(limit)

        items = list(db.execute(query).scalars().all())
        return items, total

    @staticmethod
    def get_by_id(db: Session, model: Type[T], record_id: int) -> Optional[T]:
        """Fetch single record by id."""
        return db.get(model, record_id)

    @staticmethod
    def create(db: Session, model: Type[T], data: dict[str, Any]) -> T:
        """Create a new record."""
        instance = model(**data)
        db.add(instance)
        db.flush()
        db.refresh(instance)
        return instance

    @staticmethod
    def update(db: Session, instance: T, data: dict[str, Any]) -> T:
        """Update an existing record with non-None fields from data."""
        for field, value in data.items():
            if value is not None and hasattr(instance, field):
                setattr(instance, field, value)
        db.flush()
        db.refresh(instance)
        return instance

    @staticmethod
    def to_dict(instance: Any) -> dict[str, Any]:
        """Convert SQLAlchemy model instance to dict (column values only)."""
        mapper = inspect(type(instance))
        return {c.key: getattr(instance, c.key) for c in mapper.column_attrs}
