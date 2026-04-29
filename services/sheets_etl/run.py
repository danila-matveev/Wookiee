"""CLI orchestrator: pull → transform → upsert all CRM sheets in dependency order.

Usage:
    .venv/bin/python -m services.sheets_etl.run [--sheet NAME]
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from services.sheets_etl.article_resolver import ArticleResolver
from services.sheets_etl.config import SPREADSHEET_ID
from services.sheets_etl.fetch import read_range
from services.sheets_etl.hash import sheet_row_id
from services.sheets_etl.incremental import existing_sheet_row_ids, filter_new_rows
from services.sheets_etl.loader import get_conn, insert_junction, upsert
from services.sheets_etl.transformers import (
    bloggers as t_bloggers,
)
from services.sheets_etl.transformers import (
    candidates as t_candidates,
)
from services.sheets_etl.transformers import (
    integrations as t_integrations,
)
from services.sheets_etl.transformers import (
    promo_codes as t_promo,
)
from services.sheets_etl.transformers import (
    substitute_articles as t_subs,
)


def run_promo_codes(conn, incremental: bool = False) -> int:
    rows = t_promo.transform(read_range(SPREADSHEET_ID, "Промокоды_справочник!A1:G1000"))
    if incremental:
        existing = existing_sheet_row_ids(conn, "crm.promo_codes")
        rows = filter_new_rows(rows, existing)
    # `code` — business key. Stable across hash-algo changes; if Sheets row
    # moves and gets a new sheet_row_id, the same code still maps to the same
    # DB row. Avoids UniqueViolation on uq_promo_code when telemetry hashing
    # evolves between phases.
    return upsert(conn, "crm.promo_codes", rows, conflict_col="code")


def run_bloggers(conn, incremental: bool = False) -> tuple[int, int]:
    bloggers, channels = t_bloggers.transform(
        read_range(SPREADSHEET_ID, "БД БЛОГЕРЫ!A1:G2000")
    )
    if incremental:
        existing = existing_sheet_row_ids(conn, "crm.bloggers")
        bloggers = filter_new_rows(bloggers, existing)
    n_b = upsert(conn, "crm.bloggers", bloggers)
    handle_to_id = _resolve_handles(conn)
    ch_rows = []
    for c in channels:
        bid = handle_to_id.get(c["display_handle_ref"].lower())
        if not bid:
            continue
        ch_rows.append({
            "blogger_id": bid,
            "channel": c["channel"],
            "handle": c["handle"],
            "url": c["url"],
            "followers": c["followers"],
        })
    n_c = insert_junction(
        conn,
        "crm.blogger_channels",
        ch_rows,
        conflict_target_sql="(channel, (LOWER(handle)))",
    )
    return n_b, n_c


def _ensure_substitute_article(conn, code: str, artikul_id: int, purpose: str = "creators") -> int:
    """Find or create crm.substitute_articles row by artikul_id. Returns id."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM crm.substitute_articles WHERE artikul_id = %s LIMIT 1",
            (artikul_id,),
        )
        row = cur.fetchone()
        if row:
            return row[0]
        srid = sheet_row_id([code, str(artikul_id)])
        cur.execute(
            """
            INSERT INTO crm.substitute_articles
                (code, artikul_id, purpose, status, sheet_row_id)
            VALUES (%s, %s, %s, 'active', %s)
            ON CONFLICT (sheet_row_id) DO UPDATE SET artikul_id = EXCLUDED.artikul_id
            RETURNING id
            """,
            (code, artikul_id, purpose, srid),
        )
        new_id = cur.fetchone()[0]
    conn.commit()
    return new_id


def run_substitute_articles(conn, incremental: bool = False) -> tuple[int, int, int]:
    articles, metrics = t_subs.transform(
        read_range(SPREADSHEET_ID, "Подменные!A1:HZ1500")
    )
    resolver = ArticleResolver(conn)

    matched: list[dict[str, Any]] = []
    unmatched: list[str] = []
    for a in articles:
        art_id = resolver.resolve_one(a["code"])
        if art_id is not None:
            a["artikul_id"] = art_id
            matched.append(a)
        else:
            unmatched.append(a["code"])
    if incremental:
        existing = existing_sheet_row_ids(conn, "crm.substitute_articles")
        matched = filter_new_rows(matched, existing)
    # See run_promo_codes — same uq_<entity>_code constraint exists here.
    n_a = upsert(conn, "crm.substitute_articles", matched, conflict_col="code")

    code_to_id: dict[str, int] = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, code FROM crm.substitute_articles")
        code_to_id = {c.lower(): i for i, c in cur.fetchall()}
    metric_rows = []
    for m in metrics:
        sub_id = code_to_id.get(m["sub_code_ref"].lower())
        if not sub_id:
            continue
        metric_rows.append({
            "substitute_article_id": sub_id,
            "week_start": m["week_start"],
            "frequency": m["frequency"],
            "transitions": m["transitions"],
            "additions": m["additions"],
            "orders": m["orders"],
        })
    n_m = insert_junction(
        conn,
        "crm.substitute_article_metrics_weekly",
        metric_rows,
        conflict_cols=("substitute_article_id", "week_start"),
    )
    print(f"  unmatched substitute codes: {len(unmatched)}")
    if unmatched:
        print(f"  sample: {unmatched[:5]}")
    return n_a, n_m, len(unmatched)


