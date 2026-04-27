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
