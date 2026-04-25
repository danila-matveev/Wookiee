#!/usr/bin/env python3
"""
Wave 3 Schema Migration — create `infra` schema and move 7 infrastructure tables from `public`.

Tables to migrate:
1. kb_chunks           (text vector KB, ~7 091 rows)
2. content_assets      (photo vector KB, ~10 146 rows)
3. field_definitions   (Product Matrix API schema, ~44 rows)
4. istoriya_izmeneniy  (PIM audit log from triggers, ~4 014 rows)
5. archive_records     (dormant soft-delete mechanism, 0 rows)
6. agent_runs          (observability logs, ~650 rows)
7. orchestrator_runs   (observability logs, ~130 rows)

After migration:
- `ALTER ROLE service_role SET search_path TO public, infra` ensures unqualified table names
  (e.g. SELECT * FROM kb_chunks) continue to resolve without any code changes.
- All indexes, constraints, triggers, sequences are preserved by ALTER TABLE SET SCHEMA.
"""

import os
import sys
from pathlib import Path

# Allow running from project root: python scripts/audit_remediation/wave3_schema_migration.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


# ---------------------------------------------------------------------------
# Tables to migrate (order matters if there are FK deps — none expected here)
# ---------------------------------------------------------------------------

TABLES_TO_MIGRATE = [
    "kb_chunks",
    "content_assets",
    "field_definitions",
    "istoriya_izmeneniy",
    "archive_records",
    "agent_runs",
    "orchestrator_runs",
]


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=os.getenv("SUPABASE_HOST", "aws-1-ap-northeast-2.pooler.supabase.com"),
        port=int(os.getenv("SUPABASE_PORT", "5432")),
        database=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER", "postgres"),
        password=os.getenv("SUPABASE_PASSWORD", ""),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def table_exists(cur: psycopg2.extensions.cursor, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        )
        """,
        (schema, table),
    )
    return cur.fetchone()[0]


def count_rows(cur: psycopg2.extensions.cursor, schema: str, table: str) -> int:
    cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Phase 1: Pre-migration snapshot
# ---------------------------------------------------------------------------

def snapshot_before(cur: psycopg2.extensions.cursor) -> dict[str, int]:
    """Check current state and return {table: row_count} for tables found in public."""
    print("\n=== PRE-MIGRATION SNAPSHOT ===")
    counts: dict[str, int] = {}
    for tbl in TABLES_TO_MIGRATE:
        in_public = table_exists(cur, "public", tbl)
        in_infra = table_exists(cur, "infra", tbl)
        if in_public:
            cnt = count_rows(cur, "public", tbl)
            counts[tbl] = cnt
            print(f"  public.{tbl}: {cnt} rows")
        elif in_infra:
            cnt = count_rows(cur, "infra", tbl)
            counts[tbl] = cnt
            print(f"  infra.{tbl}: {cnt} rows  (already migrated)")
        else:
            print(f"  {tbl}: NOT FOUND in public or infra  — will skip")
    return counts


# ---------------------------------------------------------------------------
# Phase 2: Create infra schema + grants
# ---------------------------------------------------------------------------

def create_infra_schema(cur: psycopg2.extensions.cursor) -> None:
    print("\n=== CREATING SCHEMA infra ===")
    cur.execute("CREATE SCHEMA IF NOT EXISTS infra")
    print("  CREATE SCHEMA IF NOT EXISTS infra — OK")

    # Grant usage to the roles that Supabase uses
    for role in ("postgres", "service_role", "anon", "authenticated"):
        cur.execute(f'GRANT USAGE ON SCHEMA infra TO "{role}"')
        print(f"  GRANT USAGE ON SCHEMA infra TO {role} — OK")

    # Allow all privileges on future tables to service_role
    cur.execute('GRANT ALL ON ALL TABLES IN SCHEMA infra TO "service_role"')
    print("  GRANT ALL ON ALL TABLES IN SCHEMA infra TO service_role — OK")

    cur.execute(
        'ALTER DEFAULT PRIVILEGES IN SCHEMA infra GRANT ALL ON TABLES TO "service_role"'
    )
    print("  ALTER DEFAULT PRIVILEGES ... GRANT ALL ON TABLES TO service_role — OK")


# ---------------------------------------------------------------------------
# Phase 3: Migrate tables one by one
# ---------------------------------------------------------------------------

def migrate_tables(cur: psycopg2.extensions.cursor) -> tuple[list[str], list[str], list[str]]:
    """
    Move each table from public to infra.

    Returns (migrated, skipped, failed).
    """
    print("\n=== MIGRATING TABLES ===")
    migrated: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    for tbl in TABLES_TO_MIGRATE:
        in_public = table_exists(cur, "public", tbl)
        in_infra = table_exists(cur, "infra", tbl)

        if in_infra:
            print(f"  {tbl}: already in infra — skipping")
            skipped.append(tbl)
            continue

        if not in_public:
            print(f"  {tbl}: NOT FOUND in public — skipping (may have been dropped)")
            skipped.append(tbl)
            continue

        try:
            cur.execute(f'ALTER TABLE public."{tbl}" SET SCHEMA infra')
            print(f"  {tbl}: moved public → infra — OK")
            migrated.append(tbl)
        except Exception as exc:
            print(f"  {tbl}: FAILED — {exc}")
            failed.append(tbl)

    return migrated, skipped, failed


# ---------------------------------------------------------------------------
# Phase 4: Set search_path so unqualified names resolve
# ---------------------------------------------------------------------------

def set_search_path(cur: psycopg2.extensions.cursor) -> None:
    print("\n=== SETTING search_path ===")
    # Set for the connection role (postgres user used by our app)
    cur.execute(
        "ALTER ROLE \"postgres\" SET search_path TO public, infra"
    )
    print("  ALTER ROLE postgres SET search_path TO public, infra — OK")

    cur.execute(
        "ALTER ROLE \"service_role\" SET search_path TO public, infra"
    )
    print("  ALTER ROLE service_role SET search_path TO public, infra — OK")

    # Also set for authenticated/anon in case they need read access
    try:
        cur.execute(
            "ALTER ROLE \"authenticated\" SET search_path TO public, infra"
        )
        print("  ALTER ROLE authenticated SET search_path TO public, infra — OK")
    except Exception as exc:
        print(f"  ALTER ROLE authenticated: skipped — {exc}")

    try:
        cur.execute(
            "ALTER ROLE \"anon\" SET search_path TO public, infra"
        )
        print("  ALTER ROLE anon SET search_path TO public, infra — OK")
    except Exception as exc:
        print(f"  ALTER ROLE anon: skipped — {exc}")


# ---------------------------------------------------------------------------
# Phase 5: Post-migration verification
# ---------------------------------------------------------------------------

def verify_migration(
    cur: psycopg2.extensions.cursor,
    before_counts: dict[str, int],
    migrated: list[str],
) -> bool:
    """
    Verify:
    1. Each migrated table exists in infra schema.
    2. Row counts match pre-migration counts.
    3. Unqualified SELECT still works (search_path resolution).

    Returns True if all checks pass.
    """
    print("\n=== VERIFICATION ===")
    all_ok = True

    # Set search_path for current session too so unqualified queries work
    cur.execute("SET search_path TO public, infra")

    for tbl in migrated:
        in_infra = table_exists(cur, "infra", tbl)
        in_public = table_exists(cur, "public", tbl)

        if not in_infra:
            print(f"  {tbl}: FAIL — not found in infra schema!")
            all_ok = False
            continue

        if in_public:
            print(f"  {tbl}: WARN — still exists in public (unexpected duplicate)")

        infra_count = count_rows(cur, "infra", tbl)
        expected = before_counts.get(tbl, -1)
        count_ok = (infra_count == expected)
        count_msg = f"rows: {infra_count} (expected {expected}) {'OK' if count_ok else 'MISMATCH'}"

        # Unqualified access test
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{tbl}"')
            unqualified_count = cur.fetchone()[0]
            unqualified_ok = (unqualified_count == infra_count)
            unqualified_msg = f"unqualified SELECT: {unqualified_count} {'OK' if unqualified_ok else 'MISMATCH'}"
        except Exception as exc:
            unqualified_ok = False
            unqualified_msg = f"unqualified SELECT: FAIL — {exc}"

        status = "OK" if (count_ok and unqualified_ok) else "FAIL"
        print(f"  {tbl}: {status} — {count_msg}, {unqualified_msg}")

        if not count_ok or not unqualified_ok:
            all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# Post-migration snapshot
# ---------------------------------------------------------------------------

def snapshot_after(cur: psycopg2.extensions.cursor) -> None:
    print("\n=== POST-MIGRATION SNAPSHOT ===")
    print("Tables in infra schema:")
    cur.execute(
        """
        SELECT table_name, pg_size_pretty(pg_total_relation_size(
            quote_ident(table_schema) || '.' || quote_ident(table_name)
        )) AS size
        FROM information_schema.tables
        WHERE table_schema = 'infra'
        ORDER BY table_name
        """
    )
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  infra.{r[0]}  ({r[1]})")
    else:
        print("  (none)")

    print("\nTables remaining in public (target tables only):")
    for tbl in TABLES_TO_MIGRATE:
        in_public = table_exists(cur, "public", tbl)
        if in_public:
            print(f"  public.{tbl}  (still present — check manually)")
    print("  (check complete)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Wave 3 Schema Migration — starting")
    print("=" * 60)

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                before_counts = snapshot_before(cur)

                create_infra_schema(cur)

                migrated, skipped, failed = migrate_tables(cur)

                set_search_path(cur)

                all_ok = verify_migration(cur, before_counts, migrated)

                snapshot_after(cur)

                print("\n=== SUMMARY ===")
                print(f"  Migrated : {len(migrated)} tables — {migrated}")
                print(f"  Skipped  : {len(skipped)} tables — {skipped}")
                print(f"  Failed   : {len(failed)} tables — {failed}")
                print(f"  Verification: {'PASS' if all_ok else 'FAIL'}")

                if failed:
                    print("\nDONE_WITH_CONCERNS: some tables failed to migrate — see output above.")
                elif not all_ok:
                    print("\nDONE_WITH_CONCERNS: migration complete but verification found issues.")
                else:
                    print("\nDONE: all tables migrated and verified successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
