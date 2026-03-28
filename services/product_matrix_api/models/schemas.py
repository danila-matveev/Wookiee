"""Pydantic v2 schemas for Product Matrix API request/response models."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

import re

from pydantic import BaseModel, ConfigDict, field_validator

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
    status_id: Optional[int] = None
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
    status_id: Optional[int] = None
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
    status_id: Optional[int] = None
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


# ── Artikuly ─────────────────────────────────────────────────────────────────

class ArtikulCreate(BaseModel):
    artikul: str
    model_id: Optional[int] = None
    cvet_id: Optional[int] = None
    status_id: Optional[int] = None
    nomenklatura_wb: Optional[int] = None
    artikul_ozon: Optional[str] = None


class ArtikulUpdate(BaseModel):
    artikul: Optional[str] = None
    model_id: Optional[int] = None
    cvet_id: Optional[int] = None
    status_id: Optional[int] = None
    nomenklatura_wb: Optional[int] = None
    artikul_ozon: Optional[str] = None


class ArtikulRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artikul: str
    model_id: Optional[int] = None
    cvet_id: Optional[int] = None
    status_id: Optional[int] = None
    nomenklatura_wb: Optional[int] = None
    artikul_ozon: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_name: Optional[str] = None
    cvet_name: Optional[str] = None
    status_name: Optional[str] = None
    tovary_count: Optional[int] = None


# ── Tovary (SKU) ─────────────────────────────────────────────────────────────

class TovarCreate(BaseModel):
    barkod: str
    barkod_gs1: Optional[str] = None
    barkod_gs2: Optional[str] = None
    barkod_perehod: Optional[str] = None
    artikul_id: Optional[int] = None
    razmer_id: Optional[int] = None
    status_id: Optional[int] = None
    status_ozon_id: Optional[int] = None
    ozon_product_id: Optional[int] = None
    ozon_fbo_sku_id: Optional[int] = None
    lamoda_seller_sku: Optional[str] = None
    sku_china_size: Optional[str] = None


class TovarUpdate(BaseModel):
    barkod: Optional[str] = None
    barkod_gs1: Optional[str] = None
    barkod_gs2: Optional[str] = None
    barkod_perehod: Optional[str] = None
    artikul_id: Optional[int] = None
    razmer_id: Optional[int] = None
    status_id: Optional[int] = None
    status_ozon_id: Optional[int] = None
    ozon_product_id: Optional[int] = None
    ozon_fbo_sku_id: Optional[int] = None
    lamoda_seller_sku: Optional[str] = None
    sku_china_size: Optional[str] = None


class TovarRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    barkod: str
    barkod_gs1: Optional[str] = None
    barkod_gs2: Optional[str] = None
    barkod_perehod: Optional[str] = None
    artikul_id: Optional[int] = None
    razmer_id: Optional[int] = None
    status_id: Optional[int] = None
    status_ozon_id: Optional[int] = None
    ozon_product_id: Optional[int] = None
    ozon_fbo_sku_id: Optional[int] = None
    lamoda_seller_sku: Optional[str] = None
    sku_china_size: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    artikul_name: Optional[str] = None
    razmer_name: Optional[str] = None
    status_name: Optional[str] = None
    status_ozon_name: Optional[str] = None


# ── Cveta (Colors) ───────────────────────────────────────────────────────────

class CvetCreate(BaseModel):
    color_code: str
    cvet: Optional[str] = None
    color: Optional[str] = None
    lastovica: Optional[str] = None
    status_id: Optional[int] = None


class CvetUpdate(BaseModel):
    color_code: Optional[str] = None
    cvet: Optional[str] = None
    color: Optional[str] = None
    lastovica: Optional[str] = None
    status_id: Optional[int] = None


class CvetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    color_code: str
    cvet: Optional[str] = None
    color: Optional[str] = None
    lastovica: Optional[str] = None
    status_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status_name: Optional[str] = None
    artikuly_count: Optional[int] = None


# ── Fabriki (Factories) ─────────────────────────────────────────────────────

class FabrikaCreate(BaseModel):
    nazvanie: str
    strana: Optional[str] = None


class FabrikaUpdate(BaseModel):
    nazvanie: Optional[str] = None
    strana: Optional[str] = None


class FabrikaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nazvanie: str
    strana: Optional[str] = None
    modeli_count: Optional[int] = None


# ── Importery (Importers) ───────────────────────────────────────────────────

class ImporterCreate(BaseModel):
    nazvanie: str
    nazvanie_en: Optional[str] = None
    inn: Optional[str] = None
    adres: Optional[str] = None


class ImporterUpdate(BaseModel):
    nazvanie: Optional[str] = None
    nazvanie_en: Optional[str] = None
    inn: Optional[str] = None
    adres: Optional[str] = None


class ImporterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nazvanie: str
    nazvanie_en: Optional[str] = None
    inn: Optional[str] = None
    adres: Optional[str] = None
    modeli_count: Optional[int] = None


# ── Skleyki WB (Marketplace cards WB) ───────────────────────────────────────

class SleykaWBCreate(BaseModel):
    nazvanie: str
    importer_id: Optional[int] = None


class SleykaWBUpdate(BaseModel):
    nazvanie: Optional[str] = None
    importer_id: Optional[int] = None


class SleykaWBRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nazvanie: str
    importer_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    importer_name: Optional[str] = None
    tovary_count: Optional[int] = None


# ── Skleyki Ozon (Marketplace cards Ozon) ───────────────────────────────────

class SleykaOzonCreate(BaseModel):
    nazvanie: str
    importer_id: Optional[int] = None


class SleykaOzonUpdate(BaseModel):
    nazvanie: Optional[str] = None
    importer_id: Optional[int] = None


class SleykaOzonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nazvanie: str
    importer_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    importer_name: Optional[str] = None
    tovary_count: Optional[int] = None


# ── Sertifikaty (Certificates) ──────────────────────────────────────────────

class SertifikatCreate(BaseModel):
    nazvanie: str
    tip: Optional[str] = None
    nomer: Optional[str] = None
    data_vydachi: Optional[str] = None
    data_okonchaniya: Optional[str] = None
    organ_sertifikacii: Optional[str] = None
    file_url: Optional[str] = None
    gruppa_sertifikata: Optional[str] = None


class SertifikatUpdate(BaseModel):
    nazvanie: Optional[str] = None
    tip: Optional[str] = None
    nomer: Optional[str] = None
    data_vydachi: Optional[str] = None
    data_okonchaniya: Optional[str] = None
    organ_sertifikacii: Optional[str] = None
    file_url: Optional[str] = None
    gruppa_sertifikata: Optional[str] = None


class SertifikatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nazvanie: str
    tip: Optional[str] = None
    nomer: Optional[str] = None
    data_vydachi: Optional[datetime] = None
    data_okonchaniya: Optional[datetime] = None
    organ_sertifikacii: Optional[str] = None
    file_url: Optional[str] = None
    gruppa_sertifikata: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── Search ───────────────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    entity: str
    id: int
    name: str
    match_field: str
    match_text: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    by_entity: dict[str, int]


# ── Bulk Operations ─────────────────────────────────────────────────────────

class BulkActionRequest(BaseModel):
    ids: list[int]
    action: str  # "update" | "delete"
    changes: Optional[dict] = None  # for "update"


# ── Constants ────────────────────────────────────────────────────────────────

VALID_ENTITY_TYPES = {
    "modeli_osnova", "modeli", "artikuly", "tovary", "cveta",
    "fabriki", "importery", "skleyki_wb", "skleyki_ozon", "sertifikaty",
}

VALID_FIELD_TYPES = {
    "text", "number", "select", "multi_select", "file",
    "url", "relation", "date", "checkbox", "formula", "rollup",
}

FIELD_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,99}$")


# ── Field Definitions ────────────────────────────────────────────────────────

class FieldDefinitionCreate(BaseModel):
    entity_type: str
    field_name: str
    display_name: str
    field_type: str
    config: Optional[dict] = None
    section: Optional[str] = None
    sort_order: int = 0
    is_system: bool = False
    is_visible: bool = True

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, v: str) -> str:
        if v not in VALID_FIELD_TYPES:
            raise ValueError(f"field_type must be one of {sorted(VALID_FIELD_TYPES)}, got '{v}'")
        return v

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        if v not in VALID_ENTITY_TYPES:
            raise ValueError(f"entity_type must be one of {sorted(VALID_ENTITY_TYPES)}, got '{v}'")
        return v

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        if not FIELD_NAME_PATTERN.match(v):
            raise ValueError(
                f"field_name must match ^[a-z][a-z0-9_]{{0,99}}$, got '{v}'"
            )
        return v


class FieldDefinitionUpdate(BaseModel):
    display_name: Optional[str] = None
    field_type: Optional[str] = None
    config: Optional[dict] = None
    section: Optional[str] = None
    sort_order: Optional[int] = None
    is_visible: Optional[bool] = None

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_FIELD_TYPES:
            raise ValueError(f"field_type must be one of {sorted(VALID_FIELD_TYPES)}, got '{v}'")
        return v


class FieldDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    field_name: str
    display_name: str
    field_type: str
    config: Optional[dict] = None
    section: Optional[str] = None
    sort_order: int = 0
    is_system: bool = False
    is_visible: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── Saved Views ──────────────────────────────────────────────────────────────

class ViewConfig(BaseModel):
    columns: list[str] = []
    filters: list[dict[str, Any]] = []
    sort: list[dict[str, Any]] = []
    group_by: Optional[str] = None


class SavedViewCreate(BaseModel):
    entity_type: str
    name: str
    config: dict
    user_id: Optional[int] = None
    is_default: bool = False
    sort_order: int = 0

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        if v not in VALID_ENTITY_TYPES:
            raise ValueError(f"entity_type must be one of {sorted(VALID_ENTITY_TYPES)}, got '{v}'")
        return v


class SavedViewUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    is_default: Optional[bool] = None
    sort_order: Optional[int] = None


class SavedViewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    entity_type: str
    name: str
    config: dict
    is_default: bool = False
    sort_order: int = 0
    created_at: Optional[datetime] = None


# ── Phase 5: Delete / Archive / Admin ────────────────────────────────────────

class DeleteImpact(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str
    strategy: str  # "cascade_archive" | "block_if_active" | "simple"
    children: dict[str, int] = {}
    blocked_by: Optional[dict[str, int]] = None
    message: str


class DeleteChallenge(BaseModel):
    requires_confirmation: bool = True
    challenge: str  # e.g. "27 × 3"
    expected_hash: str  # sha256(answer + salt)
    impact: DeleteImpact


class ArchiveRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_table: str
    original_id: int
    full_record: dict
    related_records: Optional[list] = None
    deleted_by: Optional[str] = None
    deleted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    restore_available: bool = True


class TableStats(BaseModel):
    name: str
    count: int
    growth_week: int = 0
    growth_month: int = 0


class DbStats(BaseModel):
    tables: list[TableStats]
    total_records: int


# ── External Data: Stock ─────────────────────────────────────────────────────

class StockChannel(BaseModel):
    stock_mp: float
    daily_sales: float
    turnover_days: float
    sales_count: int
    days_in_stock: int


class MoySkladStock(BaseModel):
    stock_main: float
    stock_transit: float
    total: float
    snapshot_date: Optional[str]
    is_stale: bool


class StockResponse(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str
    period_days: int
    wb: Optional[StockChannel]
    ozon: Optional[StockChannel]
    moysklad: Optional[MoySkladStock]
    total_stock: float
    total_turnover_days: Optional[float]


# ── External Data: Finance ───────────────────────────────────────────────────

class ExpenseItem(BaseModel):
    value: float
    pct: float
    delta_value: Optional[float] = None
    delta_pct: Optional[float] = None


class DRR(BaseModel):
    total: float
    internal: float
    external: float


class FinanceChannel(BaseModel):
    revenue_before_spp: float
    revenue_after_spp: float
    margin: float
    margin_pct: float
    orders_count: int
    orders_sum: float
    sales_count: int
    sales_sum: float
    avg_check_before_spp: float
    avg_check_after_spp: float
    spp_pct: float
    buyout_pct: float
    returns_count: int
    returns_pct: float
    expenses: dict[str, ExpenseItem]
    drr: DRR


class FinanceDelta(BaseModel):
    revenue_before_spp: float
    revenue_after_spp: float
    margin: float
    margin_pct: float
    orders_count: int
    orders_sum: float
    sales_count: int
    avg_check_before_spp: float
    avg_check_after_spp: float
    spp_pct: float
    buyout_pct: float
    returns_count: int
    returns_pct: float
    drr_total: float
    drr_internal: float
    drr_external: float


class FinanceResponse(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str
    period_start: str
    period_end: str
    compare_period_start: Optional[str]
    compare_period_end: Optional[str]
    wb: Optional[FinanceChannel]
    ozon: Optional[FinanceChannel]
    delta_wb: Optional[FinanceDelta]
    delta_ozon: Optional[FinanceDelta]
