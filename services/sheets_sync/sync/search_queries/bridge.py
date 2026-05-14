"""DB→Sheets bridge for search-queries sync.

Before pulling metrics from WB API, ensure all words from `crm.branded_queries`
and `crm.substitute_articles` are present in Sheets col A in the correct
section. Words added via the Marketing Hub UI (Phase 2A: AddWWPanel /
AddBrandQueryPanel) live only in the DB — without this bridge they would be
silently skipped on every sync run because the WB pull iterates over Sheets
col A.

Section dividers in Sheets col A:
- (implicit top section)   → brand queries (from crm.branded_queries; no marker)
- "Артикулы внешний лид"   → external (purpose != 'creators'/'social')
- "Креаторы общие:"        → cr_general (purpose='creators', generic campaign)
- "Креаторы личные:"       → cr_personal (purpose='creators', campaign LIKE 'креатор_*')
- "Соцсети:"               → social (purpose='social')

Inserts go at the END of each section (one row before the next divider) so the
existing data layout is preserved and gspread row indices stay sane.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence


from services.sheets_etl.loader import get_conn

logger = logging.getLogger(__name__)


# Marker text → key in the parsed sections dict. Match is case-sensitive on the
# canonical Russian header strings used in the live sheet today.
SECTION_MARKERS: dict[str, str] = {
    "Артикулы внешний лид": "external_end",
    "Креаторы общие:":      "cr_general_end",
    "Креаторы личные:":     "cr_personal_end",
    "Соцсети:":             "social_end",
}

# Personal-creator campaigns: the Hub form auto-prefixes 'креатор_<name>' on
# personal traffic creators, generic creators get a plain campaign label.
CREATOR_PERSONAL_RE = re.compile(r"^креатор[_ ]", re.IGNORECASE)


def parse_section_dividers(col_a: list[str]) -> dict[str, int]:
    """Return {section_end_key: insert_row (1-indexed)} for each section.

    The insert row is the row of the next section's divider — i.e. inserting at
    that row pushes the divider down and lands the new value at the bottom of
    the current section.

    If a divider is missing, that section's end defaults to len(col_a)+1
    (append to bottom of sheet).
    """
    markers_found: dict[str, int] = {}
    for idx, val in enumerate(col_a):
        text = (val or "").strip()
        if text in SECTION_MARKERS:
            markers_found[SECTION_MARKERS[text]] = idx + 1  # 1-indexed Sheets row

    fallback = len(col_a) + 1
    result: dict[str, int] = {}

    # Brand section (top, no marker) → insert before "Артикулы внешний лид"
    result["brand_end"] = markers_found.get("external_end", fallback)
    # External section → insert before "Креаторы общие:"
    result["external_end"] = markers_found.get("cr_general_end", fallback)
    # Cr_general section → insert before "Креаторы личные:"
    result["cr_general_end"] = markers_found.get("cr_personal_end", fallback)
    # Cr_personal section → insert before "Соцсети:"
    result["cr_personal_end"] = markers_found.get("social_end", fallback)
    # Social section → bottom of sheet
    result["social_end"] = fallback

    return result


def _route_word(
    word: str,
    purpose: str,
    campaign_name: str | None,
    sections: dict[str, int],
) -> int:
    """Decide which 1-indexed row a DB word should be inserted at.

    Routing is purely by (purpose, campaign_name) — does NOT touch the word
    itself, so brand words like "wooki" land in the brand section even if they
    look numeric.
    """
    p = (purpose or "").lower()
    if not p or p == "brand":
        return sections["brand_end"]
    if p == "creators":
        if campaign_name and CREATOR_PERSONAL_RE.match(campaign_name):
            return sections["cr_personal_end"]
        return sections["cr_general_end"]
    if p == "social":
        return sections["social_end"]
    # yandex, vk_target, adblogger, other → external
    return sections["external_end"]


def plan_inserts(
    db_words: Iterable[Sequence],
    sheet_words: set[str],
    sections: dict[str, int],
) -> list[tuple[str, int]]:
    """Build list of (word, target_row) tuples to insert.

    Each db_words entry: (word, purpose) or (word, purpose, campaign_name).
    Words already present in `sheet_words` are skipped (case-sensitive match
    against the existing col-A values).
    """
    inserts: list[tuple[str, int]] = []
    for entry in db_words:
        if len(entry) == 2:
            word, purpose = entry
            campaign: str | None = None
        else:
            word, purpose, campaign = entry[0], entry[1], entry[2]
        if not word:
            continue
        if word in sheet_words:
            continue
        row = _route_word(word, purpose or "", campaign, sections)
        inserts.append((word, row))
    return inserts


def fetch_db_words() -> list[tuple[str, str, str | None]]:
    """Fetch all active search words from `crm.branded_queries` + `crm.substitute_articles`.

    Returns list of `(word, purpose, campaign_name)` tuples. Branded queries
    get `purpose='brand'` and `campaign_name=None` (the brand section has no
    campaign concept). `status='active'` filter applied on both tables.

    Raises whatever psycopg2 raises on connection / query failure — caller
    decides whether to abort the sync.
    """
    rows: list[tuple[str, str, str | None]] = []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT query
                FROM crm.branded_queries
                WHERE status = 'active'
                  AND query IS NOT NULL
                  AND TRIM(query) <> ''
                """
            )
            for (q,) in cur.fetchall():
                rows.append((q.strip(), "brand", None))

            cur.execute(
                """
                SELECT code, purpose, campaign_name
                FROM crm.substitute_articles
                WHERE status = 'active'
                  AND code IS NOT NULL
                  AND TRIM(code) <> ''
                """
            )
            for code, purpose, campaign in cur.fetchall():
                rows.append((code.strip(), purpose, campaign))
    finally:
        conn.close()
    return rows


def ensure_db_words_in_sheets(ws, db_words: list[tuple[str, str, str | None]] | None = None) -> int:
    """Insert any DB-only words into Sheets col A in the correct section.

    Args:
        ws: gspread Worksheet — `Аналитика по запросам`.
        db_words: optional pre-fetched list (test injection point); when None,
            the function calls `fetch_db_words()` itself.

    Returns count of rows inserted (0 if everything is already in sync).

    Raises on DB / Sheets failures so the caller can abort the WB pull rather
    than silently drift.
    """
    col_a = ws.col_values(1)
    # Skip rows 1-2 (headers / dates) when building the existing-words set.
    sheet_words: set[str] = {
        (c or "").strip() for c in col_a[2:] if c and (c or "").strip()
    }
    sections = parse_section_dividers(col_a)
    if db_words is None:
        db_words = fetch_db_words()

    inserts = plan_inserts(db_words, sheet_words, sections)
    if not inserts:
        logger.info("Bridge: no new words to insert (sheet=%d, db=%d)",
                    len(sheet_words), len(db_words))
        return 0

    # Insert from the bottom up so earlier inserts don't shift the row numbers
    # of later ones.
    inserts_sorted = sorted(inserts, key=lambda x: -x[1])
    for word, target_row in inserts_sorted:
        ws.insert_row([word], target_row)

    logger.info("Bridge: inserted %d new words into Sheets (db=%d)",
                len(inserts), len(db_words))
    return len(inserts)


# Re-export for ergonomic imports from sync_search_queries.
__all__ = [
    "SECTION_MARKERS",
    "ensure_db_words_in_sheets",
    "fetch_db_words",
    "parse_section_dividers",
    "plan_inserts",
]
