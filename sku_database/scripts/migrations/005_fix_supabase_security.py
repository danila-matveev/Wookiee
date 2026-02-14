#!/usr/bin/env python3
"""
Migration 005: Fix Supabase Security Vulnerabilities

Fixes 25 security errors reported by Supabase Security Advisor:
- Enables RLS on ALL 16 tables
- Revokes excessive privileges from anon and authenticated roles
- Creates appropriate RLS policies (service_role only for writes)
- Secures public functions

IMPORTANT: This does NOT affect the Python scripts that connect via
postgres user (service_role) — RLS does not apply to superuser/service_role.
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

# All base tables in public schema
TABLES = [
    "kategorii",
    "kollekcii",
    "statusy",
    "razmery",
    "importery",
    "fabriki",
    "cveta",
    "modeli_osnova",
    "modeli",
    "skleyki_wb",
    "skleyki_ozon",
    "artikuly",
    "tovary",
    "tovary_skleyki_wb",
    "tovary_skleyki_ozon",
    "istoriya_izmeneniy",
]

# All views in public schema
VIEWS = [
    "v_tovary_polnaya_info",
    "v_statistika_modeli_osnova",
    "v_statistika_modeli",
    "v_statistika_cveta",
    "v_modeli_po_osnove",
    "v_cveta_modeli_osnova",
    "v_artikuly_po_cvetam",
    "v_matrica_cveta_modeli",
    "v_tricot_nepolnye_cveta",
]

# Public functions
FUNCTIONS = [
    "log_izmeneniya()",
    "update_updated_at()",
    "get_istoriya_zapisi(VARCHAR, INT)",
    "get_izmeneniya_za_period(TIMESTAMP, TIMESTAMP)",
]


def migrate():
    print("=" * 60)
    print("Migration 005: Fix Supabase Security Vulnerabilities")
    print("=" * 60)

    conn = psycopg2.connect(**SUPABASE_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # ============================================
        # STEP 1: Enable RLS on ALL tables
        # ============================================
        print("\n--- Step 1: Enable RLS on all tables ---")
        for table in TABLES:
            cur.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;")
            print(f"  RLS enabled: {table}")

        # ============================================
        # STEP 2: Revoke ALL privileges from anon on tables
        # ============================================
        print("\n--- Step 2: Revoke privileges from anon ---")
        for table in TABLES:
            cur.execute(f"REVOKE ALL ON public.{table} FROM anon;")
            print(f"  Revoked from anon: {table}")

        for view in VIEWS:
            cur.execute(f"REVOKE ALL ON public.{view} FROM anon;")
            print(f"  Revoked from anon: {view}")

        # ============================================
        # STEP 3: Revoke write privileges from authenticated,
        #         keep SELECT only
        # ============================================
        print("\n--- Step 3: Restrict authenticated to SELECT only ---")
        for table in TABLES:
            cur.execute(f"REVOKE ALL ON public.{table} FROM authenticated;")
            cur.execute(f"GRANT SELECT ON public.{table} TO authenticated;")
            print(f"  authenticated SELECT only: {table}")

        for view in VIEWS:
            cur.execute(f"REVOKE ALL ON public.{view} FROM authenticated;")
            cur.execute(f"GRANT SELECT ON public.{view} TO authenticated;")
            print(f"  authenticated SELECT only: {view}")

        # ============================================
        # STEP 4: Create RLS policies
        # ============================================
        print("\n--- Step 4: Create RLS policies ---")

        for table in TABLES:
            # Policy: service_role gets full access
            policy_name = f"service_role_full_access_{table}"
            cur.execute(f"""
                CREATE POLICY {policy_name} ON public.{table}
                FOR ALL
                TO postgres
                USING (true)
                WITH CHECK (true);
            """)
            print(f"  Policy created (postgres full): {table}")

            # Policy: authenticated can SELECT
            policy_name_auth = f"authenticated_select_{table}"
            cur.execute(f"""
                CREATE POLICY {policy_name_auth} ON public.{table}
                FOR SELECT
                TO authenticated
                USING (true);
            """)
            print(f"  Policy created (authenticated select): {table}")

        # ============================================
        # STEP 5: Secure functions — revoke EXECUTE from anon
        # ============================================
        print("\n--- Step 5: Secure functions ---")
        for func in FUNCTIONS:
            cur.execute(f"REVOKE EXECUTE ON FUNCTION public.{func} FROM anon;")
            cur.execute(f"REVOKE EXECUTE ON FUNCTION public.{func} FROM public;")
            print(f"  Secured function: {func}")

        # ============================================
        # STEP 6: Revoke default privileges for future objects
        # ============================================
        print("\n--- Step 6: Revoke default privileges for future objects ---")
        cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon;")
        cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon;")
        cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon;")
        print("  Default privileges revoked for anon")

        # Commit all changes
        conn.commit()
        print("\n" + "=" * 60)
        print("ALL SECURITY FIXES APPLIED SUCCESSFULLY!")
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

    # Check RLS status
    cur.execute("""
        SELECT tablename, rowsecurity
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename;
    """)
    print("\nRLS Status:")
    all_rls_ok = True
    for row in cur.fetchall():
        status = "ENABLED" if row[1] else "DISABLED"
        icon = "+" if row[1] else "!"
        if not row[1]:
            all_rls_ok = False
        print(f"  [{icon}] {row[0]:35} {status}")

    # Check policies
    cur.execute("""
        SELECT tablename, COUNT(*)
        FROM pg_policies
        WHERE schemaname = 'public'
        GROUP BY tablename
        ORDER BY tablename;
    """)
    print("\nRLS Policies per table:")
    for row in cur.fetchall():
        print(f"  {row[0]:35} {row[1]} policies")

    # Check anon grants
    cur.execute("""
        SELECT table_name, privilege_type
        FROM information_schema.table_privileges
        WHERE table_schema = 'public'
        AND grantee = 'anon'
        ORDER BY table_name;
    """)
    anon_grants = cur.fetchall()
    print(f"\nAnon grants remaining: {len(anon_grants)}")
    if anon_grants:
        for g in anon_grants:
            print(f"  WARNING: {g[0]} — {g[1]}")

    # Check authenticated grants
    cur.execute("""
        SELECT table_name, privilege_type
        FROM information_schema.table_privileges
        WHERE table_schema = 'public'
        AND grantee = 'authenticated'
        AND privilege_type != 'SELECT'
        ORDER BY table_name;
    """)
    auth_non_select = cur.fetchall()
    print(f"\nAuthenticated non-SELECT grants remaining: {len(auth_non_select)}")
    if auth_non_select:
        for g in auth_non_select:
            print(f"  WARNING: {g[0]} — {g[1]}")

    cur.close()
    conn.close()

    if all_rls_ok and len(anon_grants) == 0 and len(auth_non_select) == 0:
        print("\nAll security checks PASSED!")
        return True
    else:
        print("\nSome checks FAILED — review above.")
        return False


if __name__ == "__main__":
    success = migrate()
    if success:
        verify()
    sys.exit(0 if success else 1)
