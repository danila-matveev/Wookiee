"""Configuration for the Hub → Google Sheets mirror sync."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

CATALOG_MIRROR_SHEET_ID: str = os.getenv("CATALOG_MIRROR_SHEET_ID", "")
GOOGLE_SA_FILE: str = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    str(Path(__file__).resolve().parents[1] / "credentials" / "google_sa.json"),
)

# Status value applied to sheet rows whose anchor disappeared from the DB
# (non-skleyki sheets only — skleyki rows are physically removed).
ARCHIVE_STATUS_VALUE: str = "Архив"


@dataclass(frozen=True)
class SheetSpec:
    """Mapping between a sheet tab and its Supabase view.

    Attributes:
        sheet_name:   tab name in the mirror spreadsheet (must already exist
                      and have a header row).
        view_name:    fully-qualified view in Supabase (public.vw_export_*).
        anchor_cols:  business-key column(s) used to match a DB row to a
                      sheet row. Single column → simple key; tuple → composite.
        status_col:   header name of the status column that gets set to
                      "Архив" for deleted rows. None → physical delete on
                      missing-from-DB rows (skleyki).
    """

    sheet_name: str
    view_name: str
    anchor_cols: tuple[str, ...]
    status_col: str | None


SHEET_SPECS: list[SheetSpec] = [
    SheetSpec(
        sheet_name="Все модели",
        view_name="public.vw_export_modeli",
        anchor_cols=("Модель",),
        status_col="Статус",
    ),
    SheetSpec(
        sheet_name="Все артикулы",
        view_name="public.vw_export_artikuly",
        anchor_cols=("Артикул",),
        status_col="Статус",
    ),
    SheetSpec(
        sheet_name="Все товары",
        view_name="public.vw_export_tovary",
        anchor_cols=("БАРКОД",),
        status_col="Статус товара",
    ),
    SheetSpec(
        sheet_name="Аналитики цветов",
        view_name="public.vw_export_cveta",
        anchor_cols=("Color code",),
        status_col="Статус",
    ),
    SheetSpec(
        sheet_name="Склейки WB",
        view_name="public.vw_export_skleyki_wb",
        anchor_cols=("Название склейки", "БАРКОД"),
        status_col=None,
    ),
    SheetSpec(
        sheet_name="Склейки Озон",
        view_name="public.vw_export_skleyki_ozon",
        anchor_cols=("Название склейки", "БАРКОД"),
        status_col=None,
    ),
]


def get_spec(sheet_name: str) -> SheetSpec:
    """Return the SheetSpec for a tab name (case-sensitive). Raises KeyError if absent."""
    for spec in SHEET_SPECS:
        if spec.sheet_name == sheet_name:
            return spec
    raise KeyError(f"No SheetSpec for sheet '{sheet_name}'. Known: {[s.sheet_name for s in SHEET_SPECS]}")
