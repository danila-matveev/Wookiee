"""Terminal name → category mapping for card (terminal) payments."""
from __future__ import annotations

from .description_rules import (
    CAT_LOGISTICS_OTHER, CAT_LOGISTICS_WB, CAT_LOGISTICS_CHINA,
    CAT_SELFBUYS, CAT_GIFTS_BLOGGERS, CAT_SOFTWARE,
    CAT_WAREHOUSE_UPKEEP, CAT_SUPPLIES, CAT_PHOTO,
    CAT_STAFF_OTHER, CAT_FOT_MGMT,
)

# Terminal name (substring match) → (category_id, rule_name)
TERMINAL_RULES: list[tuple[str, int, str]] = [
    # Delivery / logistics
    ("YANDEX*4215*DOSTAVKA", CAT_LOGISTICS_OTHER, "term_yandex_dostavka"),
    ("YANDEX 4121 YANDEX.TAX", CAT_LOGISTICS_OTHER, "term_yandex_taxi"),
    ("YANDEX*4121*TAXI", CAT_LOGISTICS_OTHER, "term_yandex_taxi2"),
    ("YANDEX*4121*GO", CAT_LOGISTICS_OTHER, "term_yandex_go"),
    ("PEK MOSKVA", CAT_LOGISTICS_CHINA, "term_pek"),
    # WILDBERRIES.RU removed — too ambiguous (supplies, photo, blogger items etc.)
    # Gifts
    ("CP* FLOWWOW", CAT_GIFTS_BLOGGERS, "term_flowwow"),
    # Software / SaaS
    ("TIMEWEB.CLOUD", CAT_SOFTWARE, "term_timeweb"),
    ("MPSTATS.IO", CAT_SOFTWARE, "term_mpstats"),
    ("SELLEGO.COM", CAT_SOFTWARE, "term_sellego"),
    ("YM*labelup", CAT_SOFTWARE, "term_labelup"),
    ("CP* TILDA", CAT_SOFTWARE, "term_tilda"),
    ("YM*mpmgr", CAT_SOFTWARE, "term_mpmgr"),
    ("Finolog", CAT_SOFTWARE, "term_finolog"),
    ("REG.RU", CAT_SOFTWARE, "term_regru"),
    # Warehouse
    ("OZON RETAIL", CAT_WAREHOUSE_UPKEEP, "term_ozon_retail"),
    # Supplies
    ("RUSSKARTON", CAT_SUPPLIES, "term_russkarton"),
    ("KOMUS", CAT_SUPPLIES, "term_komus"),
    # Photo
    ("AppEvent", CAT_PHOTO, "term_appevent"),
    # Staff
    ("ONETWOTRIP", CAT_STAFF_OTHER, "term_onetwotrip"),
    ("CITY.TRAVEL", CAT_FOT_MGMT, "term_city_travel"),
]


def extract_terminal(description: str) -> str | None:
    """Extract terminal name from 'Покупка товара(Терминал:XXX,...)' pattern."""
    import re
    m = re.search(r"Терминал:([\w\s*.\-]+)", description)
    if m:
        return m.group(1).strip()
    return None


def match_terminal(description: str) -> tuple[int, str] | None:
    """Match a transaction description against terminal rules.

    Returns (category_id, rule_name) or None.
    """
    terminal = extract_terminal(description)
    if not terminal:
        return None
    terminal_upper = terminal.upper()
    for pattern, cat_id, rule_name in TERMINAL_RULES:
        if pattern.upper() in terminal_upper:
            return (cat_id, rule_name)
    return None
