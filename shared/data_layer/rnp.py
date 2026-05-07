"""РНП (Рука на Пульсе) — data layer: WB PostgreSQL queries + week aggregation."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from shared.data_layer._connection import _get_wb_connection, _get_supabase_connection

logger = logging.getLogger(__name__)

__all__ = [
    "fetch_rnp_wb_daily",
    "fetch_rnp_models_wb",
    "resolve_wb_key",
    "fetch_rnp_sheets_digital",
    "fetch_rnp_sheets_bloggers",
    "aggregate_to_weeks",
    "_safe_div",
    "_week_start",
    "_detect_phase",
]

# Type alias for model list items
RnpModel = dict  # {"label": str, "value": str}


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _week_start(d: date) -> date:
    """Return Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


def _detect_phase(margin_pct: Optional[float]) -> str:
    if margin_pct is None:
        return "recovery"
    if margin_pct >= 15:
        return "norm"
    if margin_pct < 10:
        return "decline"
    return "recovery"


def fetch_rnp_models_wb() -> list[dict]:
    """List of active WB models from Supabase `modeli` table.

    Returns only models with statuses: "Продается" (8), "Выводим" (9), "Запуск" (14).
    Skips models where artikul_modeli IS NULL.
    Models sharing the same WB article prefix are collapsed — MIN(kod) is the label.

    Returns list of dicts: [{"label": str, "value": str}, ...]
    where value = LOWER(MIN(kod)) — the display-name key used throughout the API.
    The actual WB article prefix (which may differ, e.g. "компбел-ж-бесшов" for Vuki)
    is resolved internally via resolve_wb_key() when querying the WB database.
    """
    conn = _get_supabase_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    MIN(kod)       AS label,
                    LOWER(MIN(kod)) AS display_key
                FROM modeli
                WHERE artikul_modeli IS NOT NULL
                  AND status_id IN (8, 9, 14)
                GROUP BY LOWER(SPLIT_PART(artikul_modeli, '/', 1))
                ORDER BY LOWER(MIN(kod))
            """)
            return [{"label": row[0], "value": row[1]} for row in cur.fetchall()]
    finally:
        conn.close()


def resolve_wb_key(display_model: str) -> str:
    """Map a display model key (LOWER(MIN(kod))) to the WB article prefix.

    For most models, display key = WB key (e.g. "wendy" → "wendy").
    For legacy Vuki, "vuki" → "компбел-ж-бесшов".
    Falls back to returning display_model unchanged if no match found.
    """
    conn = _get_supabase_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT LOWER(SPLIT_PART(artikul_modeli, '/', 1)) AS wb_key
                FROM modeli
                WHERE artikul_modeli IS NOT NULL
                  AND status_id IN (8, 9, 14)
                GROUP BY wb_key
                HAVING LOWER(MIN(kod)) = %s
            """, (display_model,))
            row = cur.fetchone()
            return row[0] if row else display_model
    finally:
        conn.close()


