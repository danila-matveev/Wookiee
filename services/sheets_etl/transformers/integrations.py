"""Блогеры → crm.integrations + crm.integration_substitute_articles.

Wide layout, ~89 cols. Returns (integrations, sub_links).

Each integration carries `blogger_handle_ref` (col 0) and `marketer_name` (col 1)
so the loader can resolve FKs after the upserts. sub_links carry
`integration_sheet_row_id` and `sub_code` so loader can resolve both ends.
"""
from __future__ import annotations

from typing import Any

from services.sheets_etl.hash import sheet_row_id
from services.sheets_etl.parsers import parse_bool, parse_date, parse_decimal, parse_int

CHANNEL_MAP = {
    "instagram": "instagram",
    "telegram": "telegram",
    "tiktok": "tiktok",
    "youtube": "youtube",
    "vk": "vk",
    "vk посевы": "vk",
    "rutube": "rutube",
}

AD_FORMAT_MAP = {
    "сторис": "story",
    "рилс": "short_video",
    "видео": "long_video",
    "пост/лонгрид": "long_post",
    "сторис+пост": "story",
    "пост": "image_post",
    "интеграция": "integration",
    "стрим": "live_stream",
}

MARKETPLACE_MAP = {
    "wb": "wb",
    "ozon": "ozon",
    "озон": "ozon",
    "оба": "both",
    "wb+ozon": "both",
    "оба маркетплейса": "both",
}


def _first_token(s: str) -> str:
    """Take first comma/slash separated value, lowercase, trim."""
    s = (s or "").strip().lower()
    for sep in (",", "/", " и ", "+"):
        if sep in s:
            s = s.split(sep, 1)[0].strip()
            break
    return s


def _map_channel(s: str) -> str | None:
    return CHANNEL_MAP.get(_first_token(s))


def _map_ad_format(s: str) -> str | None:
    key = (s or "").strip().lower()
    if key in AD_FORMAT_MAP:
        return AD_FORMAT_MAP[key]
    return AD_FORMAT_MAP.get(_first_token(s))


def _map_marketplace(s: str) -> str | None:
    return MARKETPLACE_MAP.get((s or "").strip().lower())


def _stage_for(publish_date: Any, erid: str | None) -> str:
    """Pick a stage that satisfies chk_int_erid for historic rows."""
    if erid:
        return "done"
    # 2022-09-01 cutoff — older rows don't need erid
    if publish_date and str(publish_date) < "2022-09-01":
        return "done"
    return "content_received"


def transform(values: list[list[Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not values or len(values) < 2:
        return [], []

    integrations: list[dict[str, Any]] = []
    sub_links: list[dict[str, Any]] = []

    for raw in values[1:]:
        if not raw or len(raw) < 10:
            continue
        blogger = str(raw[0]).strip() if raw[0] else ""
        # Skip free-text divider rows (long comments, month markers like "ФЕВРАЛЬ 2023")
        if not blogger or len(blogger) > 80 or blogger.isupper():
            continue

        publish_date = parse_date(raw[5]) if len(raw) > 5 else None
        if not publish_date:
            continue

        marketplace = _map_marketplace(raw[8] if len(raw) > 8 else "")
        if not marketplace:
            continue

        channel = _map_channel(raw[9] if len(raw) > 9 else "")
        if not channel:
            continue

        ad_format = _map_ad_format(raw[7] if len(raw) > 7 else "")
        if not ad_format:
            ad_format = "integration"

        marketer = str(raw[1]).strip() if len(raw) > 1 and raw[1] else None
        if not marketer:
            continue

        srid = sheet_row_id([blogger, marketer, str(publish_date), channel])
        erid = None  # not in current sheet layout
        post_url = str(raw[41]).strip() if len(raw) > 41 and raw[41] else None
        stage = _stage_for(publish_date, erid)

        rec: dict[str, Any] = {
            "blogger_handle_ref": blogger,
            "marketer_name": marketer,
            "publish_date": publish_date,
            "channel": channel,
            "ad_format": ad_format,
            "marketplace": marketplace,
            "stage": stage,
            "is_barter": False,
            "cost_placement": parse_decimal(raw[10]) if len(raw) > 10 else None,
            "cost_delivery": parse_decimal(raw[11]) if len(raw) > 11 else None,
            "cost_goods": parse_decimal(raw[12]) if len(raw) > 12 else None,
            "plan_cpm": parse_decimal(raw[19]) if len(raw) > 19 else None,
            "plan_ctr": parse_decimal(raw[20]) if len(raw) > 20 else None,
            "plan_clicks": parse_int(raw[21]) if len(raw) > 21 else None,
            "plan_cpc": parse_decimal(raw[22]) if len(raw) > 22 else None,
            "fact_views": parse_int(raw[23]) if len(raw) > 23 else None,
            "fact_cpm": parse_decimal(raw[24]) if len(raw) > 24 else None,
            "fact_clicks": parse_int(raw[25]) if len(raw) > 25 else None,
            "fact_ctr": parse_decimal(raw[26]) if len(raw) > 26 else None,
            "fact_cpc": parse_decimal(raw[27]) if len(raw) > 27 else None,
            "fact_carts": parse_int(raw[28]) if len(raw) > 28 else None,
            "cr_to_cart": parse_decimal(raw[29]) if len(raw) > 29 else None,
            "fact_orders": parse_int(raw[30]) if len(raw) > 30 else None,
            "cr_to_order": parse_decimal(raw[31]) if len(raw) > 31 else None,
            "recommended_models": str(raw[39]).strip() if len(raw) > 39 and raw[39] else None,
            "contract_url": str(raw[40]).strip() if len(raw) > 40 and raw[40] else None,
            "post_url": post_url,
            "tz_url": str(raw[42]).strip() if len(raw) > 42 and raw[42] else None,
            "screen_url": str(raw[43]).strip() if len(raw) > 43 and raw[43] else None,
            "post_content": str(raw[44]).strip() if len(raw) > 44 and raw[44] else None,
            "analysis": str(raw[45]).strip() if len(raw) > 45 and raw[45] else None,
            "has_marking":         parse_bool(raw[46]) if len(raw) > 46 else None,
            "has_contract":        parse_bool(raw[47]) if len(raw) > 47 else None,
            "has_deeplink":        parse_bool(raw[48]) if len(raw) > 48 else None,
            "has_closing_docs":    parse_bool(raw[49]) if len(raw) > 49 else None,
            "has_full_recording":  parse_bool(raw[50]) if len(raw) > 50 else None,
            "all_data_filled":     parse_bool(raw[51]) if len(raw) > 51 else None,
            "has_quality_content": parse_bool(raw[52]) if len(raw) > 52 else None,
            "complies_with_rules": parse_bool(raw[53]) if len(raw) > 53 else None,
            "sheet_row_id": srid,
        }
        integrations.append(rec)

        # Sub-articles: cols 33/34/35 (slot 1) and 36/37/38 (slot 2)
        for slot, base_col in enumerate((33, 36), start=1):
            code = (
                str(raw[base_col]).strip()
                if len(raw) > base_col and raw[base_col]
                else ""
            )
            if not code:
                continue
            url = (
                str(raw[base_col + 2]).strip()
                if len(raw) > base_col + 2 and raw[base_col + 2]
                else None
            )
            sub_links.append({
                "integration_sheet_row_id": srid,
                "sub_code": code,
                "display_order": slot,
                "tracking_url": url,
            })

    return integrations, sub_links
