#!/usr/bin/env python3
"""
Migration 001: Create Knowledge Base tables in Supabase.

Creates:
- pgvector extension (if not exists)
- kb_chunks table with vector(768) column
- IVFFlat index for cosine similarity search
- RLS policies (per project rules)
- search_kb() function for vector search

SAFE: Does NOT touch any existing tables (cveta, modeli, artikuly, etc.)
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
    print("Migration 001: Create Knowledge Base tables")
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

        # Step 2: Create kb_chunks table
        print("\n--- Step 2: Create kb_chunks table ---")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kb_chunks (
                id BIGSERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                embedding vector(768) NOT NULL,
                module VARCHAR(20),
                file_name VARCHAR(500) NOT NULL,
                file_type VARCHAR(10) NOT NULL,
                content_type VARCHAR(20),
                chunk_index INTEGER NOT NULL,
                is_cleaned BOOLEAN DEFAULT false,
                source_path TEXT,
                ingested_at TIMESTAMPTZ DEFAULT now()
            );
        """)
        print("  kb_chunks table created")

        # Step 3: Create indexes
        print("\n--- Step 3: Create indexes ---")

        # Check if we have enough rows for IVFFlat (needs > lists count)
        # Create index after data is loaded; for now create btree indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS kb_chunks_module_idx
            ON kb_chunks (module);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS kb_chunks_file_name_idx
            ON kb_chunks (file_name);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS kb_chunks_content_type_idx
            ON kb_chunks (content_type);
        """)
        print("  Metadata indexes created")
        print("  NOTE: Vector index (IVFFlat) will be created after data ingestion")

        # Step 4: Enable RLS
        print("\n--- Step 4: Enable RLS ---")
        cur.execute("ALTER TABLE kb_chunks ENABLE ROW LEVEL SECURITY;")
        print("  RLS enabled on kb_chunks")

        # Step 5: Create RLS policies
        print("\n--- Step 5: Create RLS policies ---")
        cur.execute("""
            CREATE POLICY service_role_full_access_kb_chunks ON kb_chunks
            FOR ALL TO postgres
            USING (true) WITH CHECK (true);
        """)
        print("  Policy: postgres full access")

        cur.execute("""
            CREATE POLICY authenticated_select_kb_chunks ON kb_chunks
            FOR SELECT TO authenticated
            USING (true);
        """)
        print("  Policy: authenticated SELECT only")

        # Step 6: Create search function
        print("\n--- Step 6: Create search_kb() function ---")
        cur.execute("""
            CREATE OR REPLACE FUNCTION search_kb(
                query_embedding vector(768),
                match_count INT DEFAULT 5,
                filter_module VARCHAR DEFAULT NULL,
                filter_content_type VARCHAR DEFAULT NULL,
                min_similarity FLOAT DEFAULT 0.5
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
                source_path TEXT
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
                    kc.source_path
                FROM kb_chunks kc
                WHERE
                    (filter_module IS NULL OR kc.module = filter_module)
                    AND (filter_content_type IS NULL OR kc.content_type = filter_content_type)
                    AND (1 - (kc.embedding <=> query_embedding)) >= min_similarity
                ORDER BY kc.embedding <=> query_embedding
                LIMIT match_count;
            END;
            $$;
        """)
        print("  search_kb() function created")

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


def create_vector_index():
    """Create IVFFlat vector index. Call AFTER data ingestion."""
    print("\nCreating IVFFlat vector index...")
    conn = psycopg2.connect(**SUPABASE_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) FROM kb_chunks;")
        count = cur.fetchone()[0]
        lists = max(10, min(count // 10, 100))  # 10-100 lists based on data size
        print(f"  Rows: {count}, IVFFlat lists: {lists}")

        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS kb_chunks_embedding_idx ON kb_chunks
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = {lists});
        """)
        conn.commit()
        print("  Vector index created!")
    except Exception as e:
        conn.rollback()
        print(f"  ERROR creating vector index: {e}")
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
            WHERE table_schema = 'public' AND table_name = 'kb_chunks'
        );
    """)
    exists = cur.fetchone()[0]
    print(f"  kb_chunks table exists: {exists}")

    # Check RLS
    cur.execute("""
        SELECT rowsecurity FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'kb_chunks';
    """)
    row = cur.fetchone()
    rls = row[0] if row else False
    print(f"  RLS enabled: {rls}")

    # Check policies
    cur.execute("""
        SELECT policyname FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'kb_chunks';
    """)
    policies = [r[0] for r in cur.fetchall()]
    print(f"  Policies: {policies}")

    # Check function
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM pg_proc
            WHERE proname = 'search_kb'
        );
    """)
    func_exists = cur.fetchone()[0]
    print(f"  search_kb() function exists: {func_exists}")

    # Check pgvector
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM pg_extension WHERE extname = 'vector'
        );
    """)
    vec_exists = cur.fetchone()[0]
    print(f"  pgvector extension: {vec_exists}")

    cur.close()
    conn.close()

    ok = exists and rls and func_exists and vec_exists
    print(f"\n  All checks {'PASSED' if ok else 'FAILED'}!")
    return ok


if __name__ == "__main__":
    success = migrate()
    if success:
        verify()
    sys.exit(0 if success else 1)
