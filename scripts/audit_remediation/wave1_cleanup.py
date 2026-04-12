#!/usr/bin/env python3
"""
Wave 1 PIM Cleanup — delete verified junk records with 0 FK dependencies.

Targets:
1. modeli_osnova id=24 (kod="компбел-ж-бесшов") — artikul pattern accidentally stored as model base
2. 16 ghost models in modeli (ids: 42-56, 58) — empty variants with 0 artikuly and 0 tovary

Safety: each DELETE is preceded by a FK check; skips with warning if any refs found.
"""

import os
import sys
from pathlib import Path

# Allow running from project root: python scripts/audit_remediation/wave1_cleanup.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')


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
# FK verification helpers
# ---------------------------------------------------------------------------

def count_modeli_referencing_osnova(cur: psycopg2.extensions.cursor, osnova_id: int) -> int:
    """Return number of modeli rows that reference modeli_osnova.id = osnova_id."""
    cur.execute(
        "SELECT COUNT(*) FROM modeli WHERE model_osnova_id = %s",
        (osnova_id,),
    )
    return cur.fetchone()[0]


def count_artikuly_referencing_model(cur: psycopg2.extensions.cursor, model_id: int) -> int:
    """Return number of artikuly rows that reference modeli.id = model_id."""
    cur.execute(
        "SELECT COUNT(*) FROM artikuly WHERE model_id = %s",
        (model_id,),
    )
    return cur.fetchone()[0]


def count_tovary_referencing_model(cur: psycopg2.extensions.cursor, model_id: int) -> int:
    """Return number of tovary rows that reference modeli.id = model_id via artikuly."""
    cur.execute(
        """
        SELECT COUNT(*)
        FROM tovary t
        JOIN artikuly a ON a.id = t.artikul_id
        WHERE a.model_id = %s
        """,
        (model_id,),
    )
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Pre-deletion state snapshot
# ---------------------------------------------------------------------------

def snapshot_before(cur: psycopg2.extensions.cursor) -> None:
    print("\n=== PRE-DELETION SNAPSHOT ===")

    # modeli_osnova id=24
    cur.execute("SELECT id, kod FROM modeli_osnova WHERE id = 24")
    row = cur.fetchone()
    if row:
        print(f"modeli_osnova id=24: kod='{row[1]}'")
        ref_count = count_modeli_referencing_osnova(cur, 24)
        print(f"  FK refs in modeli: {ref_count}")
    else:
        print("modeli_osnova id=24: NOT FOUND")

    # ghost modeli
    ghost_ids = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 58]
    cur.execute(
        "SELECT id, nazvanie FROM modeli WHERE id = ANY(%s) ORDER BY id",
        (ghost_ids,),
    )
    rows = cur.fetchall()
    print(f"\nGhost modeli found ({len(rows)} of {len(ghost_ids)} expected):")
    for r in rows:
        a = count_artikuly_referencing_model(cur, r[0])
        t = count_tovary_referencing_model(cur, r[0])
        print(f"  id={r[0]:3d} nazvanie='{r[1]}'  artikuly={a}  tovary={t}")
    if not rows:
        print("  (none found)")


# ---------------------------------------------------------------------------
# Deletion with FK guards
# ---------------------------------------------------------------------------

def delete_modeli_osnova_24(cur: psycopg2.extensions.cursor) -> bool:
    """Delete modeli_osnova id=24 if it has 0 FK references. Returns True if deleted."""
    print("\n--- Deleting modeli_osnova id=24 ---")
    ref = count_modeli_referencing_osnova(cur, 24)
    if ref > 0:
        print(f"  WARNING: {ref} modeli rows reference modeli_osnova id=24. SKIPPING.")
        return False

    cur.execute("DELETE FROM modeli_osnova WHERE id = 24")
    deleted = cur.rowcount
    if deleted == 1:
        print("  OK: deleted 1 row from modeli_osnova.")
        return True
    elif deleted == 0:
        print("  WARNING: row not found (already gone?).")
        return False
    else:
        print(f"  ERROR: unexpected rowcount={deleted}.")
        return False


def delete_ghost_modeli(cur: psycopg2.extensions.cursor) -> tuple[int, int]:
    """
    Delete ghost modeli rows one by one with FK checks.

    Returns (deleted_count, skipped_count).
    """
    ghost_ids = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 58]
    print(f"\n--- Deleting {len(ghost_ids)} ghost modeli rows ---")

    deleted = 0
    skipped = 0

    for mid in ghost_ids:
        artikuly_count = count_artikuly_referencing_model(cur, mid)
        tovary_count = count_tovary_referencing_model(cur, mid)

        if artikuly_count > 0 or tovary_count > 0:
            print(
                f"  id={mid:3d}: WARNING — artikuly={artikuly_count}, tovary={tovary_count}. SKIPPING."
            )
            skipped += 1
            continue

        cur.execute("DELETE FROM modeli WHERE id = %s", (mid,))
        rc = cur.rowcount
        if rc == 1:
            print(f"  id={mid:3d}: deleted.")
            deleted += 1
        else:
            print(f"  id={mid:3d}: not found (rowcount={rc}), skipping.")
            skipped += 1

    return deleted, skipped


# ---------------------------------------------------------------------------
# Post-deletion verification snapshot
# ---------------------------------------------------------------------------

def snapshot_after(cur: psycopg2.extensions.cursor) -> None:
    print("\n=== POST-DELETION SNAPSHOT ===")

    cur.execute("SELECT COUNT(*) FROM modeli_osnova WHERE id = 24")
    cnt = cur.fetchone()[0]
    print(f"modeli_osnova id=24 remaining rows: {cnt} (expected 0)")

    ghost_ids = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 58]
    cur.execute(
        "SELECT COUNT(*) FROM modeli WHERE id = ANY(%s)",
        (ghost_ids,),
    )
    cnt = cur.fetchone()[0]
    print(f"Ghost modeli remaining rows: {cnt} (expected 0)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Wave 1 PIM Cleanup — starting")
    print("=" * 50)

    conn = get_connection()
    try:
        with conn:  # transaction block; auto-commits on exit, rolls back on exception
            with conn.cursor() as cur:
                snapshot_before(cur)

                print("\n=== EXECUTING DELETIONS ===")
                osnova_deleted = delete_modeli_osnova_24(cur)
                modeli_deleted, modeli_skipped = delete_ghost_modeli(cur)

                print("\n=== SUMMARY ===")
                print(f"modeli_osnova id=24: {'deleted' if osnova_deleted else 'skipped/not found'}")
                print(f"ghost modeli: {modeli_deleted} deleted, {modeli_skipped} skipped")

                snapshot_after(cur)

                if modeli_skipped > 0 or not osnova_deleted:
                    print(
                        "\nDONE_WITH_CONCERNS: some records were skipped — see warnings above."
                    )
                else:
                    print("\nDONE: all targeted records deleted successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
