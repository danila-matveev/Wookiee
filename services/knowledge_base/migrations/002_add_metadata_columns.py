#!/usr/bin/env python3
"""
Migration 002: Add metadata columns to kb_chunks.

Adds:
- source_tag: origin of the content (course, playbook, manual, insight)
- verified: whether the content has been verified
- updated_at: last update timestamp
- Updated search_kb() function with new columns
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
    print("Migration 002: Add metadata columns to kb_chunks")
    print("=" * 60)
    print(f"Host: {SUPABASE_CONFIG['host']}")
    print(f"Database: {SUPABASE_CONFIG['database']}")

    conn = psycopg2.connect(**SUPABASE_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Step 1: Add source_tag column
        print("\n--- Step 1: Add source_tag column ---")
        cur.execute("""
            ALTER TABLE kb_chunks
            ADD COLUMN IF NOT EXISTS source_tag VARCHAR(30) DEFAULT 'course';
        """)
        print("  source_tag column added")

        # Step 2: Add verified column
        print("\n--- Step 2: Add verified column ---")
        cur.execute("""
            ALTER TABLE kb_chunks
            ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT false;
        """)
        print("  verified column added")

        # Step 3: Add updated_at column
        print("\n--- Step 3: Add updated_at column ---")
        cur.execute("""
            ALTER TABLE kb_chunks
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
        """)
        print("  updated_at column added")

        # Step 4: Create index on source_tag
        print("\n--- Step 4: Create source_tag index ---")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS kb_chunks_source_tag_idx
            ON kb_chunks (source_tag);
        """)
        print("  source_tag index created")

        # Step 5: Mark all existing rows as course + verified
        print("\n--- Step 5: Update existing rows ---")
        cur.execute("""
            UPDATE kb_chunks
            SET source_tag = 'course', verified = true
            WHERE source_tag IS NULL OR source_tag = 'course';
        """)
        updated = cur.rowcount
        print(f"  Updated {updated} existing rows: source_tag='course', verified=true")

        # Step 6: Recreate search_kb() with new columns
        print("\n--- Step 6: Update search_kb() function ---")
        cur.execute("""
            CREATE OR REPLACE FUNCTION search_kb(
                query_embedding vector(768),
                match_count INT DEFAULT 5,
                filter_module VARCHAR DEFAULT NULL,
                filter_content_type VARCHAR DEFAULT NULL,
                min_similarity FLOAT DEFAULT 0.5,
                filter_source_tag VARCHAR DEFAULT NULL
            )
            RETURNS TABLE (
                id BIGINT,
                content TEXT,
                similarity FLOAT,
                module VARCHAR,
                file_name VARCHAR,
                file_type VARCHAR,
                content_type VARCHAR,
                chunk_index INTEGER,
                source_path TEXT,
                source_tag VARCHAR,
                verified BOOLEAN
            ) LANGUAGE plpgsql AS $$
            BEGIN
                RETURN QUERY
                SELECT
                    kc.id,
                    kc.content,
                    (1 - (kc.embedding <=> query_embedding))::FLOAT AS similarity,
                    kc.module,
                    kc.file_name,
                    kc.file_type,
                    kc.content_type,
                    kc.chunk_index,
                    kc.source_path,
                    kc.source_tag,
                    kc.verified
                FROM kb_chunks kc
                WHERE
                    (filter_module IS NULL OR kc.module = filter_module)
                    AND (filter_content_type IS NULL OR kc.content_type = filter_content_type)
                    AND (filter_source_tag IS NULL OR kc.source_tag = filter_source_tag)
                    AND (1 - (kc.embedding <=> query_embedding)) >= min_similarity
                ORDER BY kc.embedding <=> query_embedding
                LIMIT match_count;
            END;
            $$;
        """)
        print("  search_kb() function updated with source_tag + verified")

        conn.commit()
        print("\n" + "=" * 60)
        print("MIGRATION 002 COMPLETED SUCCESSFULLY!")
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

    # Check new columns exist
    for col in ('source_tag', 'verified', 'updated_at'):
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'kb_chunks'
                  AND column_name = %s
            );
        """, (col,))
        exists = cur.fetchone()[0]
        print(f"  Column '{col}' exists: {exists}")

    # Check all existing rows have source_tag='course'
    cur.execute("""
        SELECT COUNT(*) FROM kb_chunks WHERE source_tag = 'course';
    """)
    course_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM kb_chunks;")
    total_count = cur.fetchone()[0]
    print(f"  Rows with source_tag='course': {course_count}/{total_count}")

    # Check search_kb function has new parameter
    cur.execute("""
        SELECT pronargs FROM pg_proc WHERE proname = 'search_kb';
    """)
    row = cur.fetchone()
    nargs = row[0] if row else 0
    print(f"  search_kb() parameter count: {nargs} (expected 6)")

    cur.close()
    conn.close()

    print(f"\n  Verification {'PASSED' if nargs == 6 else 'CHECK MANUALLY'}!")
    return nargs == 6


if __name__ == "__main__":
    success = migrate()
    if success:
        verify()
    sys.exit(0 if success else 1)
