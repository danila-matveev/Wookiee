"""External marketplace data integration for Product Matrix entities.

Provides stock/inventory and unit-economics data by resolving matrix entities
to marketplace keys and querying the contractor database.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional

from cachetools import TTLCache
from sqlalchemy.orm import Session

from sku_database.database.models import (
    ModelOsnova, Model, Artikul, Tovar, SleykaWB, SleykaOzon,
)
from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection, to_float
from shared.data_layer._sql_fragments import WB_MARGIN_SQL
from shared.model_mapping import get_osnova_sql
from shared.data_layer.inventory import (
    get_wb_turnover_by_model,
    get_ozon_turnover_by_model,
    get_moysklad_stock_by_model,
    get_wb_avg_stock,
    get_ozon_avg_stock,
    get_moysklad_stock_by_article,
)
from shared.data_layer.article import (
    get_wb_by_article,
    get_ozon_by_article,
    get_wb_fin_data_by_barcode,
    get_ozon_fin_data_by_barcode,
    get_wb_orders_by_barcode,
    get_ozon_orders_by_barcode,
)

from services.product_matrix_api.models.schemas import (
    StockChannel, MoySkladStock, StockResponse,
    ExpenseItem, DRR, FinanceChannel, FinanceDelta, FinanceResponse,
)

logger = logging.getLogger(__name__)

# Entity types that have marketplace data (stock/finance tabs visible)
ENTITIES_WITH_MP_DATA = frozenset({
    "models_osnova", "models", "articles", "products", "cards_wb", "cards_ozon",
})

# Bulk data cache: TTL 1 hour, max 32 entries
_bulk_cache: TTLCache = TTLCache(maxsize=64, ttl=3600)

_BULK_FUNCS = {
    "wb_turnover": get_wb_turnover_by_model,
    "ozon_turnover": get_ozon_turnover_by_model,
    "moysklad": get_moysklad_stock_by_model,
    "wb_avg_stock": get_wb_avg_stock,
    "ozon_avg_stock": get_ozon_avg_stock,
    "wb_by_article": get_wb_by_article,
    "ozon_by_article": get_ozon_by_article,
    "wb_fin_barcode": get_wb_fin_data_by_barcode,
    "ozon_fin_barcode": get_ozon_fin_data_by_barcode,
    "wb_orders_barcode": get_wb_orders_by_barcode,
    "ozon_orders_barcode": get_ozon_orders_by_barcode,
}

# Finance query cache: TTL 30 min, max 64 entries
_finance_cache: TTLCache = TTLCache(maxsize=64, ttl=1800)

# MoySklad article cache (no date args): TTL 1 hour
_ms_article_cache: TTLCache = TTLCache(maxsize=1, ttl=3600)


@dataclass
class MarketplaceKey:
    level: str          # "model" | "article" | "barcode" | "barcode_list"
    key: Optional[str] = None
    keys: Optional[List[str]] = None
    channel: Optional[str] = None  # "wb" | "ozon" | None (both)


def resolve_marketplace_key(entity_type: str, entity_id: int, db: Session) -> MarketplaceKey:
    """Resolve a matrix entity to its marketplace lookup key."""
    if entity_type == "models_osnova":
        record = db.get(ModelOsnova, entity_id)
        if not record:
            raise ValueError(f"ModelOsnova #{entity_id} not found")
        return MarketplaceKey(level="model", key=record.kod.lower())

    elif entity_type == "models":
        record = db.get(Model, entity_id)
        if not record:
            raise ValueError(f"Model #{entity_id} not found")
        return MarketplaceKey(level="model", key=record.kod.lower())

    elif entity_type == "articles":
        record = db.get(Artikul, entity_id)
        if not record:
            raise ValueError(f"Artikul #{entity_id} not found")
        return MarketplaceKey(level="article", key=record.artikul.lower())

    elif entity_type == "products":
        record = db.get(Tovar, entity_id)
        if not record:
            raise ValueError(f"Tovar #{entity_id} not found")
        return MarketplaceKey(level="barcode", key=record.barkod)

    elif entity_type == "cards_wb":
        record = db.get(SleykaWB, entity_id)
        if not record:
            raise ValueError(f"SleykaWB #{entity_id} not found")
        barcodes = [t.barkod for t in record.tovary if t.barkod]
        return MarketplaceKey(level="barcode_list", keys=barcodes, channel="wb")

    elif entity_type == "cards_ozon":
        record = db.get(SleykaOzon, entity_id)
        if not record:
            raise ValueError(f"SleykaOzon #{entity_id} not found")
        barcodes = [t.barkod for t in record.tovary if t.barkod]
        return MarketplaceKey(level="barcode_list", keys=barcodes, channel="ozon")

    else:
        raise ValueError(f"Entity type '{entity_type}' has no marketplace mapping")


def _get_cached_bulk(func_name: str, *args):
    """Cache result of a bulk data_layer function."""
    cache_key = f"{func_name}:{args}"
    if cache_key not in _bulk_cache:
        _bulk_cache[cache_key] = _BULK_FUNCS[func_name](*args)
    return _bulk_cache[cache_key]


def _get_cached_ms_article():
    """Cache MoySklad stock by article (no date args)."""
    cache_key = "moysklad_article"
    if cache_key not in _ms_article_cache:
        _ms_article_cache[cache_key] = get_moysklad_stock_by_article()
    return _ms_article_cache[cache_key]


def _calc_dates(period_days: int, compare: str):
    """Calculate date ranges for finance queries.

    Returns (current_start, prev_start, current_end, compare_period_end).
    """
    today = date.today()
    current_end = today.isoformat()
    current_start = (today - timedelta(days=period_days)).isoformat()

    if compare == "week":
        prev_start = (today - timedelta(days=period_days + 7)).isoformat()
    elif compare == "month":
        prev_start = (today - timedelta(days=period_days + 30)).isoformat()
    else:
        prev_start = current_start

    compare_period_end = current_start if compare != "none" else None
    return current_start, prev_start, current_end, compare_period_end


# ---------------------------------------------------------------------------
# Barcode-level stock SQL (no bulk functions exist at barcode level)
# ---------------------------------------------------------------------------

def _get_wb_barcode_stock(barcodes: List[str]) -> Dict[str, float]:
    """WB stock for specific barcodes from the latest date in stocks table."""
    if not barcodes:
        return {}
    conn = _get_wb_connection()
    cur = conn.cursor()
    try:
        placeholders = ",".join(["%s"] * len(barcodes))
        cur.execute(f"""
        SELECT barcode, SUM(quantityfull) as stock
        FROM stocks
        WHERE barcode IN ({placeholders})
          AND lastchangedate::date = (SELECT MAX(lastchangedate::date) FROM stocks)
          AND tip = 'FBO'
        GROUP BY barcode;
        """, barcodes)
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return {str(r[0]): to_float(r[1]) for r in rows}


def _get_ozon_barcode_stock(barcodes: List[str]) -> Dict[str, float]:
    """Ozon stock for specific barcodes. JOIN nomenclature to map barcode->offer_id."""
    if not barcodes:
        return {}
    conn = _get_ozon_connection()
    cur = conn.cursor()
    try:
        placeholders = ",".join(["%s"] * len(barcodes))
        cur.execute(f"""
        SELECT n.barcode, SUM(s.stockspresent) as stock
        FROM stocks s
        JOIN nomenclature n ON s.offer_id = n.article
        WHERE n.barcode IN ({placeholders})
          AND s.dateupdate::date = (SELECT MAX(dateupdate::date) FROM stocks)
        GROUP BY n.barcode;
        """, barcodes)
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return {str(r[0]): to_float(r[1]) for r in rows}


def _get_wb_barcode_daily_sales(barcodes: List[str], start_date: str, end_date: str) -> Dict[str, float]:
    """WB daily sales for specific barcodes from abc_date."""
    if not barcodes:
        return {}
    conn = _get_wb_connection()
    cur = conn.cursor()
    try:
        placeholders = ",".join(["%s"] * len(barcodes))
        cur.execute(f"""
        SELECT barcode, SUM(full_counts) as sales_count
        FROM abc_date
        WHERE barcode IN ({placeholders})
          AND date >= %s AND date < %s
        GROUP BY barcode;
        """, barcodes + [start_date, end_date])
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return {str(r[0]): to_float(r[1]) for r in rows}


def _get_ozon_barcode_daily_sales(barcodes: List[str], start_date: str, end_date: str) -> Dict[str, float]:
    """Ozon daily sales for specific barcodes from abc_date via nomenclature JOIN."""
    if not barcodes:
        return {}
    conn = _get_ozon_connection()
    cur = conn.cursor()
    try:
        placeholders = ",".join(["%s"] * len(barcodes))
        cur.execute(f"""
        SELECT COALESCE(n.barcode, a.article) as barcode, SUM(a.count_end) as sales_count
        FROM abc_date a
        LEFT JOIN nomenclature n ON a.article = n.article AND a.lk = n.lk
        WHERE COALESCE(n.barcode, a.article) IN ({placeholders})
          AND a.date >= %s AND a.date < %s
        GROUP BY 1;
        """, barcodes + [start_date, end_date])
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return {str(r[0]): to_float(r[1]) for r in rows}


# ---------------------------------------------------------------------------
# Article-level finance SQL
# ---------------------------------------------------------------------------

def _get_article_wb_finance(current_start: str, prev_start: str, current_end: str, article_key: str):
    """WB unit-economics for a single article. Same shape as _get_full_wb_finance."""
    conn = _get_wb_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
        SELECT
            CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
            SUM(full_counts) as sales_count,
            SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
            SUM(revenue) - COALESCE(SUM(revenue_return), 0) as revenue_after_spp,
            SUM(reclama) as adv_internal,
            SUM(reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_external,
            SUM(sebes) as cost_of_goods,
            SUM(logist) as logistics,
            SUM(storage) as storage,
            SUM(comis_spp) as commission,
            SUM(spp) as spp_amount,
            SUM(nds) as nds,
            SUM(penalty) as penalty,
            SUM(retention) as retention,
            SUM(deduction) as deduction,
            {WB_MARGIN_SQL} as margin,
            COALESCE(SUM(revenue_return_spp), 0) as returns_revenue,
            0 as returns_count_direct
        FROM abc_date
        WHERE date >= %s AND date < %s
          AND LOWER(article) = %s
        GROUP BY 1
        ORDER BY period DESC;
        """, (current_start, prev_start, current_end, article_key))
        sales_data = cur.fetchall()

        cur.execute("""
        SELECT
            CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
            COUNT(*) as orders_count,
            SUM(pricewithdisc) as orders_rub
        FROM orders
        WHERE date >= %s AND date < %s
          AND LOWER(supplierarticle) = %s
        GROUP BY 1
        ORDER BY period DESC;
        """, (current_start, prev_start, current_end, article_key))
        orders_data = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return sales_data, orders_data


