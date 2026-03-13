"""Dashboard API — backend for WookieeHub dashboard.

    GET /health  — healthcheck for Docker / monitoring
"""
from __future__ import annotations

import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


# ── Endpoints ────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}