def fetch_rnp_wb_daily(
    model: str,
    date_from: date,
    date_to: date,
) -> list[dict]:
    """
    Fetch daily WB data for one model across 4 tables.
    Returns list of dicts keyed by date; missing days from any table → None fields.
    """
    m = model.lower()
    conn = _get_wb_connection()
    try:
        with conn.cursor() as cur:
            # ── abc_date: orders, sales, adv_internal, margin ──────────────────
            cur.execute("""
                SELECT
                    date::date AS dt,
                    SUM(count_orders)                                       AS orders_qty,
                    SUM(full_counts - returns)                              AS sales_qty,
                    SUM(revenue_spp - COALESCE(revenue_return_spp, 0))     AS sales_rub,
                    SUM(reclama)                                            AS adv_internal_rub,
                    SUM(
                        marga - nds - reclama_vn
                        - COALESCE(reclama_vn_vk, 0)
                        - COALESCE(reclama_vn_creators, 0)
                    )                                                       AS margin_rub
                FROM abc_date
                WHERE LOWER(SPLIT_PART(article, '/', 1)) = %s
                  AND date::date BETWEEN %s AND %s
                GROUP BY 1
            """, (m, date_from, date_to))
            abc = {r[0]: r for r in cur.fetchall()}

            # ── orders: orders_rub, orders_spp_rub ─────────────────────────────
            cur.execute("""
                SELECT
                    date::date           AS dt,
                    SUM(pricewithdisc)   AS orders_rub,
                    SUM(finishedprice)   AS orders_spp_rub
                FROM orders
                WHERE LOWER(SPLIT_PART(supplierarticle, '/', 1)) = %s
                  AND date::date BETWEEN %s AND %s
                GROUP BY 1
            """, (m, date_from, date_to))
            ord_ = {r[0]: r for r in cur.fetchall()}

            # ── content_analysis: full funnel (clicks, carts, orders, buyouts) ─
            # Источник истины для воронки и CR. orders/buyouts здесь — funnel-level
            # (отличаются от abc_date.count_orders, который финансовый).
            cur.execute("""
                SELECT
                    date::date              AS dt,
                    SUM(opencardcount)      AS clicks_total,
                    SUM(addtocartcount)     AS cart_total,
                    SUM(orderscount)        AS funnel_orders_qty,
                    SUM(buyoutscount)       AS funnel_buyouts_qty
                FROM content_analysis
                WHERE LOWER(SPLIT_PART(vendorcode, '/', 1)) = %s
                  AND date::date BETWEEN %s AND %s
                  AND brandname = 'Wookiee'
                GROUP BY 1
            """, (m, date_from, date_to))
            ca = {r[0]: r for r in cur.fetchall()}

            # ── wb_adv: internal ad views/clicks/orders ────────────────────────
            # nmid→model resolved via `nomenclature` table (confirmed pattern from advertising.py)
            cur.execute("""
                SELECT
                    wa.date::date   AS dt,
                    SUM(wa.views)   AS adv_views,
                    SUM(wa.clicks)  AS adv_clicks,
                    SUM(wa.orders)  AS adv_orders
                FROM wb_adv wa
                JOIN (SELECT DISTINCT nmid, vendorcode FROM nomenclature) n
                  ON wa.nmid = n.nmid
                WHERE LOWER(SPLIT_PART(n.vendorcode, '/', 1)) = %s
                  AND wa.date::date BETWEEN %s AND %s
                GROUP BY 1
            """, (m, date_from, date_to))
            adv = {r[0]: r for r in cur.fetchall()}

    finally:
        conn.close()

    def _f(v) -> Optional[float]:
        return float(v) if v is not None else None

    all_dates = sorted(set(abc) | set(ord_) | set(ca) | set(adv))
    result = []
    for dt in all_dates:
        a = abc.get(dt, (None,) * 6)
        o = ord_.get(dt, (None,) * 3)
        c = ca.get(dt, (None,) * 5)
        w = adv.get(dt, (None,) * 4)
        result.append({
            "date": dt,
            "orders_qty":         _f(a[1]),
            "sales_qty":          _f(a[2]),
            "sales_rub":          _f(a[3]),
            "adv_internal_rub":   _f(a[4]),
            "margin_rub":         _f(a[5]),
            "orders_rub":         _f(o[1]),
            "orders_spp_rub":     _f(o[2]),
            "clicks_total":       _f(c[1]),
            "cart_total":         _f(c[2]),
            "funnel_orders_qty":  _f(c[3]),
            "funnel_buyouts_qty": _f(c[4]),
            "adv_views":          _f(w[1]),
            "adv_clicks":         _f(w[2]),
            "adv_orders":         _f(w[3]),
        })
    return result


def _parse_sheet_date(raw: str) -> Optional[date]:
    """Parse DD.MM.YYYY or YYYY-MM-DD sheet date strings."""
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _to_float(raw) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        import re
        s = str(raw).replace("\xa0", "").replace(" ", "")
        # Strip leading currency symbols/prefixes ("р.", "₽", "$")
        s = re.sub(r'^[^\d\-]+', '', s)
        return float(s.replace(",", "."))
    except (ValueError, TypeError):
        return None


