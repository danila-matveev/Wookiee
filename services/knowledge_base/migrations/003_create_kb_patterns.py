#!/usr/bin/env python3
"""
Migration 003: Create kb_patterns table for structured business rule storage.

Creates:
- kb_patterns table with category/severity/confidence constraints
- RLS policies (per project rules)
- Indexes on category, verified, source_tag

SAFE: Does NOT touch any existing tables (kb_chunks, etc.)
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
    print("Migration 003: Create kb_patterns table")
    print("=" * 60)
    print(f"Host: {SUPABASE_CONFIG['host']}")
    print(f"Database: {SUPABASE_CONFIG['database']}")

    conn = psycopg2.connect(**SUPABASE_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Step 1: Create kb_patterns table
        print("\n--- Step 1: Create kb_patterns table ---")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kb_patterns (
                id SERIAL PRIMARY KEY,
                pattern_name VARCHAR(200) NOT NULL UNIQUE,
                description TEXT NOT NULL,
                category VARCHAR(20) NOT NULL
                    CHECK (category IN (
                        'margin', 'turnover', 'funnel', 'adv', 'price', 'model'
                    )),
                trigger_condition JSONB NOT NULL,
                action_hint TEXT,
                impact_on VARCHAR(10) NOT NULL
                    CHECK (impact_on IN ('margin', 'turnover', 'both')),
                severity VARCHAR(10) DEFAULT 'warning'
                    CHECK (severity IN ('info', 'warning', 'critical')),
                source_tag VARCHAR(30) NOT NULL
                    CHECK (source_tag IN ('manual', 'insight', 'auto', 'base')),
                verified BOOLEAN DEFAULT FALSE,
                confidence VARCHAR(10) DEFAULT 'medium'
                    CHECK (confidence IN ('high', 'medium', 'low')),
                trigger_count INT DEFAULT 0,
                last_triggered_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        print("  kb_patterns table created")

        # Step 2: Enable RLS
        print("\n--- Step 2: Enable RLS ---")
        cur.execute("ALTER TABLE kb_patterns ENABLE ROW LEVEL SECURITY;")
        print("  RLS enabled on kb_patterns")

        # Step 3: Create RLS policies
        print("\n--- Step 3: Create RLS policies ---")
        cur.execute("""
            CREATE POLICY service_role_full_access_kb_patterns ON kb_patterns
            FOR ALL TO postgres
            USING (true) WITH CHECK (true);
        """)
        print("  Policy: postgres full access")

        cur.execute("""
            CREATE POLICY authenticated_select_kb_patterns ON kb_patterns
            FOR SELECT TO authenticated
            USING (true);
        """)
        print("  Policy: authenticated SELECT only")

        # Step 4: Create indexes
        print("\n--- Step 4: Create indexes ---")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_kb_patterns_category
            ON kb_patterns (category);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_kb_patterns_verified
            ON kb_patterns (verified);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_kb_patterns_source
            ON kb_patterns (source_tag);
        """)
        print("  Indexes created: category, verified, source_tag")

        conn.commit()
        print("\n" + "=" * 60)
        print("MIGRATION 003 COMPLETED SUCCESSFULLY!")
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
            WHERE table_schema = 'public' AND table_name = 'kb_patterns'
        );
    """)
    exists = cur.fetchone()[0]
    print(f"  kb_patterns table exists: {exists}")

    # Check RLS
    cur.execute("""
        SELECT rowsecurity FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'kb_patterns';
    """)
    row = cur.fetchone()
    rls = row[0] if row else False
    print(f"  RLS enabled: {rls}")

    # Check policies
    cur.execute("""
        SELECT policyname FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'kb_patterns';
    """)
    policies = [r[0] for r in cur.fetchall()]
    print(f"  Policies: {policies}")

    # Check key columns exist
    for col in ('pattern_name', 'category', 'trigger_condition',
                'impact_on', 'severity', 'source_tag', 'confidence'):
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'kb_patterns'
                  AND column_name = %s
            );
        """, (col,))
        col_exists = cur.fetchone()[0]
        print(f"  Column '{col}' exists: {col_exists}")

    cur.close()
    conn.close()

    ok = exists and rls and len(policies) == 2
    print(f"\n  All checks {'PASSED' if ok else 'FAILED'}!")
    return ok


if __name__ == "__main__":
    success = migrate()
    if success:
        verify()
    sys.exit(0 if success else 1)
