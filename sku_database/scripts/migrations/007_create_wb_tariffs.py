#!/usr/bin/env python3
"""
Migration 007: Create wb_tariffs table for daily WB tariff snapshots.

Stores historical box tariffs from /api/v1/tariffs/box for logistics
overpayment calculations in services/logistics_audit.

- UNIQUE constraint on (dt, warehouse_name) prevents duplicates
- RLS enabled: anon blocked, authenticated gets SELECT only
- Python scripts via postgres role are unaffected by RLS
"""

import psycopg2
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent.parent.parent / ".env")

SUPABASE_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "aws-1-ap-northeast-2.pooler.supabase.com"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "postgres"),
    "user": os.getenv("POSTGRES_USER", "postgres.gjvwcdtfglupewcwzfhw"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "sslmode": "require",
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS wb_tariffs (
    id                BIGSERIAL PRIMARY KEY,
    dt                DATE           NOT NULL,
    warehouse_name    TEXT           NOT NULL,
    delivery_coef     INTEGER        NOT NULL DEFAULT 0,
    logistics_1l      NUMERIC(10,2)  NOT NULL DEFAULT 0,
    logistics_extra_l NUMERIC(10,2)  NOT NULL DEFAULT 0,
    storage_1l_day    NUMERIC(10,2)  NOT NULL DEFAULT 0,
    acceptance        NUMERIC(10,2)  NOT NULL DEFAULT 0,
    geo_name          TEXT           NOT NULL DEFAULT '',
    created_at        TIMESTAMPTZ    NOT NULL DEFAULT now(),

    UNIQUE (dt, warehouse_name)
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_wb_tariffs_dt_wh
    ON wb_tariffs (dt, warehouse_name);
"""

RLS_SQL = """
ALTER TABLE wb_tariffs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON wb_tariffs FROM anon, authenticated;
GRANT SELECT ON wb_tariffs TO authenticated;

CREATE POLICY wb_tariffs_select ON wb_tariffs
    FOR SELECT TO authenticated USING (true);

REVOKE ALL ON SEQUENCE wb_tariffs_id_seq FROM anon, authenticated;
"""


def run():
    print("Migration 007: Create wb_tariffs table")
    print(f"  Host: {SUPABASE_CONFIG['host']}")

    conn = psycopg2.connect(**SUPABASE_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        print("  Creating table wb_tariffs...")
        cur.execute(CREATE_TABLE_SQL)

        print("  Creating index idx_wb_tariffs_dt_wh...")
        cur.execute(CREATE_INDEX_SQL)

        print("  Enabling RLS and setting permissions...")
        for stmt in RLS_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt + ";")

        # Verify
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'wb_tariffs' ORDER BY ordinal_position"
        )
        columns = cur.fetchall()
        print(f"  Table created with {len(columns)} columns:")
        for col_name, col_type in columns:
            print(f"    - {col_name}: {col_type}")

        cur.execute(
            "SELECT relrowsecurity FROM pg_class WHERE relname = 'wb_tariffs'"
        )
        rls_enabled = cur.fetchone()[0]
        print(f"  RLS enabled: {rls_enabled}")

        print("Migration 007 completed successfully!")

    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
