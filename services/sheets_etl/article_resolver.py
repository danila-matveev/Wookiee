"""Caching resolver: any string → list of public.artikuly.id.

Sheets reference articles in 5 formats. We try them in order:
  1. SKU with size:    "Wendy/black_S"   → match on artikul_ozon
  2. SKU without size: "Wendy/white"     → match on artikul
  3. WB nm-id:         "175569270"       → match on nomenklatura_wb
  4. OZON FBO SKU id:  "1334932371"      → match via tovary.ozon_fbo_sku_id → artikul_id
  5. Model name:       "Wendy"           → match on modeli.nazvanie / nazvanie_en
                                            → returns ALL artikuly of that model

Whitespace normalization strips NBSP (\\xa0) and NNBSP (\\u202f) so values
copied from Sheets like "1\\xa0334\\xa0932\\xa0371" still resolve.

WW-prefixed codes (e.g. "WW136611") found in historic blogger rows are
*not* in the SKU master DB anywhere — they're sheet-only legacy markers
and remain unresolved by design.

Cached on first call so we don't hammer the DB inside loops.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def _normalize(value: str) -> str:
    """Lower + strip incl. NBSP/NNBSP/zero-width chars."""
    if not value:
        return ""
    s = value.strip().lower()
    # NBSP, NNBSP, zero-width space, regular spaces between digits
    for ch in ("\xa0", " ", "​"):
        s = s.replace(ch, "")
    return s


class ArticleResolver:
    def __init__(self, conn: Any) -> None:
        self.conn = conn
        self._by_artikul: dict[str, int] = {}
        self._by_artikul_ozon: dict[str, int] = {}
        self._by_nm_wb: dict[str, int] = {}
        self._by_ozon_sku: dict[str, int] = {}
        self._by_model: dict[str, list[int]] = defaultdict(list)
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT a.id, a.artikul, a.artikul_ozon, a.nomenklatura_wb,
                       LOWER(m.nazvanie) AS model_ru,
                       LOWER(m.nazvanie_en) AS model_en
                FROM public.artikuly a
                LEFT JOIN public.modeli m ON m.id = a.model_id
            """)
            for art_id, artikul, art_ozon, nm_wb, model_ru, model_en in cur.fetchall():
                if artikul:
                    self._by_artikul[_normalize(artikul)] = art_id
                if art_ozon:
                    self._by_artikul_ozon[_normalize(art_ozon)] = art_id
                if nm_wb is not None:
                    self._by_nm_wb[str(nm_wb)] = art_id
                if model_ru:
                    self._by_model[model_ru].append(art_id)
                if model_en and model_en != model_ru:
                    self._by_model[model_en].append(art_id)

            # OZON FBO SKU IDs live on `tovary` (size-level). The same
            # ozon_fbo_sku_id can repeat across sizes that share an OZON
            # listing; we collapse to artikul_id (color-level).
            cur.execute("""
                SELECT DISTINCT t.ozon_fbo_sku_id, t.artikul_id
                FROM public.tovary t
                WHERE t.ozon_fbo_sku_id IS NOT NULL AND t.artikul_id IS NOT NULL
            """)
            for sku_id, art_id in cur.fetchall():
                self._by_ozon_sku.setdefault(str(sku_id), art_id)
        self._loaded = True

    def resolve_one(self, value: str) -> int | None:
        """Resolve a single SKU-shaped string → one artikul.id (or None)."""
        self._load()
        v = _normalize(value)
        if not v:
            return None
        if v in self._by_artikul:
            return self._by_artikul[v]
        if v in self._by_artikul_ozon:
            return self._by_artikul_ozon[v]
        # Strip size suffix (_S/_M/_L/_XL/_XS) and retry
        base = v.rsplit("_", 1)[0] if v.rsplit("_", 1)[-1] in {"s", "m", "l", "xl", "xs"} else v
        if base != v and base in self._by_artikul:
            return self._by_artikul[base]
        if v.isdigit():
            if v in self._by_nm_wb:
                return self._by_nm_wb[v]
            if v in self._by_ozon_sku:
                return self._by_ozon_sku[v]
        return None

    def resolve_many(self, value: str) -> list[int]:
        """Resolve any reference → list of artikul.id.

        SKU-shaped (contains "/" or digits) → 0..1 ids.
        Model name → all artikuly of that model.
        """
        self._load()
        v = _normalize(value)
        if not v:
            return []
        # Try as SKU first
        one = self.resolve_one(v)
        if one is not None:
            return [one]
        # Fallback to model lookup (only if value is a single bareword: no "/")
        if "/" not in v and not v.isdigit():
            return list(self._by_model.get(v, []))
        return []
