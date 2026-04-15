"""Connection factories and shared utilities for the data layer."""

import logging
import os
from contextlib import contextmanager
from decimal import Decimal

import psycopg2

from shared.config import DB_CONFIG, DB_WB, DB_OZON, MARKETPLACE_DB_CONFIG

logger = logging.getLogger(__name__)

__all__ = [
    "_DATA_SOURCE",
    "_get_wb_connection",
    "_get_ozon_connection",
    "_get_supabase_connection",
    "_db_cursor",
    "to_float",
    "format_num",
    "format_pct",
    "get_arrow",
    "calc_change",
    "calc_change_pp",
]

# =============================================================================
# CONNECTION FACTORY — переключение legacy / managed БД
# =============================================================================
_DATA_SOURCE = os.getenv('DATA_SOURCE', 'legacy')  # 'legacy' | 'managed'


def _get_wb_connection():
    """Get WB database connection (legacy or managed)."""
    if _DATA_SOURCE == 'managed' and MARKETPLACE_DB_CONFIG.get('host'):
        conn = psycopg2.connect(**MARKETPLACE_DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("SET search_path TO wb, public")
        return conn
    return psycopg2.connect(**DB_CONFIG, database=DB_WB)


def _get_ozon_connection():
    """Get Ozon database connection (legacy or managed)."""
    if _DATA_SOURCE == 'managed' and MARKETPLACE_DB_CONFIG.get('host'):
        conn = psycopg2.connect(**MARKETPLACE_DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("SET search_path TO ozon, public")
        return conn
    return psycopg2.connect(**DB_CONFIG, database=DB_OZON)


def _get_supabase_connection():
    """Get a connection to the Supabase pooler using root .env settings."""
    return psycopg2.connect(
        host=os.getenv("SUPABASE_HOST", "aws-1-ap-northeast-2.pooler.supabase.com"),
        port=int(os.getenv("SUPABASE_PORT", "5432")),
        database=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER", "postgres"),
        password=os.getenv("SUPABASE_PASSWORD", ""),
        sslmode="require",
    )


@contextmanager
def _db_cursor(conn_factory):
    """Context manager: гарантирует закрытие cursor и connection при исключении.

    Использование::

        with _db_cursor(_get_wb_connection) as (conn, cur):
            cur.execute(...)
            results = cur.fetchall()
        # cur и conn закрываются автоматически, даже при исключении
    """
    conn = conn_factory()
    cur = conn.cursor()
    try:
        yield conn, cur
    finally:
        cur.close()
        conn.close()


# =============================================================================
# УТИЛИТЫ
# =============================================================================

def to_float(val):
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    return float(val)


def format_num(num, decimals=0):
    if num is None:
        return "0"
    if decimals == 0:
        return f"{num:,.0f}".replace(",", " ")
    return f"{num:,.{decimals}f}".replace(",", " ")


def format_pct(num):
    if num is None:
        return "0.0%"
    return f"{num:.1f}%"


def get_arrow(change):
    if change > 0.5:
        return "↑"
    elif change < -0.5:
        return "↓"
    return "→"


def calc_change(current, previous):
    if previous == 0 or previous is None:
        return 0
    return ((current - previous) / abs(previous)) * 100


def calc_change_pp(current, previous):
    if current is None or previous is None:
        return 0
    return current - previous