def _get_article_ozon_finance(current_start: str, prev_start: str, current_end: str, article_key: str):
    """Ozon unit-economics for a single article. Same shape as _get_full_ozon_finance."""
    conn = _get_ozon_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT
            CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
            SUM(count_end) as sales_count,
            SUM(price_end) as revenue_before_spp,
            SUM(price_end_spp) as revenue_after_spp,
            SUM(reclama_end) as adv_internal,
            SUM(adv_vn) as adv_external,
            SUM(sebes_end) as cost_of_goods,
            SUM(logist_end) as logistics,
            SUM(storage_end) as storage,
            SUM(comission_end) as commission,
            SUM(spp) as spp_amount,
            SUM(nds) as nds,
            0 as penalty, 0 as retention, 0 as deduction,
            SUM(marga) - SUM(nds) as margin,
            0 as returns_revenue,
            COALESCE(SUM(count_return), 0) as returns_count_direct
        FROM abc_date
        WHERE date >= %s AND date < %s
          AND LOWER(REGEXP_REPLACE(article, '_[^_]+$', '')) = %s
        GROUP BY 1
        ORDER BY period DESC;
        """, (current_start, prev_start, current_end, article_key))
        sales_data = cur.fetchall()

        cur.execute("""
        SELECT
            CASE WHEN in_process_at::date >= %s THEN 'current' ELSE 'previous' END as period,
            COUNT(*) as orders_count,
            SUM(price) as orders_rub
        FROM orders
        WHERE in_process_at::date >= %s AND in_process_at::date < %s
          AND LOWER(REGEXP_REPLACE(offer_id, '_[^_]+$', '')) = %s
        GROUP BY 1
        ORDER BY period DESC;
        """, (current_start, prev_start, current_end, article_key))
        orders_data = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return sales_data, orders_data


# ---------------------------------------------------------------------------
# Build FinanceChannel from barcode-level dicts
# ---------------------------------------------------------------------------

def _build_finance_channel_from_barcode_dicts(
    fin_rows: List[dict],
    orders_map: Dict[str, dict],
    barcodes: List[str],
    is_ozon: bool = False,
) -> Optional[FinanceChannel]:
    """Aggregate barcode-level finance dicts into a single FinanceChannel.

    fin_rows: list of dicts from get_wb_fin_data_by_barcode / get_ozon_fin_data_by_barcode
    orders_map: dict from get_wb_orders_by_barcode / get_ozon_orders_by_barcode
    barcodes: list of barcodes to filter on
    """
    barcode_set = set(str(b) for b in barcodes)

    # Filter and aggregate finance rows
    matched = [r for r in fin_rows if str(r.get("barcode", "")) in barcode_set]
    if not matched:
        return None

    # Aggregate numeric fields
    sales_count = int(sum(to_float(r.get("sales_count", 0)) for r in matched))
    rev_before = sum(to_float(r.get("revenue_before_spp", 0)) for r in matched)
    rev_after = sum(to_float(r.get("revenue_after_spp", 0)) for r in matched)
    margin_val = sum(to_float(r.get("margin", 0)) for r in matched)
    commission = sum(to_float(r.get("commission", 0)) for r in matched)
    logistics = sum(to_float(r.get("logistics", 0)) for r in matched)
    cost = sum(to_float(r.get("cost_of_goods", 0)) for r in matched)
    adv_int = sum(to_float(r.get("adv_internal", 0)) for r in matched)
    adv_ext = sum(to_float(r.get("adv_external", 0)) for r in matched)
    storage = sum(to_float(r.get("storage", 0)) for r in matched)
    nds = sum(to_float(r.get("nds", 0)) for r in matched)
    returns_rev = sum(to_float(r.get("returns_revenue", 0)) for r in matched)

    if is_ozon:
        returns_count_direct = int(sum(to_float(r.get("returns_count", 0)) for r in matched))
        penalty = 0.0
        retention = 0.0
        deduction = 0.0
    else:
        returns_count_direct = 0
        penalty = sum(to_float(r.get("penalty", 0)) for r in matched)
        retention = sum(to_float(r.get("retention", 0)) for r in matched)
        deduction = sum(to_float(r.get("deduction", 0)) for r in matched)

    # Orders from separate orders_map
    orders_count = 0
    orders_rub = 0.0
    for bc in barcode_set:
        om = orders_map.get(bc)
        if om:
            orders_count += int(to_float(om.get("orders_count", 0)))
            orders_rub += to_float(om.get("orders_rub", 0))

    margin_pct = (margin_val / rev_before * 100) if rev_before > 0 else 0
    avg_before = rev_before / sales_count if sales_count > 0 else 0
    avg_after = rev_after / sales_count if sales_count > 0 else 0
    spp_pct = (1 - rev_after / rev_before) * 100 if rev_before > 0 else 0
    buyout_pct = (sales_count / orders_count * 100) if orders_count > 0 else 0
    returns_count = returns_count_direct if returns_count_direct > 0 else max(0, orders_count - sales_count)
    returns_pct = (returns_count / orders_count * 100) if orders_count > 0 else 0

    total_adv = adv_int + adv_ext
    drr_total = (total_adv / orders_rub * 100) if orders_rub > 0 else 0
    drr_int = (adv_int / orders_rub * 100) if orders_rub > 0 else 0
    drr_ext = (adv_ext / orders_rub * 100) if orders_rub > 0 else 0

    def _expense(val):
        v = to_float(val)
        return ExpenseItem(value=v, pct=(v / rev_before * 100) if rev_before > 0 else 0)

    expenses = {
        "commission": _expense(commission),
        "logistics": _expense(logistics),
        "cost_price": _expense(cost),
        "advertising": _expense(total_adv),
        "storage": _expense(storage),
        "nds": _expense(nds),
        "other": _expense(penalty + retention + deduction),
    }

    return FinanceChannel(
        revenue_before_spp=rev_before, revenue_after_spp=rev_after,
        margin=margin_val, margin_pct=round(margin_pct, 1),
        orders_count=orders_count, orders_sum=orders_rub,
        sales_count=sales_count, sales_sum=rev_before,
        avg_check_before_spp=round(avg_before, 0), avg_check_after_spp=round(avg_after, 0),
        spp_pct=round(spp_pct, 1), buyout_pct=round(buyout_pct, 1),
        returns_count=returns_count, returns_pct=round(returns_pct, 1),
        expenses=expenses,
        drr=DRR(total=round(drr_total, 1), internal=round(drr_int, 1), external=round(drr_ext, 1)),
    )


class ExternalDataService:
    """Service for fetching external marketplace data for matrix entities."""

    @staticmethod
    def get_stock(entity_type: str, entity_id: int, period_days: int, db: Session) -> StockResponse:
        """Get stock/inventory data for a matrix entity."""
        key = resolve_marketplace_key(entity_type, entity_id, db)
        entity_name = _get_entity_name(entity_type, entity_id, db)

        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=period_days)).isoformat()

        wb_channel = None
        ozon_channel = None
        ms_stock = None

        if key.level == "model":
            wb_data = _get_cached_bulk("wb_turnover", start_date, end_date)
            ozon_data = _get_cached_bulk("ozon_turnover", start_date, end_date)
            ms_data = _get_cached_bulk("moysklad")

            wb_raw = wb_data.get(key.key)
            ozon_raw = ozon_data.get(key.key)
            ms_raw = ms_data.get(key.key)

            if wb_raw:
                wb_channel = StockChannel(
                    stock_mp=wb_raw["stock_mp"],
                    daily_sales=wb_raw["daily_sales"],
                    turnover_days=wb_raw["turnover_days"],
                    sales_count=wb_raw["sales_count"],
                    days_in_stock=wb_raw.get("days_in_stock", period_days),
                )
            if ozon_raw:
                ozon_channel = StockChannel(
                    stock_mp=ozon_raw["stock_mp"],
                    daily_sales=ozon_raw["daily_sales"],
                    turnover_days=ozon_raw["turnover_days"],
                    sales_count=ozon_raw["sales_count"],
                    days_in_stock=ozon_raw.get("days_in_stock", period_days),
                )
            if ms_raw:
                ms_stock = MoySkladStock(
                    stock_main=ms_raw["stock_main"],
                    stock_transit=ms_raw["stock_transit"],
                    total=ms_raw["total"],
                    snapshot_date=ms_raw.get("snapshot_date"),
                    is_stale=ms_raw.get("is_stale", False),
                )

        elif key.level == "article":
            wb_stock_data = _get_cached_bulk("wb_avg_stock", start_date, end_date)
            ozon_stock_data = _get_cached_bulk("ozon_avg_stock", start_date, end_date)
            ms_data = _get_cached_ms_article()

            wb_articles = _get_cached_bulk("wb_by_article", start_date, end_date)
            ozon_articles = _get_cached_bulk("ozon_by_article", start_date, end_date)

            wb_stock_val = to_float(wb_stock_data.get(key.key, 0))
            ozon_stock_val = to_float(ozon_stock_data.get(key.key, 0))
            ms_raw = ms_data.get(key.key)

            wb_article_data = next((a for a in wb_articles if a["article"] == key.key), None)
            ozon_article_data = next((a for a in ozon_articles if a["article"] == key.key), None)

            wb_sales_count = to_float(wb_article_data["sales_count"]) if wb_article_data else 0
            ozon_sales_count = to_float(ozon_article_data["sales_count"]) if ozon_article_data else 0
            wb_daily = (wb_sales_count / period_days) if wb_sales_count > 0 else 0
            ozon_daily = (ozon_sales_count / period_days) if ozon_sales_count > 0 else 0

            if wb_stock_val > 0 or wb_article_data:
                wb_channel = StockChannel(
                    stock_mp=wb_stock_val,
                    daily_sales=round(wb_daily, 1),
                    turnover_days=round(wb_stock_val / wb_daily, 1) if wb_daily > 0 else 0,
                    sales_count=int(wb_sales_count),
                    days_in_stock=period_days,
                )
            if ozon_stock_val > 0 or ozon_article_data:
                ozon_channel = StockChannel(
                    stock_mp=ozon_stock_val,
                    daily_sales=round(ozon_daily, 1),
                    turnover_days=round(ozon_stock_val / ozon_daily, 1) if ozon_daily > 0 else 0,
                    sales_count=int(ozon_sales_count),
                    days_in_stock=period_days,
                )
            if ms_raw:
                ms_stock = MoySkladStock(
                    stock_main=ms_raw["stock_main"],
                    stock_transit=ms_raw["stock_transit"],
                    total=ms_raw["total"],
                    snapshot_date=ms_raw.get("snapshot_date"),
                    is_stale=ms_raw.get("is_stale", False),
                )

        elif key.level in ("barcode", "barcode_list"):
            barcodes = key.keys if key.level == "barcode_list" else [key.key]
            fetch_wb = key.channel in (None, "wb")
            fetch_ozon = key.channel in (None, "ozon")

            wb_stock_map = _get_wb_barcode_stock(barcodes) if fetch_wb else {}
            ozon_stock_map = _get_ozon_barcode_stock(barcodes) if fetch_ozon else {}
            wb_sales_map = _get_wb_barcode_daily_sales(barcodes, start_date, end_date) if fetch_wb else {}
            ozon_sales_map = _get_ozon_barcode_daily_sales(barcodes, start_date, end_date) if fetch_ozon else {}

            wb_stock_total = sum(wb_stock_map.get(str(b), 0) for b in barcodes)
            ozon_stock_total = sum(ozon_stock_map.get(str(b), 0) for b in barcodes)
            wb_sales_total = sum(wb_sales_map.get(str(b), 0) for b in barcodes)
            ozon_sales_total = sum(ozon_sales_map.get(str(b), 0) for b in barcodes)

            wb_daily = (wb_sales_total / period_days) if wb_sales_total > 0 else 0
            ozon_daily = (ozon_sales_total / period_days) if ozon_sales_total > 0 else 0

            if fetch_wb and (wb_stock_total > 0 or wb_sales_total > 0):
                wb_channel = StockChannel(
                    stock_mp=wb_stock_total,
                    daily_sales=round(wb_daily, 1),
                    turnover_days=round(wb_stock_total / wb_daily, 1) if wb_daily > 0 else 0,
                    sales_count=int(wb_sales_total),
                    days_in_stock=period_days,
                )
            if fetch_ozon and (ozon_stock_total > 0 or ozon_sales_total > 0):
                ozon_channel = StockChannel(
                    stock_mp=ozon_stock_total,
                    daily_sales=round(ozon_daily, 1),
                    turnover_days=round(ozon_stock_total / ozon_daily, 1) if ozon_daily > 0 else 0,
                    sales_count=int(ozon_sales_total),
                    days_in_stock=period_days,
                )
            # MoySklad not available at barcode level

        total = (
            (wb_channel.stock_mp if wb_channel else 0)
            + (ozon_channel.stock_mp if ozon_channel else 0)
            + (ms_stock.total if ms_stock else 0)
        )

        # Weighted turnover
        total_daily = (
            (wb_channel.daily_sales if wb_channel else 0)
            + (ozon_channel.daily_sales if ozon_channel else 0)
        )
        total_turnover = (total / total_daily) if total_daily > 0 else None

        return StockResponse(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            period_days=period_days,
            wb=wb_channel,
            ozon=ozon_channel,
            moysklad=ms_stock,
            total_stock=total,
            total_turnover_days=round(total_turnover, 1) if total_turnover else None,
        )

    @staticmethod
    def get_finance(entity_type: str, entity_id: int, period_days: int,
                    compare: str, db: Session) -> FinanceResponse:
        """Get unit-economics data for a matrix entity."""
        key = resolve_marketplace_key(entity_type, entity_id, db)
        entity_name = _get_entity_name(entity_type, entity_id, db)
        current_start, prev_start, current_end, compare_end = _calc_dates(period_days, compare)

        wb_channel = None
        ozon_channel = None
        delta_wb = None
        delta_ozon = None

        if key.level == "model":
            # WB
            wb_sales, wb_orders = _get_full_wb_finance(current_start, prev_start, current_end, key.key)
            wb_current_sales = next((r for r in wb_sales if r[0] == "current"), None)
            wb_prev_sales = next((r for r in wb_sales if r[0] == "previous"), None)
            wb_current_orders = next((r for r in wb_orders if r[0] == "current"), None)
            wb_prev_orders = next((r for r in wb_orders if r[0] == "previous"), None)

            wb_channel = _build_finance_channel(wb_current_sales, wb_current_orders)

            if compare != "none" and wb_prev_sales and wb_channel:
                wb_prev_channel = _build_finance_channel(wb_prev_sales, wb_prev_orders)
                if wb_prev_channel:
                    delta_wb = _build_delta(wb_channel, wb_prev_channel)
                    _fill_expense_deltas(wb_channel, wb_prev_channel)

            # Ozon (same pattern)
            oz_sales, oz_orders = _get_full_ozon_finance(current_start, prev_start, current_end, key.key)
            oz_current_sales = next((r for r in oz_sales if r[0] == "current"), None)
            oz_prev_sales = next((r for r in oz_sales if r[0] == "previous"), None)
            oz_current_orders = next((r for r in oz_orders if r[0] == "current"), None)
            oz_prev_orders = next((r for r in oz_orders if r[0] == "previous"), None)

            ozon_channel = _build_finance_channel(oz_current_sales, oz_current_orders)

            if compare != "none" and oz_prev_sales and ozon_channel:
                oz_prev_channel = _build_finance_channel(oz_prev_sales, oz_prev_orders)
                if oz_prev_channel:
                    delta_ozon = _build_delta(ozon_channel, oz_prev_channel)
                    _fill_expense_deltas(ozon_channel, oz_prev_channel)

        elif key.level == "article":
            # WB article-level
            wb_sales, wb_orders = _get_article_wb_finance(
                current_start, prev_start, current_end, key.key)
            wb_current_sales = next((r for r in wb_sales if r[0] == "current"), None)
            wb_prev_sales = next((r for r in wb_sales if r[0] == "previous"), None)
            wb_current_orders = next((r for r in wb_orders if r[0] == "current"), None)
            wb_prev_orders = next((r for r in wb_orders if r[0] == "previous"), None)

            wb_channel = _build_finance_channel(wb_current_sales, wb_current_orders)

            if compare != "none" and wb_prev_sales and wb_channel:
                wb_prev_channel = _build_finance_channel(wb_prev_sales, wb_prev_orders)
                if wb_prev_channel:
                    delta_wb = _build_delta(wb_channel, wb_prev_channel)
                    _fill_expense_deltas(wb_channel, wb_prev_channel)

            # Ozon article-level
            oz_sales, oz_orders = _get_article_ozon_finance(
                current_start, prev_start, current_end, key.key)
            oz_current_sales = next((r for r in oz_sales if r[0] == "current"), None)
            oz_prev_sales = next((r for r in oz_sales if r[0] == "previous"), None)
            oz_current_orders = next((r for r in oz_orders if r[0] == "current"), None)
            oz_prev_orders = next((r for r in oz_orders if r[0] == "previous"), None)

            ozon_channel = _build_finance_channel(oz_current_sales, oz_current_orders)

            if compare != "none" and oz_prev_sales and ozon_channel:
                oz_prev_channel = _build_finance_channel(oz_prev_sales, oz_prev_orders)
                if oz_prev_channel:
                    delta_ozon = _build_delta(ozon_channel, oz_prev_channel)
                    _fill_expense_deltas(ozon_channel, oz_prev_channel)

        elif key.level in ("barcode", "barcode_list"):
            barcodes = key.keys if key.level == "barcode_list" else [key.key]
            fetch_wb = key.channel in (None, "wb")
            fetch_ozon = key.channel in (None, "ozon")

            if fetch_wb:
                wb_fin_rows = _get_cached_bulk("wb_fin_barcode", current_start, current_end)
                wb_orders_map = _get_cached_bulk("wb_orders_barcode", current_start, current_end)
                wb_channel = _build_finance_channel_from_barcode_dicts(
                    wb_fin_rows, wb_orders_map, barcodes, is_ozon=False)

                if compare != "none" and wb_channel:
                    wb_fin_prev = _get_cached_bulk("wb_fin_barcode", prev_start, current_start)
                    wb_orders_prev = _get_cached_bulk("wb_orders_barcode", prev_start, current_start)
                    wb_prev_channel = _build_finance_channel_from_barcode_dicts(
                        wb_fin_prev, wb_orders_prev, barcodes, is_ozon=False)
                    if wb_prev_channel:
                        delta_wb = _build_delta(wb_channel, wb_prev_channel)
                        _fill_expense_deltas(wb_channel, wb_prev_channel)

            if fetch_ozon:
                oz_fin_rows = _get_cached_bulk("ozon_fin_barcode", current_start, current_end)
                oz_orders_map = _get_cached_bulk("ozon_orders_barcode", current_start, current_end)
                ozon_channel = _build_finance_channel_from_barcode_dicts(
                    oz_fin_rows, oz_orders_map, barcodes, is_ozon=True)

                if compare != "none" and ozon_channel:
                    oz_fin_prev = _get_cached_bulk("ozon_fin_barcode", prev_start, current_start)
                    oz_orders_prev = _get_cached_bulk("ozon_orders_barcode", prev_start, current_start)
                    oz_prev_channel = _build_finance_channel_from_barcode_dicts(
                        oz_fin_prev, oz_orders_prev, barcodes, is_ozon=True)
                    if oz_prev_channel:
                        delta_ozon = _build_delta(ozon_channel, oz_prev_channel)
                        _fill_expense_deltas(ozon_channel, oz_prev_channel)

        return FinanceResponse(
            entity_type=entity_type, entity_id=entity_id, entity_name=entity_name,
            period_start=current_start, period_end=current_end,
            compare_period_start=prev_start if compare != "none" else None,
            compare_period_end=compare_end,
            wb=wb_channel, ozon=ozon_channel,
            delta_wb=delta_wb, delta_ozon=delta_ozon,
        )


def _fill_expense_deltas(current_ch: FinanceChannel, prev_ch: FinanceChannel) -> None:
    """Fill expense delta_value / delta_pct on the current channel in-place."""
    for exp_key in current_ch.expenses:
        if exp_key in prev_ch.expenses:
            current_ch.expenses[exp_key].delta_value = round(
                current_ch.expenses[exp_key].value - prev_ch.expenses[exp_key].value, 0)
            current_ch.expenses[exp_key].delta_pct = round(
                current_ch.expenses[exp_key].pct - prev_ch.expenses[exp_key].pct, 1)


def _get_full_wb_finance(current_start: str, prev_start: str, current_end: str, model_key: str):
    """Full WB unit-economics for a single model. Two SQL queries."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    try:
        cur.execute(f"""
        SELECT
            CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
            SUM(full_counts) as sales_count,
            SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
            SUM(revenue) - COALESCE(SUM(revenue_return), 0) as revenue_after_spp,
            SUM(reclama) as adv_internal,
            SUM(reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_external,
            SUM(sebes) as cost_of_goods,
            SUM(logist) as logistics,
            SUM(storage) as storage,
            SUM(comis_spp) as commission,
            SUM(spp) as spp_amount,
            SUM(nds) as nds,
            SUM(penalty) as penalty,
            SUM(retention) as retention,
            SUM(deduction) as deduction,
            {WB_MARGIN_SQL} as margin,
            COALESCE(SUM(revenue_return_spp), 0) as returns_revenue,
            0 as returns_count_direct
        FROM abc_date
        WHERE date >= %s AND date < %s
          AND {get_osnova_sql("SPLIT_PART(article, '/', 1)")} = %s
        GROUP BY 1
        ORDER BY period DESC;
        """, (current_start, prev_start, current_end, model_key))
        sales_data = cur.fetchall()

        cur.execute(f"""
        SELECT
            CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
            COUNT(*) as orders_count,
            SUM(pricewithdisc) as orders_rub
        FROM orders
        WHERE date >= %s AND date < %s
          AND {get_osnova_sql("SPLIT_PART(supplierarticle, '/', 1)")} = %s
        GROUP BY 1
        ORDER BY period DESC;
        """, (current_start, prev_start, current_end, model_key))
        orders_data = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return sales_data, orders_data