def fetch_rnp_sheets_digital(
    date_from: date,
    date_to: date,
    model: str,
    sa_file: str,
    spreadsheet_id: str,
) -> dict[str, dict]:
    """
    Read ADS/ADB/EPS sheets from the external-ads spreadsheet.
    Returns dict keyed by ISO week_start string; values accumulate channel spend/views/clicks/orders.

    Column layout (confirmed for ADS, assumed identical for ADB/EPS):
      0=Дата, 1=Артикул, 2=Товар (model filter), 3=Цвет,
      4=Spend(E), 5=Views(F), 6=Clicks(G), 11=Orders(L)
    """
    from shared.clients.sheets_client import get_client

    SHEET_TO_PREFIX = {
        "Отчет ADS ежедневный": "vk_sids",
        "Отчет ADB ежедневный": "sids_contractor",
        "Отчет EPS ежедневный": "yandex_contractor",
    }
    COL = {"date": 0, "model": 2, "spend": 4, "views": 5, "clicks": 6, "orders": 11}

    weekly: dict[str, dict] = {}
    try:
        gc = get_client(sa_file)
        ss = gc.open_by_key(spreadsheet_id)
    except Exception as exc:
        logger.warning("Sheets digital: failed to open spreadsheet: %s", exc)
        return weekly

    for sheet_name, prefix in SHEET_TO_PREFIX.items():
        try:
            ws = ss.worksheet(sheet_name)
            rows = ws.get_all_values()
        except Exception as exc:
            logger.warning("Sheets digital: sheet '%s' unavailable: %s", sheet_name, exc)
            continue

        for row in rows[1:]:  # skip header row
            if len(row) <= COL["orders"]:
                continue
            row_date = _parse_sheet_date(row[COL["date"]])
            if row_date is None or not (date_from <= row_date <= date_to):
                continue
            if row[COL["model"]].lower().strip() != model.lower():
                continue

            wk = _week_start(row_date).isoformat()
            if wk not in weekly:
                weekly[wk] = {}
            b = weekly[wk]

            for field, col_idx in [
                (f"{prefix}_rub",    COL["spend"]),
                (f"{prefix}_views",  COL["views"]),
                (f"{prefix}_clicks", COL["clicks"]),
                (f"{prefix}_orders", COL["orders"]),
            ]:
                val = _to_float(row[col_idx])
                if val is not None:
                    b[field] = b.get(field, 0.0) + val

    return weekly


def fetch_rnp_sheets_bloggers(
    date_from: date,
    date_to: date,
    model: str,
    sa_file: str,
    spreadsheet_id: str,
    sheet_name: str = "Блогеры",
) -> dict[str, dict]:
    """
    Read the Bloggers sheet. Returns dict keyed by ISO week_start.
    Column layout (from GAS script):
      5=Дата кампании, 6=Модель, 13=Бюджет,
      23=Просмотры, 25=Клики, 28=Корзины, 30=Заказы

    # TODO: RNP_BLOGGERS_SHEET_ID — уточнить у Артёма (пока env var пустой,
    # функция возвращает {} при отсутствующем spreadsheet_id в app.py)
    """
    from shared.clients.sheets_client import get_client

    COL = {
        "date": 5, "model": 6, "spend": 13,
        "views": 23, "clicks": 25, "carts": 28, "orders": 30,
    }
    weekly: dict[str, dict] = {}
    try:
        gc = get_client(sa_file)
        ws = gc.open_by_key(spreadsheet_id).worksheet(sheet_name)
        rows = ws.get_all_values()
    except Exception as exc:
        logger.warning("Sheets bloggers: unavailable: %s", exc)
        return weekly

    for row in rows[1:]:
        max_col = max(COL.values())
        if len(row) <= max_col:
            continue
        row_date = _parse_sheet_date(row[COL["date"]])
        if row_date is None or not (date_from <= row_date <= date_to):
            continue
        if row[COL["model"]].lower().strip() != model.lower():
            continue

        wk = _week_start(row_date).isoformat()
        b = weekly.setdefault(wk, {})

        spend = _to_float(row[COL["spend"]]) or 0.0
        b["blogger_rub"] = b.get("blogger_rub", 0.0) + spend

        has_stats = False
        for field, col_idx in [
            ("blogger_views", COL["views"]),
            ("blogger_clicks", COL["clicks"]),
            ("blogger_carts", COL["carts"]),
            ("blogger_orders", COL["orders"]),
        ]:
            val = _to_float(row[col_idx])
            if val is not None:
                b[field] = b.get(field, 0.0) + val
                has_stats = True

        # no_stats = budget exists but all stats columns empty
        if spend > 0 and not has_stats:
            b["blogger_no_stats"] = b.get("blogger_no_stats", True)
        else:
            b["blogger_no_stats"] = False

    return weekly


