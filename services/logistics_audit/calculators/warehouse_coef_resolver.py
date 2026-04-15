"""3-tier warehouse coefficient resolution: fixation → Supabase → dlv_prc fallback."""
from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)


@dataclass
class CoefResult:
    value: float
    source: str  # "fixation" | "supabase" | "dlv_prc"
    verified: bool  # False only for dlv_prc fallback


def resolve_warehouse_coef(
    dlv_prc: float,
    fixed_coef: float,
    fixation_end: date | None,
    order_date: date | None,
    warehouse_name: str,
    supabase_tariffs: dict[str, dict[date, float]],
) -> CoefResult:
    """Resolve warehouse coefficient with 3-tier priority.

    Priority:
    1. Fixed coefficient (if fixation is active: fixation_end > order_date)
    2. Supabase wb_tariffs (historical ETL data)
    3. dlv_prc from report (fallback, flagged as not verified)
    """
    # Tier 1: Fixed coefficient (fixation active)
    if fixed_coef > 0 and fixation_end and order_date and fixation_end > order_date:
        return CoefResult(value=fixed_coef, source="fixation", verified=True)

    # Tier 2: Supabase historical tariffs
    wh_tariffs = supabase_tariffs.get(warehouse_name)
    if wh_tariffs and order_date:
        matching_dates = [d for d in wh_tariffs if d <= order_date]
        if matching_dates:
            closest = max(matching_dates)
            coef = wh_tariffs[closest]
            if coef > 0:
                return CoefResult(value=coef, source="supabase", verified=True)

    # Tier 3: dlv_prc fallback
    if dlv_prc > 0:
        return CoefResult(value=dlv_prc, source="dlv_prc", verified=False)

    return CoefResult(value=0.0, source="dlv_prc", verified=False)


def load_tariff_file_coefs(
    tariff_file: str | None = None,
) -> dict[str, dict[date, float]]:
    """Load warehouse coefficients from local tariff Excel file.

    File: Тарифы на логискику.xlsx → sheet 'Тарифы короб'
    Returns: {warehouse_name: {date: delivery_coef_decimal}}
    """
    from pathlib import Path

    if tariff_file is None:
        tariff_file = str(Path(__file__).parent.parent / "Тарифы на логискику.xlsx")

    path = Path(tariff_file)
    if not path.exists():
        logger.warning(f"Tariff file not found: {tariff_file}")
        return {}

    try:
        import openpyxl
    except ImportError:
        logger.warning("openpyxl not installed, skipping tariff file loading")
        return {}

    try:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        ws = wb["Тарифы короб"]

        result: dict[str, dict[date, float]] = {}
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:  # header
                continue
            dt_raw, warehouse, coef_pct, *_ = row
            if dt_raw is None or warehouse is None or coef_pct is None:
                continue
            # Parse date
            from datetime import datetime
            if isinstance(dt_raw, datetime):
                dt = dt_raw.date()
            elif isinstance(dt_raw, date):
                dt = dt_raw
            else:
                continue
            wh_name = str(warehouse).strip()
            if wh_name not in result:
                result[wh_name] = {}
            result[wh_name][dt] = float(coef_pct) / 100.0

        wb.close()
        logger.info(f"Loaded tariff file: {len(result)} warehouses, "
                     f"{sum(len(v) for v in result.values())} data points")
        return result
    except Exception as e:
        logger.warning(f"Failed to load tariff file: {e}")
        return {}


def load_supabase_tariffs(date_from: date, date_to: date) -> dict[str, dict[date, float]]:
    """Load warehouse coefficients from Supabase wb_tariffs table.

    Returns: {warehouse_name: {date: delivery_coef / 100}}
    """
    try:
        import psycopg2
    except ImportError:
        logger.warning("psycopg2 not installed, skipping Supabase tariff lookup")
        return {}

    # Same env vars as etl/tariff_collector.py (Supabase connection)
    config = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("POSTGRES_DB", "postgres"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "sslmode": "require",
    }

    try:
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT dt, warehouse_name, delivery_coef
            FROM wb_tariffs
            WHERE dt BETWEEN %s AND %s
            """,
            (date_from, date_to),
        )
        result: dict[str, dict[date, float]] = {}
        for dt, wh_name, coef in cur.fetchall():
            if wh_name not in result:
                result[wh_name] = {}
            result[wh_name][dt] = coef / 100.0  # stored as pct, need decimal
        cur.close()
        conn.close()
        logger.info(f"Loaded Supabase tariffs: {len(result)} warehouses, "
                     f"{sum(len(v) for v in result.values())} data points")
        return result
    except Exception as e:
        logger.warning(f"Failed to load Supabase tariffs: {e}")
        return {}
