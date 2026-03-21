"""Product Matrix API — FastAPI backend for the Wookiee product matrix editor."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.product_matrix_api.routes.lookups import router as lookups_router
from services.product_matrix_api.routes.models import router as models_router
from services.product_matrix_api.routes.articles import router as articles_router
from services.product_matrix_api.routes.products import router as products_router
from services.product_matrix_api.routes.colors import router as colors_router
from services.product_matrix_api.routes.factories import router as factories_router
from services.product_matrix_api.routes.importers import router as importers_router
from services.product_matrix_api.routes.cards import router as cards_router
from services.product_matrix_api.routes.certs import router as certs_router
from services.product_matrix_api.routes.search import router as search_router
from services.product_matrix_api.routes.bulk import router as bulk_router

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
app.include_router(articles_router)
app.include_router(products_router)
app.include_router(colors_router)
app.include_router(factories_router)
app.include_router(importers_router)
app.include_router(cards_router)
app.include_router(certs_router)
app.include_router(search_router)
app.include_router(bulk_router)


@app.get("/health")
def health():
    return {"ok": True}
