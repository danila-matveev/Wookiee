#!/usr/bin/env python3
"""
Delete 28 legacy modeli rows with Russian descriptive names (col-C sync bug remnants).

All targeted rows have 0 artikuly and 0 tovary. Most have correct short-code
counterparts already in the table.

IDs to delete:
57, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 82, 84, 86, 88,
90, 92, 94, 96, 98, 100, 102, 104, 106, 108, 112, 113

Safety: each DELETE is preceded by a per-record FK check;
skips with warning if any refs found.
"""

import os
import sys
from pathlib import Path

# Allow running from project root: python scripts/audit_remediation/delete_legacy_models.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# ---------------------------------------------------------------------------
# Target IDs
# ---------------------------------------------------------------------------

LEGACY_IDS: list[int] = [
    57, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 82, 84, 86, 88,
    90, 92, 94, 96, 98, 100, 102, 104, 106, 108, 112, 113,
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
# FK verification helpers
# ---------------------------------------------------------------------------

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

    cur.execute(
        "SELECT id, nazvanie FROM modeli WHERE id = ANY(%s) ORDER BY id",
        (LEGACY_IDS,),
    )
    rows = cur.fetchall()
    print(f"Legacy modeli found ({len(rows)} of {len(LEGACY_IDS)} expected):")
    for r in rows:
        a = count_artikuly_referencing_model(cur, r[0])
        t = count_tovary_referencing_model(cur, r[0])
        print(f"  id={r[0]:3d}  nazvanie='{r[1]}'  artikuly={a}  tovary={t}")

    if not rows:
        print("  (none found — already cleaned?)")

    # Overall modeli count before deletion
    cur.execute("SELECT COUNT(*) FROM modeli")
    total = cur.fetchone()[0]
    print(f"\nTotal modeli rows (before): {total}")

    # NULL osnova check
    cur.execute("SELECT COUNT(*) FROM modeli WHERE model_osnova_id IS NULL")
    null_osnova = cur.fetchone()[0]
    print(f"Rows with NULL model_osnova_id (before): {null_osnova}")


# ---------------------------------------------------------------------------
# Deletion with FK guards
# ---------------------------------------------------------------------------

def delete_legacy_modeli(cur: psycopg2.extensions.cursor) -> tuple[int, int]:
    """
    Delete legacy modeli rows one by one with FK checks.

    Returns (deleted_count, skipped_count).
    """
    print(f"\n--- Deleting {len(LEGACY_IDS)} legacy modeli rows ---")

    deleted = 0
    skipped = 0

    for mid in LEGACY_IDS:
        artikuly_count = count_artikuly_referencing_model(cur, mid)
        tovary_count = count_tovary_referencing_model(cur, mid)

        if artikuly_count > 0 or tovary_count > 0:
            print(
                f"  id={mid:3d}: WARNING — artikuly={artikuly_count}, "
                f"tovary={tovary_count}. SKIPPING."
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

    cur.execute(
        "SELECT COUNT(*) FROM modeli WHERE id = ANY(%s)",
        (LEGACY_IDS,),
    )
    remaining = cur.fetchone()[0]
    print(f"Legacy modeli remaining rows: {remaining} (expected 0)")

    cur.execute("SELECT COUNT(*) FROM modeli")
    total = cur.fetchone()[0]
    print(f"Total modeli rows (after): {total}")

    cur.execute("SELECT COUNT(*) FROM modeli WHERE model_osnova_id IS NULL")
    null_osnova = cur.fetchone()[0]
    print(f"Rows with NULL model_osnova_id (after): {null_osnova} (expected 0)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Delete 28 Legacy Models (col-C bug remnants) — starting")
    print("=" * 60)

    conn = get_connection()
    try:
        with conn:  # transaction block; auto-commits on exit, rolls back on exception
            with conn.cursor() as cur:
                snapshot_before(cur)

                print("\n=== EXECUTING DELETIONS ===")
                deleted, skipped = delete_legacy_modeli(cur)

                print("\n=== SUMMARY ===")
                print(f"Deleted: {deleted}  Skipped: {skipped}  Target: {len(LEGACY_IDS)}")

                snapshot_after(cur)

                if skipped > 0:
                    print(
                        "\nDONE_WITH_CONCERNS: some records were skipped — see warnings above."
                    )
                else:
                    print("\nDONE: all 28 legacy models deleted successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