def _get_full_ozon_finance(current_start: str, prev_start: str, current_end: str, model_key: str):
    """Full Ozon unit-economics for a single model. Two SQL queries."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    try:
        cur.execute(f"""
        SELECT
            CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
            SUM(count_end) as sales_count,
            SUM(price_end) as revenue_before_spp,
            SUM(price_end_spp) as revenue_after_spp,
            SUM(reclama_end) as adv_internal,
            SUM(adv_vn) as adv_external,
            SUM(sebes_end) as cost_of_goods,
            SUM(logist_end) as logistics,
            SUM(storage_end) as storage,
            SUM(comission_end) as commission,
            SUM(spp) as spp_amount,
            SUM(nds) as nds,
            0 as penalty, 0 as retention, 0 as deduction,
            SUM(marga) - SUM(nds) as margin,
            0 as returns_revenue,
            COALESCE(SUM(count_return), 0) as returns_count_direct
        FROM abc_date
        WHERE date >= %s AND date < %s
          AND {get_osnova_sql("SPLIT_PART(article, '/', 1)")} = %s
        GROUP BY 1
        ORDER BY period DESC;
        """, (current_start, prev_start, current_end, model_key))
        sales_data = cur.fetchall()

        cur.execute(f"""
        SELECT
            CASE WHEN in_process_at::date >= %s THEN 'current' ELSE 'previous' END as period,
            COUNT(*) as orders_count,
            SUM(price) as orders_rub
        FROM orders
        WHERE in_process_at::date >= %s AND in_process_at::date < %s
          AND {get_osnova_sql("SPLIT_PART(offer_id, '/', 1)")} = %s
        GROUP BY 1
        ORDER BY period DESC;
        """, (current_start, prev_start, current_end, model_key))
        orders_data = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return sales_data, orders_data


def _build_finance_channel(sales_row, orders_row) -> Optional[FinanceChannel]:
    """Build FinanceChannel from raw SQL row tuples."""
    if not sales_row:
        return None

    # Unpack sales: (period, sales_count, rev_before, rev_after, adv_int, adv_ext, cost, logistics, storage, commission, spp, nds, penalty, retention, deduction, margin, returns_rev, returns_count_direct)
    (_, sales_count, rev_before, rev_after, adv_int, adv_ext, cost,
     logistics, storage, commission, spp, nds, penalty, retention,
     deduction, margin, returns_rev, returns_count_direct) = sales_row

    sales_count = int(to_float(sales_count))
    rev_before = to_float(rev_before)
    rev_after = to_float(rev_after)
    margin_val = to_float(margin)

    orders_count = int(to_float(orders_row[1])) if orders_row else 0
    orders_rub = to_float(orders_row[2]) if orders_row else 0

    margin_pct = (margin_val / rev_before * 100) if rev_before > 0 else 0
    avg_before = rev_before / sales_count if sales_count > 0 else 0
    avg_after = rev_after / sales_count if sales_count > 0 else 0
    spp_pct = (1 - rev_after / rev_before) * 100 if rev_before > 0 else 0
    buyout_pct = (sales_count / orders_count * 100) if orders_count > 0 else 0
    direct_returns = int(to_float(returns_count_direct))
    returns_count = direct_returns if direct_returns > 0 else max(0, orders_count - sales_count)
    returns_pct = (returns_count / orders_count * 100) if orders_count > 0 else 0

    total_adv = to_float(adv_int) + to_float(adv_ext)
    drr_total = (total_adv / orders_rub * 100) if orders_rub > 0 else 0
    drr_int = (to_float(adv_int) / orders_rub * 100) if orders_rub > 0 else 0
    drr_ext = (to_float(adv_ext) / orders_rub * 100) if orders_rub > 0 else 0

    def _expense(val):
        v = to_float(val)
        return ExpenseItem(value=v, pct=(v / rev_before * 100) if rev_before > 0 else 0)

    expenses = {
        "commission": _expense(commission),
        "logistics": _expense(logistics),
        "cost_price": _expense(cost),
        "advertising": _expense(total_adv),
        "storage": _expense(storage),
        "nds": _expense(nds),
        "other": _expense(to_float(penalty) + to_float(retention) + to_float(deduction)),
    }

    return FinanceChannel(
        revenue_before_spp=rev_before, revenue_after_spp=rev_after,
        margin=margin_val, margin_pct=round(margin_pct, 1),
        orders_count=orders_count, orders_sum=orders_rub,
        sales_count=sales_count, sales_sum=rev_before,
        avg_check_before_spp=round(avg_before, 0), avg_check_after_spp=round(avg_after, 0),
        spp_pct=round(spp_pct, 1), buyout_pct=round(buyout_pct, 1),
        returns_count=returns_count, returns_pct=round(returns_pct, 1),
        expenses=expenses, drr=DRR(total=round(drr_total, 1), internal=round(drr_int, 1), external=round(drr_ext, 1)),
    )


def _build_delta(current: FinanceChannel, previous: FinanceChannel) -> FinanceDelta:
    """Compute delta between current and previous period."""
    return FinanceDelta(
        revenue_before_spp=current.revenue_before_spp - previous.revenue_before_spp,
        revenue_after_spp=current.revenue_after_spp - previous.revenue_after_spp,
        margin=current.margin - previous.margin,
        margin_pct=round(current.margin_pct - previous.margin_pct, 1),
        orders_count=current.orders_count - previous.orders_count,
        orders_sum=current.orders_sum - previous.orders_sum,
        sales_count=current.sales_count - previous.sales_count,
        avg_check_before_spp=round(current.avg_check_before_spp - previous.avg_check_before_spp, 0),
        avg_check_after_spp=round(current.avg_check_after_spp - previous.avg_check_after_spp, 0),
        spp_pct=round(current.spp_pct - previous.spp_pct, 1),
        buyout_pct=round(current.buyout_pct - previous.buyout_pct, 1),
        returns_count=current.returns_count - previous.returns_count,
        returns_pct=round(current.returns_pct - previous.returns_pct, 1),
        drr_total=round(current.drr.total - previous.drr.total, 1),
        drr_internal=round(current.drr.internal - previous.drr.internal, 1),
        drr_external=round(current.drr.external - previous.drr.external, 1),
    )


def _get_entity_name(entity_type: str, entity_id: int, db: Session) -> str:
    """Get display name for an entity."""
    model_map = {
        "models_osnova": (ModelOsnova, "kod"),
        "models": (Model, "kod"),
        "articles": (Artikul, "artikul"),
        "products": (Tovar, "barkod"),
        "cards_wb": (SleykaWB, "nazvanie"),
        "cards_ozon": (SleykaOzon, "nazvanie"),
    }
    cls, attr = model_map[entity_type]
    record = db.get(cls, entity_id)
    return getattr(record, attr, f"#{entity_id}") if record else f"#{entity_id}"
