#!/usr/bin/env python3
"""
Migration 001: Create content_assets table for Content Knowledge Base.

Creates:
- pgvector extension (if not exists)
- content_assets table with vector(3072) column
- btree indexes on metadata columns
- RLS policies (per project rules)
- search_content() function for vector similarity search

SAFE: Does NOT touch any existing tables.
"""

import psycopg2
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")


def _env_first(keys, default=""):
    for k in keys:
        v = os.getenv(k)
        if v not in (None, ""):
            return v
    return default


SUPABASE_CONFIG = {
    "host": _env_first(['POSTGRES_HOST', 'SUPABASE_HOST'], 'localhost'),
    "port": int(_env_first(['POSTGRES_PORT', 'SUPABASE_PORT'], '5432')),
    "database": _env_first(['POSTGRES_DB', 'SUPABASE_DB'], 'postgres'),
    "user": _env_first(['POSTGRES_USER', 'SUPABASE_USER'], 'postgres'),
    "password": _env_first(['POSTGRES_PASSWORD', 'SUPABASE_PASSWORD'], ''),
    "sslmode": "require",
}


def migrate():
    print("=" * 60)
    print("Migration 001: Create content_assets table")
    print("=" * 60)
    print(f"Host: {SUPABASE_CONFIG['host']}")
    print(f"Database: {SUPABASE_CONFIG['database']}")

    conn = psycopg2.connect(**SUPABASE_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Step 1: Enable pgvector extension
        print("\n--- Step 1: Enable pgvector extension ---")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("  pgvector extension enabled")

        # Step 2: Create content_assets table
        print("\n--- Step 2: Create content_assets table ---")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS content_assets (
                id              BIGSERIAL PRIMARY KEY,
                embedding       vector(3072) NOT NULL,

                -- Path and file info
                disk_path       TEXT NOT NULL UNIQUE,
                file_name       VARCHAR(500) NOT NULL,
                mime_type       VARCHAR(100) NOT NULL,
                file_size       BIGINT,
                md5             VARCHAR(32) NOT NULL,

                -- Metadata from path
                year            SMALLINT NOT NULL DEFAULT 2025,
                content_category VARCHAR(50),
                model_name      VARCHAR(100),
                color           VARCHAR(100),
                sku             VARCHAR(50),
                status          VARCHAR(20) NOT NULL DEFAULT 'indexed',

                -- System
                indexed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ
            );
        """)
        print("  content_assets table created")

        # Step 3: Create indexes
        print("\n--- Step 3: Create indexes ---")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_assets_model
            ON content_assets (model_name);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_assets_color
            ON content_assets (color);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_assets_category
            ON content_assets (content_category);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_assets_sku
            ON content_assets (sku);
        """)
        print("  Metadata indexes created")
        print("  NOTE: Vector index (HNSW) will be created after >10K records")

        # Step 4: Enable RLS
        print("\n--- Step 4: Enable RLS ---")
        cur.execute("ALTER TABLE content_assets ENABLE ROW LEVEL SECURITY;")
        print("  RLS enabled on content_assets")

        # Step 5: Create RLS policies
        print("\n--- Step 5: Create RLS policies ---")
        cur.execute("""
            CREATE POLICY service_role_full_access_content_assets ON content_assets
            FOR ALL TO postgres
            USING (true) WITH CHECK (true);
        """)
        print("  Policy: postgres full access")

        cur.execute("""
            CREATE POLICY authenticated_select_content_assets ON content_assets
            FOR SELECT TO authenticated
            USING (true);
        """)
        print("  Policy: authenticated SELECT only")

        # Step 6: Create search_content() function
        print("\n--- Step 6: Create search_content() function ---")
        cur.execute("""
            CREATE OR REPLACE FUNCTION search_content(
                query_embedding vector(3072),
                match_count INT DEFAULT 10,
                filter_model VARCHAR DEFAULT NULL,
                filter_color VARCHAR DEFAULT NULL,
                filter_category VARCHAR DEFAULT NULL,
                filter_sku VARCHAR DEFAULT NULL,
                min_similarity FLOAT DEFAULT 0.3
            )
            RETURNS TABLE (
                id BIGINT,
                disk_path TEXT,
                file_name VARCHAR,
                similarity FLOAT,
                model_name VARCHAR,
                color VARCHAR,
                content_category VARCHAR,
                sku VARCHAR,
                mime_type VARCHAR,
                file_size BIGINT
            ) LANGUAGE plpgsql AS $$
            BEGIN
                RETURN QUERY
                SELECT
                    ca.id,
                    ca.disk_path,
                    ca.file_name,
                    (1 - (ca.embedding <=> query_embedding))::FLOAT AS similarity,
                    ca.model_name,
                    ca.color,
                    ca.content_category,
                    ca.sku,
                    ca.mime_type,
                    ca.file_size
                FROM content_assets ca
                WHERE
                    ca.status = 'indexed'
                    AND (filter_model IS NULL OR LOWER(ca.model_name) = LOWER(filter_model))
                    AND (filter_color IS NULL OR LOWER(ca.color) = LOWER(filter_color))
                    AND (filter_category IS NULL OR LOWER(ca.content_category) = LOWER(filter_category))
                    AND (filter_sku IS NULL OR ca.sku = filter_sku)
                    AND 1 - (ca.embedding <=> query_embedding) >= min_similarity
                ORDER BY ca.embedding <=> query_embedding
                LIMIT match_count;
            END;
            $$;
        """)
        print("  search_content() function created")

        conn.commit()
        print("\n" + "=" * 60)
        print("MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        return True

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        print("All changes rolled back!")
        return False

    finally:
        cur.close()
        conn.close()


def verify():
    """Verify migration was applied correctly."""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    conn = psycopg2.connect(**SUPABASE_CONFIG)
    cur = conn.cursor()

    # Check table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'content_assets'
        );
    """)
    exists = cur.fetchone()[0]
    print(f"  content_assets table exists: {exists}")

    # Check RLS
    cur.execute("""
        SELECT rowsecurity FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'content_assets';
    """)
    row = cur.fetchone()
    rls = row[0] if row else False
    print(f"  RLS enabled: {rls}")

    # Check policies
    cur.execute("""
        SELECT policyname FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'content_assets';
    """)
    policies = [r[0] for r in cur.fetchall()]
    print(f"  Policies: {policies}")

    # Check function
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM pg_proc
            WHERE proname = 'search_content'
        );
    """)
    func_exists = cur.fetchone()[0]
    print(f"  search_content() function exists: {func_exists}")

    # Check columns
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'content_assets'
        ORDER BY ordinal_position;
    """)
    print("  Columns:")
    for row in cur.fetchall():
        print(f"    {row[0]}: {row[1]}")

    cur.close()
    conn.close()

    ok = exists and rls and func_exists
    print(f"\n  All checks {'PASSED' if ok else 'FAILED'}!")
    return ok


if __name__ == "__main__":
    success = migrate()
    if success:
        verify()
    sys.exit(0 if success else 1)
