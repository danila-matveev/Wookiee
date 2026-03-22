"""SQLAlchemy models for new tables introduced by the Product Matrix Editor.

Existing tables (modeli_osnova, modeli, artikuly, tovary, etc.) are already
defined in sku_database/database/models.py — we import and reuse them.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Integer, String, Text, Boolean, DateTime, BigInteger,
    ForeignKey, CheckConstraint, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from sku_database.database.models import Base


class _DefaultsMixin:
    """Apply scalar column defaults at Python object construction time.

    SQLAlchemy's ``default=`` on ``mapped_column`` is an INSERT-time default;
    it does not populate the attribute when the object is instantiated in
    Python without a session.  This mixin walks the table's column definitions
    and injects any declared scalar defaults so that unit tests (and other
    in-memory usage) get the expected values immediately.
    """

    def __init__(self, **kwargs: object) -> None:
        for col in self.__table__.columns:  # type: ignore[attr-defined]
            if (
                col.name not in kwargs
                and col.default is not None
                and col.default.is_scalar
            ):
                kwargs[col.name] = col.default.arg
        super().__init__(**kwargs)  # type: ignore[call-arg]


# ── Public schema: new tables ────────────────────────────────────────────────

class FieldDefinition(_DefaultsMixin, Base):
    """Метаданные кастомных полей (реестр, не DDL)."""
    __tablename__ = "field_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[str] = mapped_column(
        String(30),
        CheckConstraint(
            "field_type IN ('text','number','select','multi_select','file',"
            "'url','relation','date','checkbox','formula','rollup')"
        ),
        nullable=False,
    )
    config: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    section: Mapped[Optional[str]] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Sertifikat(_DefaultsMixin, Base):
    """Сертификаты."""
    __tablename__ = "sertifikaty"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nazvanie: Mapped[str] = mapped_column(String(200), nullable=False)
    tip: Mapped[Optional[str]] = mapped_column(String(100))
    nomer: Mapped[Optional[str]] = mapped_column(String(100))
    data_vydachi: Mapped[Optional[datetime]] = mapped_column(DateTime)
    data_okonchaniya: Mapped[Optional[datetime]] = mapped_column(DateTime)
    organ_sertifikacii: Mapped[Optional[str]] = mapped_column(String(200))
    file_url: Mapped[Optional[str]] = mapped_column(Text)
    gruppa_sertifikata: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ModelOsnovaSertifikat(_DefaultsMixin, Base):
    """Связь сертификатов с моделями основы (many-to-many)."""
    __tablename__ = "modeli_osnova_sertifikaty"

    model_osnova_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("modeli_osnova.id", ondelete="CASCADE"), primary_key=True,
    )
    sertifikat_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sertifikaty.id", ondelete="CASCADE"), primary_key=True,
    )


class ArchiveRecord(_DefaultsMixin, Base):
    """Архив мягко удалённых записей."""
    __tablename__ = "archive_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_table: Mapped[str] = mapped_column(String(50), nullable=False)
    original_id: Mapped[int] = mapped_column(Integer, nullable=False)
    full_record: Mapped[dict] = mapped_column(JSON, nullable=False)
    related_records: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    deleted_by: Mapped[Optional[str]] = mapped_column(String(100))
    deleted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    restore_available: Mapped[bool] = mapped_column(Boolean, default=True)


# ── Hub schema: UI data ─────────────────────────────────────────────────────

class HubUser(_DefaultsMixin, Base):
    """Пользователи Wookiee Hub."""
    __tablename__ = "users"
    __table_args__ = {"schema": "hub"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class HubAuditLog(_DefaultsMixin, Base):
    """Аудит лог действий в UI."""
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "hub"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    user_id: Mapped[Optional[int]] = mapped_column(Integer)
    user_email: Mapped[Optional[str]] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    entity_name: Mapped[Optional[str]] = mapped_column(String(200))
    changes: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    request_id: Mapped[Optional[str]] = mapped_column(String(36))
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default=dict)


class HubSavedView(_DefaultsMixin, Base):
    """Сохранённые представления таблиц (per user)."""
    __tablename__ = "saved_views"
    __table_args__ = {"schema": "hub"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