def aggregate_to_weeks(
    daily_rows: list[dict],
    sheets_data: dict,
    buyout_forecast: Optional[float] = None,
) -> list[dict]:
    """
    Aggregate daily WB rows into weekly buckets and compute all derived metrics.

    sheets_data: dict keyed by ISO week_start string, values are per-channel dicts
                 with keys like blogger_rub, vk_sids_rub, etc.
    buyout_forecast: override buyout %; defaults to period-average sales_qty/orders_qty
    """
    if not daily_rows:
        return []

    # Compute period-level buyout for default forecast
    if buyout_forecast is None:
        tot_orders = sum(r["orders_qty"] or 0 for r in daily_rows)
        tot_sales = sum(r["sales_qty"] or 0 for r in daily_rows)
        buyout_forecast = _safe_div(tot_sales, tot_orders) or 0.87

    # Group days by week_start (Monday)
    buckets: dict[date, list[dict]] = {}
    for row in daily_rows:
        ws = _week_start(row["date"])
        buckets.setdefault(ws, []).append(row)

    result = []
    for week_start, rows in sorted(buckets.items()):
        week_end = week_start + timedelta(days=6)
        wkey = week_start.isoformat()

        # ── DB aggregations ──────────────────────────────────────────────────
        def db_sum(field: str) -> float:
            return sum(r[field] or 0 for r in rows)

        orders_qty          = db_sum("orders_qty")           # abc_date — финансы
        sales_qty           = db_sum("sales_qty")
        sales_rub           = db_sum("sales_rub")
        adv_internal_rub    = db_sum("adv_internal_rub")
        margin_rub          = db_sum("margin_rub")
        orders_rub          = db_sum("orders_rub")
        orders_spp_rub      = db_sum("orders_spp_rub")
        clicks_total        = db_sum("clicks_total")
        cart_total          = db_sum("cart_total")
        funnel_orders_qty   = db_sum("funnel_orders_qty")    # CA — воронка
        funnel_buyouts_qty  = db_sum("funnel_buyouts_qty")   # CA — воронка
        adv_views           = db_sum("adv_views")
        adv_clicks          = db_sum("adv_clicks")
        orders_internal_qty = db_sum("adv_orders")

        # ── Sheets aggregations ──────────────────────────────────────────────
        sh = sheets_data.get(wkey, {})

        def sh_val(key: str) -> Optional[float]:
            v = sh.get(key)
            return float(v) if v else None

        blogger_rub      = sh_val("blogger_rub") or 0.0
        blogger_views    = sh_val("blogger_views")
        blogger_clicks   = sh_val("blogger_clicks")
        blogger_carts    = sh_val("blogger_carts")
        blogger_orders   = sh_val("blogger_orders")
        blogger_no_stats = bool(sh.get("blogger_no_stats", False))

        vk_sids_rub     = sh_val("vk_sids_rub") or 0.0
        vk_sids_views   = sh_val("vk_sids_views")
        vk_sids_clicks  = sh_val("vk_sids_clicks")
        vk_sids_orders  = sh_val("vk_sids_orders")

        sids_c_rub      = sh_val("sids_contractor_rub") or 0.0
        sids_c_views    = sh_val("sids_contractor_views")
        sids_c_clicks   = sh_val("sids_contractor_clicks")
        sids_c_orders   = sh_val("sids_contractor_orders")

        ya_rub          = sh_val("yandex_contractor_rub") or 0.0
        ya_views        = sh_val("yandex_contractor_views")
        ya_clicks       = sh_val("yandex_contractor_clicks")
        ya_orders       = sh_val("yandex_contractor_orders")

        # ── Derived ──────────────────────────────────────────────────────────
        adv_external_rub = blogger_rub + vk_sids_rub + sids_c_rub + ya_rub
        adv_total_rub    = adv_internal_rub + adv_external_rub

        margin_before_ads_rub = margin_rub + adv_total_rub
        # TODO: проверить формулу с Артёмом — возможно reclama_vn* уже включают Sheets-каналы.
        # Если да, то adv_total_rub = только adv_internal_rub (reclama_vn* = Sheets-расходы).
        margin_before_ads_pct = _safe_div(margin_before_ads_rub * 100, sales_rub)
        margin_pct            = _safe_div(margin_rub * 100, sales_rub)
        margin_ratio          = _safe_div(margin_before_ads_rub, sales_rub)  # as 0–1

        orders_organic_qty = max(0, orders_qty - orders_internal_qty)
        avg_order_rub      = _safe_div(orders_rub, orders_qty)

        # Internal ad profit forecast
        adv_orders_rub = orders_internal_qty * (avg_order_rub or 0)
        adv_sales_rub  = adv_orders_rub * buyout_forecast
        adv_int_profit = (
            adv_sales_rub * margin_ratio - adv_internal_rub
            if margin_ratio is not None else None
        )

        # Blogger profit forecast
        if blogger_orders and avg_order_rub and margin_ratio is not None and not blogger_no_stats:
            bl_orders_rub   = blogger_orders * avg_order_rub
            bl_sales_rub    = bl_orders_rub * buyout_forecast
            blogger_profit  = bl_sales_rub * margin_ratio - blogger_rub
        else:
            blogger_profit = None

        # Sales + margin forecast
        sales_fc_rub  = orders_rub * buyout_forecast if orders_rub else None
        margin_fc_rub = (
            sales_fc_rub * margin_ratio - adv_total_rub
            if sales_fc_rub and margin_ratio is not None else None
        )

        # Ext totals (sum non-None)
        def _ext_sum(*vals: Optional[float]) -> Optional[float]:
            total = sum(v for v in vals if v is not None)
            return total if total > 0 else None

        ext_views  = _ext_sum(blogger_views, vk_sids_views, sids_c_views, ya_views)
        ext_clicks = _ext_sum(blogger_clicks, vk_sids_clicks, sids_c_clicks, ya_clicks)

        result.append({
            "week_start": wkey,
            "week_end":   week_end.isoformat(),
            "week_label": f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m')}",
            "phase":      _detect_phase(margin_pct),
            # Заказы
            "orders_qty":        orders_qty or None,
            "orders_rub":        orders_rub or None,
            "orders_spp_rub":    orders_spp_rub or None,
            "avg_order_rub":     avg_order_rub,
            "avg_order_spp_rub": _safe_div(orders_spp_rub, orders_qty),
            "spp_pct": _safe_div((orders_rub - orders_spp_rub) * 100, orders_rub) if orders_rub else None,
            # Продажи
            "sales_qty":    sales_qty or None,
            "buyout_pct":   _safe_div(sales_qty * 100, orders_qty),
            "sales_rub":    sales_rub or None,
            "avg_sale_rub": _safe_div(sales_rub, sales_qty),
            # Воронка (все CR — intra-source: content_analysis only)
            "clicks_total":       clicks_total or None,
            "cart_total":         cart_total or None,
            "funnel_orders_qty":  funnel_orders_qty or None,
            "funnel_buyouts_qty": funnel_buyouts_qty or None,
            "cr_card_to_cart":    _safe_div(cart_total * 100, clicks_total),
            "cr_cart_to_order":   _safe_div(funnel_orders_qty * 100, cart_total),
            "cr_total":           _safe_div(funnel_orders_qty * 100, clicks_total),
            # Реклама итого
            "adv_total_rub":           adv_total_rub or None,
            "drr_total_from_sales":    _safe_div(adv_total_rub * 100, sales_rub),
            "drr_total_from_orders":   _safe_div(adv_total_rub * 100, orders_rub),
            # Внутренняя реклама
            "adv_internal_rub":          adv_internal_rub or None,
            "drr_internal_from_sales":   _safe_div(adv_internal_rub * 100, sales_rub),
            "drr_internal_from_orders":  _safe_div(adv_internal_rub * 100, orders_rub),
            "orders_organic_qty":        orders_organic_qty or None,
            "orders_internal_qty":       orders_internal_qty or None,
            "adv_views":    adv_views or None,
            "adv_clicks":   adv_clicks or None,
            "ctr_internal": _safe_div(adv_clicks * 100, adv_views),
            "cpc_internal": _safe_div(adv_internal_rub, adv_clicks),
            "cpo_internal": _safe_div(adv_internal_rub, orders_internal_qty),
            "cpm_internal": _safe_div(adv_internal_rub * 1000, adv_views),
            "adv_internal_profit_forecast": adv_int_profit,
            "romi_internal": _safe_div((adv_int_profit if adv_int_profit is not None else 0) * 100, adv_internal_rub) if adv_int_profit is not None else None,
            # Внешняя реклама итого
            "adv_external_rub":          adv_external_rub or None,
            "drr_external_from_sales":   _safe_div(adv_external_rub * 100, sales_rub),
            "drr_external_from_orders":  _safe_div(adv_external_rub * 100, orders_rub),
            "ext_views":    ext_views,
            "ext_clicks":   ext_clicks,
            "ctr_external": _safe_div((ext_clicks or 0) * 100, ext_views) if ext_views else None,
            # Блогеры
            "blogger_rub":             blogger_rub or None,
            "drr_blogger_from_sales":  _safe_div(blogger_rub * 100, sales_rub),
            "drr_blogger_from_orders": _safe_div(blogger_rub * 100, orders_rub),
            "blogger_views":   blogger_views,
            "blogger_clicks":  blogger_clicks,
            "ctr_blogger":     _safe_div((blogger_clicks or 0) * 100, blogger_views) if blogger_views else None,
            "blogger_carts":   blogger_carts,
            "blogger_orders":  blogger_orders,
            "blogger_profit_forecast": blogger_profit,
            "romi_blogger": _safe_div((blogger_profit if blogger_profit is not None else 0) * 100, blogger_rub) if blogger_profit is not None and blogger_rub else None,
            "blogger_no_stats": blogger_no_stats,
            # ВК SIDS
            "vk_sids_rub":            vk_sids_rub or None,
            "drr_vk_sids_from_sales": _safe_div(vk_sids_rub * 100, sales_rub),
            "drr_vk_sids_from_orders": _safe_div(vk_sids_rub * 100, orders_rub),
            "vk_sids_views":   vk_sids_views,
            "vk_sids_clicks":  vk_sids_clicks,
            "ctr_vk_sids":     _safe_div((vk_sids_clicks or 0) * 100, vk_sids_views) if vk_sids_views else None,
            "vk_sids_orders":  vk_sids_orders,
            "cpo_vk_sids":     _safe_div(vk_sids_rub, vk_sids_orders),
            # SIDS Contractor
            "sids_contractor_rub":             sids_c_rub or None,
            "drr_sids_contractor_from_sales":  _safe_div(sids_c_rub * 100, sales_rub),
            "drr_sids_contractor_from_orders": _safe_div(sids_c_rub * 100, orders_rub),
            "sids_contractor_views":  sids_c_views,
            "sids_contractor_clicks": sids_c_clicks,
            "ctr_sids_contractor":    _safe_div((sids_c_clicks or 0) * 100, sids_c_views) if sids_c_views else None,
            "sids_contractor_orders": sids_c_orders,
            "cpo_sids_contractor":    _safe_div(sids_c_rub, sids_c_orders),
            # Яндекс
            "yandex_contractor_rub":             ya_rub or None,
            "drr_yandex_contractor_from_sales":  _safe_div(ya_rub * 100, sales_rub),
            "drr_yandex_contractor_from_orders": _safe_div(ya_rub * 100, orders_rub),
            "yandex_contractor_views":  ya_views,
            "yandex_contractor_clicks": ya_clicks,
            "ctr_yandex_contractor":    _safe_div((ya_clicks or 0) * 100, ya_views) if ya_views else None,
            "yandex_contractor_orders": ya_orders,
            "cpo_yandex_contractor":    _safe_div(ya_rub, ya_orders),
            # Маржа
            "margin_before_ads_rub": margin_before_ads_rub,
            "margin_before_ads_pct": margin_before_ads_pct,
            "margin_rub":            margin_rub,
            "margin_pct":            margin_pct,
            # Прогноз
            "sales_forecast_rub":  sales_fc_rub,
            "margin_forecast_rub": margin_fc_rub,
            "margin_forecast_pct": _safe_div((margin_fc_rub if margin_fc_rub is not None else 0) * 100, sales_fc_rub) if margin_fc_rub is not None and sales_fc_rub else None,
        })

    return result
