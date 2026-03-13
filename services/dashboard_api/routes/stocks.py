"""Stocks routes: summary and turnover by model."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from services.dashboard_api.cache import cached
from services.dashboard_api.dependencies import CommonParams
from services.dashboard_api.schemas import (
    StocksSummaryResponse,
    TurnoverModelRow,
    TurnoverResponse,
)
from shared.data_layer import (
    get_ozon_turnover_by_model,
    get_total_avg_stock,
    get_wb_turnover_by_model,
)

logger = logging.getLogger("dashboard_api.stocks")
router = APIRouter(prefix="/api/stocks", tags=["stocks"])


# ── Summary ──────────────────────────────────────────────────────────────────

@cached
def _fetch_stock_summary(start_date: str, end_date: str, mp: str) -> StocksSummaryResponse:
    avg = 0.0
    if mp in ("wb", "all"):
        avg += get_total_avg_stock("wb", start_date, end_date)
    if mp in ("ozon", "all"):
        avg += get_total_avg_stock("ozon", start_date, end_date)
    return StocksSummaryResponse(avg_stock=round(avg, 0), channel=mp)


@router.get("/summary", response_model=StocksSummaryResponse)
def stocks_summary(params: CommonParams = Depends()):
    return _fetch_stock_summary(params.start_date, params.end_date, params.mp)


# ── Turnover ─────────────────────────────────────────────────────────────────

@cached
def _fetch_turnover(start_date: str, end_date: str, mp: str) -> TurnoverResponse:
    rows: list[TurnoverModelRow] = []

    if mp in ("wb", "all"):
        wb_data = get_wb_turnover_by_model(start_date, end_date)
        for model_name, vals in wb_data.items():
            rows.append(TurnoverModelRow(
                model=model_name,
                mp="wb",
                avg_stock=vals["avg_stock"],
                stock_mp=vals["stock_mp"],
                stock_moysklad=vals["stock_moysklad"],
                daily_sales=vals["daily_sales"],
                turnover_days=vals["turnover_days"],
                sales_count=vals["sales_count"],
                revenue=vals["revenue"],
                margin=vals["margin"],
            ))

    if mp in ("ozon", "all"):
        oz_data = get_ozon_turnover_by_model(start_date, end_date)
        for model_name, vals in oz_data.items():
            rows.append(TurnoverModelRow(
                model=model_name,
                mp="ozon",
                avg_stock=vals["avg_stock"],
                stock_mp=vals["stock_mp"],
                stock_moysklad=vals["stock_moysklad"],
                daily_sales=vals["daily_sales"],
                turnover_days=vals["turnover_days"],
                sales_count=vals["sales_count"],
                revenue=vals["revenue"],
                margin=vals["margin"],
            ))

    return TurnoverResponse(rows=rows)


@router.get("/turnover", response_model=TurnoverResponse)
def stocks_turnover(params: CommonParams = Depends()):
    return _fetch_turnover(params.start_date, params.end_date, params.mp)
