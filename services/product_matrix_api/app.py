"""Product Matrix API — FastAPI backend for the Wookiee product matrix editor."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.product_matrix_api.routes.lookups import router as lookups_router
from services.product_matrix_api.routes.models import router as models_router

app = FastAPI(title="Product Matrix API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("product_matrix_api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


app.include_router(lookups_router)
app.include_router(models_router)


@app.get("/health")
def health():
    return {"ok": True}
