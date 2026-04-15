#!/usr/bin/env python3
"""
Task 3 — Replace 10 placeholder barcodes with real GS1 values from Sheet snapshot.

Placeholder barcodes are 1-2 digit numbers (e.g. "7", "9", "18") stored in
tovary.barkod instead of real 13-digit GS1 barcodes.

Root cause: each artikul has 3 sizes (S/M/L). The Sheet's БАРКОД column only
populated S and M sizes; L rows contain the same placeholder integers. However
БАРКОД GS1 and БАРКОД GS2 columns have valid 13-digit GS1 barcodes for all sizes.

Strategy:
1. For each bad row, look up the Sheet row matching the same artikul + size.
2. Try columns in order: БАРКОД, БАРКОД GS1, БАРКОД GS2 — pick first valid
   numeric barcode (>=10 digits) not already in DB.
3. UPDATE tovary.barkod; skip with warning if none found.

Source of truth: /tmp/sheet-audit-snapshot.json (vse_tovary sheet).
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SNAPSHOT_PATH = Path("/tmp/sheet-audit-snapshot.json")

# (tovary.id, artikul, razmer) — all three used for precise Sheet lookup
BAD_BARCODE_ROWS: list[tuple[int, str, str]] = [
    (112, "компбел-ж-бесшов/желт",    "L"),
    (115, "компбел-ж-бесшов/темнфиол", "L"),
    (121, "компбел-ж-бесшов/салат",    "L"),
    (124, "компбел-ж-бесшов/фиол",     "L"),
    (127, "компбел-ж-бесшов/лосос",    "L"),
    (637, "Joy/blue_6",                "L"),
    (640, "Joy/date_red2",             "L"),
    (643, "Joy/yellow",                "L"),
    (653, "Joy/rose_pink",             "L"),
    (695, "Joy/watermelon_red",        "L"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_connection() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=os.getenv("SUPABASE_HOST", "aws-1-ap-northeast-2.pooler.supabase.com"),
        port=int(os.getenv("SUPABASE_PORT", "5432")),
        database=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER", "postgres"),
        password=os.getenv("SUPABASE_PASSWORD", ""),
    )


def is_valid_barcode(value: str) -> bool:
    """Return True if value looks like a real GS1 barcode (numeric, >=10 digits)."""
    return bool(value) and len(value) >= 10 and value.isdigit()


def load_sheet_lookup() -> dict[tuple[str, str], list[str]]:
    """Return (artikul, razmer) -> [valid barcodes] from Sheet snapshot.

    Tries barcode columns in priority order: БАРКОД, БАРКОД GS1, БАРКОД GS2.
    """
    with SNAPSHOT_PATH.open(encoding="utf-8") as f:
        data = json.load(f)

    sheet = data["vse_tovary"]
    headers: list[str] = sheet["headers"]
    rows: list[list] = sheet["rows"]

    # Column indices — note the trailing space on "БАРКОД "
    barkod_idx   = headers.index("БАРКОД ")
    gs1_idx      = headers.index("БАРКОД GS1")
    gs2_idx      = headers.index("БАРКОД GS2")
    artikul_idx  = headers.index("Артикул")
    razmer_idx   = headers.index("Размер")

    result: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        max_idx = max(barkod_idx, gs1_idx, gs2_idx, artikul_idx, razmer_idx)
        if len(row) <= max_idx:
            continue
        artikul = str(row[artikul_idx]).strip()
        razmer  = str(row[razmer_idx]).strip()

        for col_idx in (barkod_idx, gs1_idx, gs2_idx):
            val = str(row[col_idx]).strip() if len(row) > col_idx else ""
            if is_valid_barcode(val):
                result.setdefault((artikul, razmer), []).append(val)

    return result


def get_existing_barcodes(cur: psycopg2.extensions.cursor) -> set[str]:
    """Return all non-placeholder barcodes currently in tovary."""
    cur.execute(
        "SELECT barkod FROM tovary WHERE barkod IS NOT NULL AND length(barkod) >= 10"
    )
    return {row[0] for row in cur.fetchall()}


def get_db_razmer(cur: psycopg2.extensions.cursor, tovary_id: int) -> Optional[str]:
    """Return the razmer name for a tovary row."""
    cur.execute(
        """
        SELECT r.nazvanie
        FROM tovary t
        LEFT JOIN razmery r ON r.id = t.razmer_id
        WHERE t.id = %s
        """,
        (tovary_id,),
    )
    row = cur.fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    sheet_lookup = load_sheet_lookup()
    print(f"Loaded Sheet snapshot: {len(sheet_lookup)} (artikul, razmer) entries with barcodes")

    conn = get_connection()
    try:
        cur = conn.cursor()
        existing_barcodes = get_existing_barcodes(cur)
        print(f"Existing valid barcodes in DB: {len(existing_barcodes)}")
        print()

        updated = 0
        skipped = 0

        for tovary_id, artikul, expected_razmer in BAD_BARCODE_ROWS:
            # Verify current barcode is still a placeholder
            cur.execute("SELECT barkod FROM tovary WHERE id = %s", (tovary_id,))
            row = cur.fetchone()
            if row is None:
                print(f"  SKIP  id={tovary_id} — row not found in DB")
                skipped += 1
                continue

            current_barkod = row[0]
            if is_valid_barcode(current_barkod or ""):
                print(
                    f"  SKIP  id={tovary_id} ({artikul}/{expected_razmer}) "
                    f"— already has valid barcode {current_barkod!r}"
                )
                skipped += 1
                continue

            # Confirm DB razmer matches expectation
            db_razmer = get_db_razmer(cur, tovary_id)
            if db_razmer and db_razmer != expected_razmer:
                print(
                    f"  WARN  id={tovary_id} ({artikul}) "
                    f"— DB razmer={db_razmer!r}, expected {expected_razmer!r}; proceeding"
                )
            razmer_key = db_razmer or expected_razmer

            # Find a real barcode from Sheet not already used in DB
            candidates = sheet_lookup.get((artikul, razmer_key), [])
            if not candidates:
                # Fallback: try expected_razmer if db_razmer differed
                candidates = sheet_lookup.get((artikul, expected_razmer), [])
            if not candidates:
                print(
                    f"  WARN  id={tovary_id} ({artikul}/{razmer_key}) "
                    f"— no valid barcodes found in Sheet for this artikul+size, skipping"
                )
                skipped += 1
                continue

            chosen: Optional[str] = None
            for candidate in candidates:
                if candidate not in existing_barcodes:
                    chosen = candidate
                    break

            if chosen is None:
                print(
                    f"  WARN  id={tovary_id} ({artikul}/{razmer_key}) "
                    f"— all Sheet barcodes already in DB ({candidates}), skipping"
                )
                skipped += 1
                continue

            # Apply UPDATE
            cur.execute(
                "UPDATE tovary SET barkod = %s, updated_at = NOW() WHERE id = %s",
                (chosen, tovary_id),
            )
            existing_barcodes.add(chosen)  # prevent re-use within this run
            print(
                f"  UPDATE id={tovary_id} ({artikul}/{razmer_key}): "
                f"{current_barkod!r} -> {chosen!r}"
            )
            updated += 1

        conn.commit()
        print(f"\nDone: {updated} updated, {skipped} skipped")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
