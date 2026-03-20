"""Pydantic v2 schemas for Product Matrix API request/response models."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


# ── Pagination ───────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int


# ── Modeli Osnova ────────────────────────────────────────────────────────────

class ModelOsnovaCreate(BaseModel):
    kod: str
    kategoriya_id: Optional[int] = None
    kollekciya_id: Optional[int] = None
    fabrika_id: Optional[int] = None
    razmery_modeli: Optional[str] = None
    sku_china: Optional[str] = None
    upakovka: Optional[str] = None
    ves_kg: Optional[float] = None
    dlina_cm: Optional[float] = None
    shirina_cm: Optional[float] = None
    vysota_cm: Optional[float] = None
    kratnost_koroba: Optional[int] = None
    srok_proizvodstva: Optional[str] = None
    komplektaciya: Optional[str] = None
    material: Optional[str] = None
    sostav_syrya: Optional[str] = None
    composition: Optional[str] = None
    tip_kollekcii: Optional[str] = None
    tnved: Optional[str] = None
    gruppa_sertifikata: Optional[str] = None
    nazvanie_etiketka: Optional[str] = None
    nazvanie_sayt: Optional[str] = None
    opisanie_sayt: Optional[str] = None
    tegi: Optional[str] = None
    notion_link: Optional[str] = None


class ModelOsnovaUpdate(BaseModel):
    kod: Optional[str] = None
    kategoriya_id: Optional[int] = None
    kollekciya_id: Optional[int] = None
    fabrika_id: Optional[int] = None
    razmery_modeli: Optional[str] = None
    sku_china: Optional[str] = None
    upakovka: Optional[str] = None
    ves_kg: Optional[float] = None
    dlina_cm: Optional[float] = None
    shirina_cm: Optional[float] = None
    vysota_cm: Optional[float] = None
    kratnost_koroba: Optional[int] = None
    srok_proizvodstva: Optional[str] = None
    komplektaciya: Optional[str] = None
    material: Optional[str] = None
    sostav_syrya: Optional[str] = None
    composition: Optional[str] = None
    tip_kollekcii: Optional[str] = None
    tnved: Optional[str] = None
    gruppa_sertifikata: Optional[str] = None
    nazvanie_etiketka: Optional[str] = None
    nazvanie_sayt: Optional[str] = None
    opisanie_sayt: Optional[str] = None
    tegi: Optional[str] = None
    notion_link: Optional[str] = None


class ModelOsnovaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kod: str
    kategoriya_id: Optional[int] = None
    kollekciya_id: Optional[int] = None
    fabrika_id: Optional[int] = None
    razmery_modeli: Optional[str] = None
    material: Optional[str] = None
    sostav_syrya: Optional[str] = None
    tip_kollekcii: Optional[str] = None
    tnved: Optional[str] = None
    nazvanie_sayt: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    kategoriya_name: Optional[str] = None
    kollekciya_name: Optional[str] = None
    fabrika_name: Optional[str] = None
    children_count: Optional[int] = None


# ── Modeli (variations) ─────────────────────────────────────────────────────

class ModelCreate(BaseModel):
    kod: str
    nazvanie: str
    nazvanie_en: Optional[str] = None
    artikul_modeli: Optional[str] = None
    model_osnova_id: Optional[int] = None
    importer_id: Optional[int] = None
    status_id: Optional[int] = None
    nabor: bool = False
    rossiyskiy_razmer: Optional[str] = None


class ModelUpdate(BaseModel):
    kod: Optional[str] = None
    nazvanie: Optional[str] = None
    nazvanie_en: Optional[str] = None
    artikul_modeli: Optional[str] = None
    model_osnova_id: Optional[int] = None
    importer_id: Optional[int] = None
    status_id: Optional[int] = None
    nabor: Optional[bool] = None
    rossiyskiy_razmer: Optional[str] = None


class ModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kod: str
    nazvanie: str
    nazvanie_en: Optional[str] = None
    artikul_modeli: Optional[str] = None
    model_osnova_id: Optional[int] = None
    importer_id: Optional[int] = None
    status_id: Optional[int] = None
    nabor: bool = False
    rossiyskiy_razmer: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    importer_name: Optional[str] = None
    status_name: Optional[str] = None
    artikuly_count: Optional[int] = None
    tovary_count: Optional[int] = None


# ── Audit Log ────────────────────────────────────────────────────────────────

class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: Optional[datetime] = None
    user_email: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    entity_name: Optional[str] = None
    changes: Optional[dict] = None


# ── Lookups (for dropdowns) ──────────────────────────────────────────────────

class LookupItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nazvanie: str
