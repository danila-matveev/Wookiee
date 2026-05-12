"""Parse the «Промокоды_справочник» sheet into a UUID-keyed mapping."""
from __future__ import annotations


def _truthy(val) -> bool:
    """TRUE if cell looks like a checked checkbox / 'yes' / 'да' / 1."""
    s = str(val or "").strip().lower()
    return s in ("true", "1", "yes", "y", "да", "д", "✓", "✔")


def parse_dictionary(raw_rows: list[list[str]]) -> dict[str, dict]:
    """Parse the справочник sheet into {uuid_lower: {name, channel, discount_pct, cabinets, ...}}.

    Expected header (any column may be missing, gracefully degrades):
        UUID | Название | Канал | Скидка % | ИП | ООО | Старт | Окончание | Примечание

    `cabinets` is a list like ["ИП", "ООО"]; empty list means "no cabinets flagged"
    in which case the script falls back to both cabinets (legacy behaviour).
    Rows with empty UUID are dropped.
    """
    if not raw_rows or len(raw_rows) < 2:
        return {}

    header = [(c or "").strip().lower() for c in raw_rows[0]]

    def _idx(*aliases: str) -> int | None:
        for a in aliases:
            if a in header:
                return header.index(a)
        return None

    col_uuid    = _idx("uuid")
    col_name    = _idx("название", "name")
    col_channel = _idx("канал", "channel")
    col_disc    = _idx("скидка %", "скидка")
    col_ip      = _idx("ип", "ip")
    col_ooo     = _idx("ооо", "ooo")
    col_start   = _idx("старт", "start")
    col_end     = _idx("окончание", "end")
    col_note    = _idx("примечание", "note")

    if col_uuid is None:
        # Fallback to legacy positional layout
        col_uuid, col_name, col_channel, col_disc = 0, 1, 2, 3
        col_start, col_end, col_note = 4, 5, 6
        col_ip = col_ooo = None

    def _cell(row: list, idx: int | None) -> str:
        if idx is None or idx >= len(row):
            return ""
        return str(row[idx] or "").strip()

    out: dict[str, dict] = {}
    for row in raw_rows[1:]:
        uuid = _cell(row, col_uuid).lower()
        if not uuid:
            continue
        try:
            disc_str = _cell(row, col_disc)
            disc_pct = float(disc_str) if disc_str else None
        except ValueError:
            disc_pct = None

        cabinets: list[str] = []
        if col_ip is not None and _truthy(_cell(row, col_ip)):
            cabinets.append("ИП")
        if col_ooo is not None and _truthy(_cell(row, col_ooo)):
            cabinets.append("ООО")

        out[uuid] = {
            "name": _cell(row, col_name),
            "channel": _cell(row, col_channel),
            "discount_pct": disc_pct,
            "cabinets": cabinets,
            "start": _cell(row, col_start),
            "end": _cell(row, col_end),
            "note": _cell(row, col_note),
        }
    return out


def parse_dictionary_from_pivot(all_rows: list[list[str]]) -> dict[str, dict]:
    """Parse promocode dictionary directly from the main analytics sheet (cols A-E, rows 11+).

    Single source of truth: the main sheet itself stores Название/UUID/Канал/Скидка %/Статус.
    Returns {uuid_lower: {name, discount_pct, status}}. Rows marked as 'неактивный'
    are excluded so the script ignores them when resolving names and DB writes.
    """
    from .sheet_layout import DATA_START_ROW, STATUS_INACTIVE

    out: dict[str, dict] = {}
    for row in all_rows[DATA_START_ROW - 1:]:
        if not row or len(row) < 2:
            continue
        uuid = (row[1] if len(row) > 1 else "").strip().lower()
        if not uuid:
            continue
        name = (row[0] or "").strip()
        disc_str = (row[3] if len(row) > 3 else "").strip()
        status = (row[4] if len(row) > 4 else "").strip()
        if status.lower() == STATUS_INACTIVE.lower():
            continue
        try:
            disc_pct = float(disc_str.replace(",", ".")) if disc_str else None
        except ValueError:
            disc_pct = None
        out[uuid] = {
            "name": name,
            "discount_pct": disc_pct,
            "status": status,
        }
    return out
