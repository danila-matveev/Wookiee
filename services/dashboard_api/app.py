"""Dashboard API — backend for WookieeHub dashboard.

    GET /health  — healthcheck for Docker / monitoring
"""
from __future__ import annotations

import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.dashboard_api.routes.abc import router as abc_router
from services.dashboard_api.routes.finance import router as finance_router
from services.dashboard_api.routes.promo import router as promo_router
from services.dashboard_api.routes.series import router as series_router
from services.dashboard_api.routes.stocks import router as stocks_router
from services.dashboard_api.routes.traffic import router as traffic_router
from services.dashboard_api.routes.comms import router as comms_router

load_dotenv()

app = FastAPI(title="Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # dev — allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("dashboard_api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(abc_router)
app.include_router(finance_router)
app.include_router(promo_router)
app.include_router(series_router)
app.include_router(stocks_router)
app.include_router(traffic_router)
app.include_router(comms_router)


# ── Endpoints ────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}
