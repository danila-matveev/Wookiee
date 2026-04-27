"""Cell parsers for Russian-formatted Sheets data."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation

_TRUE = frozenset({"✓", "+", "v", "yes", "true", "да", "1"})
_FALSE = frozenset({"0", "false", "no", "x", "-", "нет", "—"})
_EMPTY_MARKERS = frozenset({"", "na", "n/a", "-", "—"})


def _clean_num(s: str) -> str:
    # Russian sheets use 3 space variants for thousands: regular, NBSP, NNBSP.
    return (
        s.replace("\xa0", "")
         .replace(" ", "")
         .replace(" ", "")
         .replace(",", ".")
         .rstrip("%")
    )


def parse_int(s: str | None) -> int | None:
    if s is None:
        return None
    raw = str(s).strip()
    if raw.lower() in _EMPTY_MARKERS:
        return None
    try:
        return int(float(_clean_num(raw)))
    except (ValueError, InvalidOperation):
        return None


def parse_decimal(s: str | None) -> Decimal | None:
    if s is None:
        return None
    raw = str(s).strip()
    if raw.lower() in _EMPTY_MARKERS:
        return None
    try:
        return Decimal(_clean_num(raw))
    except (InvalidOperation, ValueError):
        return None


_DATE_FMTS = ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y")


def parse_date(s: str | None) -> dt.date | None:
    if s is None:
        return None
    raw = str(s).strip()
    if not raw:
        return None
    for fmt in _DATE_FMTS:
        try:
            return dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_bool(s: str | None) -> bool | None:
    if s is None:
        return None
    v = str(s).strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return None
