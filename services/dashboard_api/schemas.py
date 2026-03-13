"""Pydantic response models for Dashboard API."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ── Finance Summary ──────────────────────────────────────────────────────────

class FinancePeriodMetrics(BaseModel):
    """Metrics for a single period (current or previous)."""
    orders_count: float = 0
    sales_count: float = 0
    revenue_before_spp: float = 0
    revenue_after_spp: float = 0
    adv_internal: float = 0
    adv_external: float = 0
    adv_total: float = 0
    cost_of_goods: float = 0
    logistics: float = 0
    storage: float = 0
    commission: float = 0
    spp_amount: float = 0
    nds: float = 0
    penalty: float = 0
    retention: float = 0
    deduction: float = 0
    margin: float = 0
    margin_pct: float = 0
    returns_revenue: float = 0
    revenue_before_spp_gross: float = 0
    orders_rub: float = 0
    drr_pct: float = 0


class FinanceSummaryResponse(BaseModel):
    current: FinancePeriodMetrics
    previous: FinancePeriodMetrics


# ── Finance By Model ─────────────────────────────────────────────────────────

class ModelFinanceRow(BaseModel):
    period: str
    model: str
    mp: str  # "wb" | "ozon"
    sales_count: float = 0
    revenue_before_spp: float = 0
    adv_internal: float = 0
    adv_external: float = 0
    adv_total: float = 0
    margin: float = 0
    margin_pct: float = 0
    cost_of_goods: float = 0
    orders_count: float = 0
    orders_rub: float = 0
    drr_pct: float = 0


class FinanceByModelResponse(BaseModel):
    rows: list[ModelFinanceRow]


# ── Series Daily ─────────────────────────────────────────────────────────────

class DailyDataPoint(BaseModel):
    date: str
    orders_count: float = 0
    sales_count: float = 0
    revenue_before_spp: float = 0
    revenue_after_spp: float = 0
    adv_total: float = 0
    cost_of_goods: float = 0
    logistics: float = 0
    storage: float = 0
    commission: float = 0
    spp_amount: float = 0
    margin: float = 0


class DailySeriesResponse(BaseModel):
    series: list[DailyDataPoint]


# ── Series Weekly ────────────────────────────────────────────────────────────

class WeeklyDataPoint(BaseModel):
    week_start: str
    week_end: str
    days: int = 0
    orders_count: float = 0
    sales_count: float = 0
    revenue_before_spp: float = 0
    adv_total: float = 0
    cost_of_goods: float = 0
    logistics: float = 0
    storage: float = 0
    commission: float = 0
    margin: float = 0
    orders_rub: float = 0


class WeeklySeriesResponse(BaseModel):
    weeks: list[WeeklyDataPoint]


# ── Stocks Summary ───────────────────────────────────────────────────────────

class StocksSummaryResponse(BaseModel):
    avg_stock: float = 0
    channel: str  # "wb" | "ozon" | "all"


# ── Stocks Turnover ──────────────────────────────────────────────────────────

class TurnoverModelRow(BaseModel):
    model: str
    mp: str  # "wb" | "ozon"
    avg_stock: float = 0
    stock_mp: float = 0
    stock_moysklad: float = 0
    daily_sales: float = 0
    turnover_days: float = 0
    sales_count: float = 0
    revenue: float = 0
    margin: float = 0


class TurnoverResponse(BaseModel):
    rows: list[TurnoverModelRow]


# ── ABC ──────────────────────────────────────────────────────────────────────

class AbcArticle(BaseModel):
    """Single article row with ABC classification and metadata."""
    article: str
    model: Optional[str] = None
    mp: str  # "wb" | "ozon"
    orders_count: float = 0
    sales_count: float = 0
    revenue: float = 0
    margin: float = 0
    adv_internal: float = 0
    adv_external: float = 0
    adv_total: float = 0
    margin_share_pct: float = 0
    cumulative_share_pct: float = 0
    abc_category: str = "C"  # A | B | C | New
    # article metadata from Supabase
    status: Optional[str] = None
    model_kod: Optional[str] = None
    model_osnova: Optional[str] = None
    color_code: Optional[str] = None
    color: Optional[str] = None
    tip_kollekcii: Optional[str] = None


class AbcResponse(BaseModel):
    articles: list[AbcArticle]
    total_margin: float
    article_count: int


# ── Traffic ──────────────────────────────────────────────────────────────────

class OrganicFunnel(BaseModel):
    period: str  # "current" | "previous"
    card_opens: float = 0
    add_to_cart: float = 0
    funnel_orders: float = 0
    buyouts: float = 0


class AdMetrics(BaseModel):
    period: str
    ad_views: float = 0
    ad_clicks: float = 0
    ad_to_cart: float = 0
    ad_orders: float = 0
    ad_spend: float = 0
    ctr: float = 0
    cpc: float = 0


class TrafficSummaryResponse(BaseModel):
    organic: list[OrganicFunnel]
    ads: list[AdMetrics]


class TrafficByModelRow(BaseModel):
    period: str
    model: str
    ad_views: float = 0
    ad_clicks: float = 0
    ad_spend: float = 0
    ad_to_cart: float = 0
    ad_orders: float = 0
    ctr: float = 0
    cpc: float = 0


class OrganicVsPaidRow(BaseModel):
    period: str
    card_opens: float = 0
    add_to_cart: float = 0
    funnel_orders: float = 0
    buyouts: float = 0
    card_to_cart_pct: float = 0
    cart_to_order_pct: float = 0
    order_to_buyout_pct: float = 0


class PaidFunnelRow(BaseModel):
    period: str
    ad_views: float = 0
    ad_clicks: float = 0
    ad_to_cart: float = 0
    ad_orders: float = 0
    ad_spend: float = 0
    ctr: float = 0
    cpc: float = 0


class OrganicVsPaidResponse(BaseModel):
    organic: list[OrganicVsPaidRow]
    paid: list[PaidFunnelRow]


class ExternalBreakdownRow(BaseModel):
    period: str
    adv_internal: float = 0
    adv_bloggers: float = 0
    adv_vk: float = 0
    adv_creators: float = 0
    adv_total: float = 0


class ExternalBreakdownResponse(BaseModel):
    wb: list[ExternalBreakdownRow]
    ozon: list[ExternalBreakdownRow]


# ── Promo / Advertising ─────────────────────────────────────────────────────

class ModelAdRoiRow(BaseModel):
    period: str
    model: str
    ad_spend: float = 0
    ad_orders: float = 0
    revenue: float = 0
    margin: float = 0
    drr_pct: Optional[float] = None
    romi: Optional[float] = None


class AdDailyRow(BaseModel):
    date: str
    views: float = 0
    clicks: float = 0
    spend: float = 0
    to_cart: float = 0
    orders: float = 0
    ctr: float = 0
    cpc: float = 0


class BudgetRow(BaseModel):
    date: str
    budget: float = 0


class ActualSpendRow(BaseModel):
    date: str
    actual_spend: float = 0
    views: float = 0
    clicks: float = 0
    orders: float = 0


class BudgetUtilizationResponse(BaseModel):
    budget: list[BudgetRow]
    actual: list[ActualSpendRow]
