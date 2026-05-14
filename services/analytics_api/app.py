"""Analytics API — РНП (Рука на Пульсе) weekly analytics dashboard backend.

    GET /health              — healthcheck
    GET /api/rnp/models      — list of available WB models
    GET /api/rnp/weeks       — weekly analytics for one model
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

GOOGLE_SA_FILE        = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "services/sheets_sync/credentials/google_sa.json")
RNP_EXT_ADS_SHEET_ID  = os.getenv("RNP_EXT_ADS_SHEET_ID", "")
RNP_BLOGGERS_SHEET_ID = os.getenv("RNP_BLOGGERS_SHEET_ID", "")

app = FastAPI(title="Analytics API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://hub.os.wookiee.shop",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

from services.analytics_api.auth import verify_auth as _verify_auth  # noqa: E402
from services.analytics_api.marketing import router as marketing_router  # noqa: E402

app.include_router(marketing_router)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("analytics_api")

MAX_PERIOD_DAYS = 91  # 13 weeks


def _align_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _align_sunday(d: date) -> date:
    return d + timedelta(days=(6 - d.weekday()))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/rnp/models")
def rnp_models(
    marketplace: str = Query("wb"),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    _verify_auth(x_api_key, authorization)
    if marketplace != "wb":
        raise HTTPException(501, "Only marketplace=wb supported in Phase 1")
    from shared.data_layer.rnp import fetch_rnp_models_wb
    models = fetch_rnp_models_wb()  # list[{"label": str, "value": str}]
    return {"marketplace": marketplace, "models": models}


@app.get("/api/rnp/weeks")
def rnp_weeks(
    model: str = Query(...),
    date_from: date = Query(...),
    date_to: date   = Query(...),
    marketplace: str          = Query("wb"),
    buyout_forecast: Optional[float] = Query(None, ge=0.0, le=1.0),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    _verify_auth(x_api_key, authorization)

    if marketplace != "wb":
        raise HTTPException(501, "Only marketplace=wb supported in Phase 1")

    date_from = _align_monday(date_from)
    date_to   = _align_sunday(date_to)

    if (date_to - date_from).days > MAX_PERIOD_DAYS:
        raise HTTPException(400, "Period exceeds 13 weeks maximum")

    from shared.data_layer.rnp import (
        fetch_rnp_wb_daily,
        fetch_rnp_sheets_digital,
        fetch_rnp_sheets_bloggers,
        aggregate_to_weeks,
        resolve_wb_key,
    )

    # model = display key (e.g. "vuki"); wb_key = actual WB article prefix (e.g. "компбел-ж-бесшов")
    wb_key = resolve_wb_key(model)
    daily_rows = fetch_rnp_wb_daily(wb_key, date_from, date_to)

    ext_ads_available = True
    sheets_data: dict = {}
    try:
        if RNP_EXT_ADS_SHEET_ID:
            digital = fetch_rnp_sheets_digital(
                date_from, date_to, model, GOOGLE_SA_FILE, RNP_EXT_ADS_SHEET_ID
            )
            for wk, ch_data in digital.items():
                sheets_data.setdefault(wk, {}).update(ch_data)

        if RNP_BLOGGERS_SHEET_ID:
            bloggers = fetch_rnp_sheets_bloggers(
                date_from, date_to, model, GOOGLE_SA_FILE, RNP_BLOGGERS_SHEET_ID
            )
            for wk, bl_data in bloggers.items():
                sheets_data.setdefault(wk, {}).update(bl_data)
    except Exception as exc:
        logger.warning("Sheets unavailable, returning DB-only data: %s", exc)
        ext_ads_available = False
        sheets_data = {}

    weeks = aggregate_to_weeks(daily_rows, sheets_data, buyout_forecast)

    tot_orders = sum(w.get("orders_qty") or 0 for w in weeks)
    tot_sales  = sum(w.get("sales_qty") or 0 for w in weeks)
    buyout_used = (tot_sales / tot_orders) if tot_orders > 0 else (buyout_forecast or 0.87)

    return {
        "model":               model,
        "marketplace":         marketplace,
        "date_from":           date_from.isoformat(),
        "date_to":             date_to.isoformat(),
        "buyout_forecast_used": round(buyout_used, 4),
        "ext_ads_available":   ext_ads_available,
        "weeks":               weeks,
    }