def _ensure_blogger(conn, display_handle: str) -> int:
    """Find or create crm.bloggers row. Returns id."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM crm.bloggers WHERE LOWER(display_handle) = LOWER(%s) LIMIT 1",
            (display_handle,),
        )
        row = cur.fetchone()
        if row:
            return row[0]
        srid = sheet_row_id([display_handle])
        cur.execute(
            """
            INSERT INTO crm.bloggers (display_handle, status, sheet_row_id)
            VALUES (%s, 'active', %s)
            ON CONFLICT (sheet_row_id) DO UPDATE SET display_handle = EXCLUDED.display_handle
            RETURNING id
            """,
            (display_handle, srid),
        )
        new_id = cur.fetchone()[0]
    conn.commit()
    return new_id


def run_integrations(conn, incremental: bool = False) -> tuple[int, int, int]:
    integrations, sub_links = t_integrations.transform(
        read_range(SPREADSHEET_ID, "Блогеры!A1:CL2000")
    )

    # Step 1: marketers map
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM crm.marketers")
        marketers = {n: i for i, n in cur.fetchall()}

    # Step 2: ensure every blogger from integrations exists in crm.bloggers
    unique_handles = {r["blogger_handle_ref"] for r in integrations}
    created_bloggers = 0
    handle_to_id: dict[str, int] = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, LOWER(display_handle) FROM crm.bloggers")
        existing = {h: i for i, h in cur.fetchall()}
    for h in unique_handles:
        h_lower = h.lower()
        if h_lower in existing:
            handle_to_id[h_lower] = existing[h_lower]
            continue
        new_id = _ensure_blogger(conn, h)
        handle_to_id[h_lower] = new_id
        created_bloggers += 1

    # Step 3: load integrations
    matched, miss_marketer = [], 0
    for r in integrations:
        m_id = marketers.get(r["marketer_name"])
        b_id = handle_to_id.get(r["blogger_handle_ref"].lower())
        if not m_id:
            miss_marketer += 1
            continue
        if not b_id:
            continue
        clean = {k: v for k, v in r.items()
                 if k not in ("blogger_handle_ref", "marketer_name")}
        clean["blogger_id"] = b_id
        clean["marketer_id"] = m_id
        matched.append(clean)
    if incremental:
        existing = existing_sheet_row_ids(conn, "crm.integrations")
        matched = filter_new_rows(matched, existing)
    n_i = upsert(conn, "crm.integrations", matched)

    # Step 4: resolve sub-links via ArticleResolver (handles SKU, OZON, model name)
    matched_srids = [m["sheet_row_id"] for m in matched]
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, sheet_row_id FROM crm.integrations WHERE sheet_row_id = ANY(%s)",
            (matched_srids,),
        )
        srid_to_id = {s: i for i, s in cur.fetchall()}

    resolver = ArticleResolver(conn)
    junction_rows = []
    seen_pairs: set[tuple[int, int]] = set()
    for sl in sub_links:
        i_id = srid_to_id.get(sl["integration_sheet_row_id"])
        if not i_id:
            continue
        artikul_ids = resolver.resolve_many(sl["sub_code"])
        if not artikul_ids:
            continue
        for idx, art_id in enumerate(artikul_ids, start=1):
            sub_id = _ensure_substitute_article(conn, sl["sub_code"], art_id, "creators")
            pair = (i_id, sub_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            junction_rows.append({
                "integration_id": i_id,
                "substitute_article_id": sub_id,
                "display_order": min(sl["display_order"] * 100 + idx, 999),
                "tracking_url": sl.get("tracking_url"),
            })
    n_j = insert_junction(
        conn,
        "crm.integration_substitute_articles",
        junction_rows,
        conflict_cols=("integration_id", "substitute_article_id"),
    )
    print(f"  auto-created bloggers from integrations: {created_bloggers}")
    print(f"  missing marketer (skipped): {miss_marketer}")
    return n_i, n_j, created_bloggers


def run_candidates(conn, incremental: bool = False) -> int:
    rows = t_candidates.transform(read_range(SPREADSHEET_ID, "inst на проверку!A1:N1000"))
    if incremental:
        existing = existing_sheet_row_ids(conn, "crm.blogger_candidates")
        rows = filter_new_rows(rows, existing)
    return upsert(conn, "crm.blogger_candidates", rows)


def _resolve_handles(conn) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, LOWER(display_handle) FROM crm.bloggers")
        return {h: i for i, h in cur.fetchall()}


SHEETS = {
    "promo_codes": run_promo_codes,
    "bloggers": run_bloggers,
    "substitute_articles": run_substitute_articles,
    "integrations": run_integrations,
    "candidates": run_candidates,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sheets ETL → crm.* tables")
    parser.add_argument("--sheet", choices=list(SHEETS.keys()), help="Run a single sheet")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Skip rows whose sheet_row_id is already present in the target table",
    )
    args = parser.parse_args(argv)

    sheets = [args.sheet] if args.sheet else list(SHEETS.keys())
    conn = get_conn()
    try:
        for s in sheets:
            print(f"=== {s} ===")
            result = SHEETS[s](conn, incremental=args.incremental)
            print(f"  loaded: {result}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
