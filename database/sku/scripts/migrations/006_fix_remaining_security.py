#!/usr/bin/env python3
"""
Migration 006: Fix Remaining Supabase Security Vulnerabilities

Fixes 9 errors reported by Supabase Security Advisor after migration 005:
- 9 views with SECURITY DEFINER (default) — bypasses RLS (the actual 9 errors)

Also fixes additional security hardening:
- 4 functions without search_path — search path injection risk
- 14 sequences accessible to anon role
- 5 retired lyudmila_* tables with incomplete RLS policies

IMPORTANT: Does NOT affect Python scripts (connect via postgres superuser).
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
    "sslmode": "require"
}

# Our 4 public functions
FUNCTIONS = [
    "log_izmeneniya()",
    "update_updated_at()",
    "get_istoriya_zapisi(character varying, integer)",
    "get_izmeneniya_za_period(timestamp without time zone, timestamp without time zone)",
]

# Our 14 sequences (from SERIAL columns on 14 tables)
SEQUENCES = [
    "artikuly_id_seq",
    "cveta_id_seq",
    "fabriki_id_seq",
    "importery_id_seq",
    "istoriya_izmeneniy_id_seq",
    "kategorii_id_seq",
    "kollekcii_id_seq",
    "modeli_id_seq",
    "modeli_osnova_id_seq",
    "razmery_id_seq",
    "skleyki_ozon_id_seq",
    "skleyki_wb_id_seq",
    "statusy_id_seq",
    "tovary_id_seq",
]

# Retired lyudmila_* tables
LYUDMILA_TABLES = [
    "lyudmila_employees",
    "lyudmila_suggestions",
    "lyudmila_task_comments",
    "lyudmila_tasks",
    "lyudmila_user_preferences",
]

# All 9 views — Security Definer View errors
VIEWS = [
    "v_artikuly_po_cvetam",
    "v_tovary_polnaya_info",
    "v_tricot_nepolnye_cveta",
    "v_statistika_modeli",
    "v_cveta_modeli_osnova",
    "v_modeli_po_osnove",
    "v_statistika_modeli_osnova",
    "v_statistika_cveta",
    "v_matrica_cveta_modeli",
]


def migrate():
    print("=" * 60)
    print("Migration 006: Fix Remaining Security Vulnerabilities")
    print("=" * 60)

    conn = psycopg2.connect(**SUPABASE_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # ============================================
        # STEP 0: Fix views — Security Definer → Security Invoker
        # (these are the actual 9 errors in Supabase Security Advisor)
        # ============================================
        print("\n--- Step 0: Set security_invoker on all views ---")
        for view in VIEWS:
            cur.execute(f"ALTER VIEW public.{view} SET (security_invoker = true);")
            print(f"  security_invoker=true: {view}")

        # ============================================
        # STEP 1: Fix function search_path
        # ============================================
        print("\n--- Step 1: Set search_path on all functions ---")
        for func in FUNCTIONS:
            cur.execute(f"ALTER FUNCTION public.{func} SET search_path = public;")
            print(f"  search_path set: {func}")

        # ============================================
        # STEP 2: Revoke sequence access from anon
        # ============================================
        print("\n--- Step 2: Revoke sequence access from anon ---")
        for seq in SEQUENCES:
            cur.execute(f"REVOKE ALL ON SEQUENCE public.{seq} FROM anon;")
            print(f"  Revoked from anon: {seq}")

        # Also revoke from public role (PostgreSQL default grants)
        cur.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon;")
        cur.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM public;")
        print("  Bulk revoked sequences from anon and public")

        # Prevent future sequence grants to anon
        cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon;")
        cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM public;")
        print("  Default privileges for sequences revoked")

        # ============================================
        # STEP 3: Fix lyudmila_* tables
        # Drop existing anon_deny policies and create proper ones
        # ============================================
        print("\n--- Step 3: Fix lyudmila_* tables (retired agent) ---")
        for table in LYUDMILA_TABLES:
            # Revoke all from anon and authenticated
            cur.execute(f"REVOKE ALL ON public.{table} FROM anon;")
            cur.execute(f"REVOKE ALL ON public.{table} FROM authenticated;")

            # Drop the old anon_deny policy
            policy_name = f"{table}_anon_deny"
            cur.execute(f"DROP POLICY IF EXISTS {policy_name} ON public.{table};")
            print(f"  Dropped old policy: {policy_name}")

            # Create proper policies (same pattern as migration 005)
            # Service role full access
            sr_policy = f"service_role_full_access_{table}"
            cur.execute(f"""
                CREATE POLICY {sr_policy} ON public.{table}
                FOR ALL
                TO postgres
                USING (true)
                WITH CHECK (true);
            """)
            print(f"  Created policy: {sr_policy}")

            # Authenticated SELECT only
            auth_policy = f"authenticated_select_{table}"
            cur.execute(f"""
                CREATE POLICY {auth_policy} ON public.{table}
                FOR SELECT
                TO authenticated
                USING (true);
            """)
            print(f"  Created policy: {auth_policy}")

        # Also revoke sequence access for lyudmila tables
        lyudmila_sequences = [f"{t}_id_seq" for t in LYUDMILA_TABLES]
        for seq in lyudmila_sequences:
            try:
                cur.execute(f"REVOKE ALL ON SEQUENCE public.{seq} FROM anon;")
                cur.execute(f"REVOKE ALL ON SEQUENCE public.{seq} FROM public;")
            except Exception:
                conn.rollback()
                conn.autocommit = False
                # Sequence might not exist, that's OK
                pass
        print("  Lyudmila sequences secured")

        # ============================================
        # STEP 4: Revoke CREATE on public schema from public role
        # ============================================
        print("\n--- Step 4: Revoke CREATE on public schema ---")
        cur.execute("REVOKE CREATE ON SCHEMA public FROM public;")
        print("  CREATE revoked from public role on public schema")

        # Commit all changes
        conn.commit()
        print("\n" + "=" * 60)
        print("ALL REMAINING SECURITY FIXES APPLIED SUCCESSFULLY!")
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
    """Verify that security fixes were applied correctly."""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    conn = psycopg2.connect(**SUPABASE_CONFIG)
    cur = conn.cursor()
    all_ok = True

    # Check view security_invoker
    print("\nView security_invoker:")
    cur.execute("""
        SELECT c.relname,
               COALESCE((SELECT option_value FROM pg_options_to_table(c.reloptions)
                         WHERE option_name = 'security_invoker'), 'false') AS security_invoker
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'v'
        ORDER BY c.relname;
    """)
    for row in cur.fetchall():
        icon = "+" if row[1] == "true" else "!"
        if row[1] != "true":
            all_ok = False
        print(f"  [{icon}] {row[0]:40} security_invoker={row[1]}")

    # Check function search_path
    print("\nFunction search_path:")
    cur.execute("""
        SELECT p.proname,
               pg_catalog.pg_get_function_identity_arguments(p.oid) AS args,
               p.proconfig
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
        ORDER BY p.proname;
    """)
    for row in cur.fetchall():
        config = row[2] if row[2] else []
        has_sp = any("search_path" in str(c) for c in config)
        icon = "+" if has_sp else "!"
        if not has_sp:
            all_ok = False
        print(f"  [{icon}] {row[0]:30} search_path={'SET' if has_sp else 'NOT SET'}")

    # Check sequence grants to anon
    print("\nSequence grants to anon:")
    cur.execute("""
        SELECT s.relname,
               has_sequence_privilege('anon', s.oid, 'USAGE') AS anon_usage
        FROM pg_class s
        JOIN pg_namespace n ON n.oid = s.relnamespace
        WHERE n.nspname = 'public'
          AND s.relkind = 'S'
        ORDER BY s.relname;
    """)
    anon_seq_count = 0
    for row in cur.fetchall():
        if row[1]:
            anon_seq_count += 1
            all_ok = False
            print(f"  [!] {row[0]:40} anon has USAGE")
    if anon_seq_count == 0:
        print("  [+] No sequences accessible to anon — OK")
    else:
        print(f"  [!] {anon_seq_count} sequences still accessible to anon")

    # Check lyudmila policies
    print("\nLyudmila table policies:")
    cur.execute("""
        SELECT tablename, policyname, roles
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename LIKE 'lyudmila_%'
        ORDER BY tablename, policyname;
    """)
    for row in cur.fetchall():
        print(f"  {row[0]:35} {row[1]:50} roles={row[2]}")

    cur.close()
    conn.close()

    if all_ok:
        print("\nAll verification checks PASSED!")
    else:
        print("\nSome checks FAILED — review above.")
    return all_ok


if __name__ == "__main__":
    success = migrate()
    if success:
        verify()
    sys.exit(0 if success else 1)
