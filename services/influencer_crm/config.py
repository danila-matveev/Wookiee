"""Loads environment for the Influencer CRM API.

Pulls Supabase Postgres credentials from `.env` (root) and
`sku_database/.env` (fallback, mirrors sheets_etl/loader.py).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / "sku_database" / ".env")


def _required(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"{name} not set in .env")
    return val


API_KEY: str = _required("INFLUENCER_CRM_API_KEY")

_HOST = _required("POSTGRES_HOST")
_PORT = os.getenv("POSTGRES_PORT", "5432")
_DB   = os.getenv("POSTGRES_DB", "postgres")
_USER = _required("POSTGRES_USER")
_PASS = _required("POSTGRES_PASSWORD")

DB_DSN: str = (
    f"postgresql+psycopg2://{_USER}:{_PASS}@{_HOST}:{_PORT}/{_DB}"
    f"?sslmode=require&options=-csearch_path%3Dcrm,public"
)

LOG_LEVEL: str = os.getenv("INFLUENCER_CRM_LOG_LEVEL", "INFO")
