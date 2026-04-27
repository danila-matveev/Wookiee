"""CLI orchestrator: pull → transform → upsert all CRM sheets in dependency order.

Usage:
    .venv/bin/python -m services.sheets_etl.run [--sheet NAME]
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from services.sheets_etl.config import SPREADSHEET_ID
from services.sheets_etl.fetch import read_range
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


def run_promo_codes(conn) -> int:
    rows = t_promo.transform(read_range(SPREADSHEET_ID, "Промокоды_справочник!A1:G1000"))
    return upsert(conn, "crm.promo_codes", rows)


def run_bloggers(conn) -> tuple[int, int]:
    bloggers, channels = t_bloggers.transform(
        read_range(SPREADSHEET_ID, "БД БЛОГЕРЫ!A1:G2000")
    )
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


def run_substitute_articles(conn) -> tuple[int, int]:
    articles, metrics = t_subs.transform(
        read_range(SPREADSHEET_ID, "Подменные!A1:HZ1500")
    )
    matched: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        for a in articles:
            cur.execute(
                "SELECT id FROM public.artikuly WHERE LOWER(artikul) = LOWER(%s) LIMIT 1",
                (a["code"],),
            )
            r = cur.fetchone()
            if r:
                a["artikul_id"] = r[0]
                matched.append(a)
    n_a = upsert(conn, "crm.substitute_articles", matched)

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
    return n_a, n_m


def run_integrations(conn) -> tuple[int, int]:
    integrations, sub_links = t_integrations.transform(
        read_range(SPREADSHEET_ID, "Блогеры!A1:CL2000")
    )
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM crm.marketers")
        marketers = {n: i for i, n in cur.fetchall()}
        cur.execute("SELECT id, LOWER(display_handle) FROM crm.bloggers")
        bloggers_by_handle = {h: i for i, h in cur.fetchall()}
    matched = []
    for r in integrations:
        m_id = marketers.get(r["marketer_name"])
        b_id = bloggers_by_handle.get(r["blogger_handle_ref"].lower())
        if not m_id or not b_id:
            continue
        clean = {k: v for k, v in r.items()
                 if k not in ("blogger_handle_ref", "marketer_name")}
        clean["blogger_id"] = b_id
        clean["marketer_id"] = m_id
        matched.append(clean)
    n_i = upsert(conn, "crm.integrations", matched)

    matched_srids = [m["sheet_row_id"] for m in matched]
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, sheet_row_id FROM crm.integrations WHERE sheet_row_id = ANY(%s)",
            (matched_srids,),
        )
        srid_to_id = {s: i for i, s in cur.fetchall()}
        cur.execute("SELECT id, code FROM crm.substitute_articles")
        code_to_sub = {c.lower(): i for i, c in cur.fetchall()}
    junction_rows = []
    for sl in sub_links:
        i_id = srid_to_id.get(sl["integration_sheet_row_id"])
        s_id = code_to_sub.get(sl["sub_code"].lower())
        if not i_id or not s_id:
            continue
        junction_rows.append({
            "integration_id": i_id,
            "substitute_article_id": s_id,
            "display_order": sl["display_order"],
            "tracking_url": sl.get("tracking_url"),
        })
    n_j = insert_junction(
        conn,
        "crm.integration_substitute_articles",
        junction_rows,
        conflict_cols=("integration_id", "substitute_article_id"),
    )
    return n_i, n_j


def run_candidates(conn) -> int:
    rows = t_candidates.transform(read_range(SPREADSHEET_ID, "inst на проверку!A1:N1000"))
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
    args = parser.parse_args(argv)

    sheets = [args.sheet] if args.sheet else list(SHEETS.keys())
    conn = get_conn()
    try:
        for s in sheets:
            print(f"=== {s} ===")
            result = SHEETS[s](conn)
            print(f"  loaded: {result}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
