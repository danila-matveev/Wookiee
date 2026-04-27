"""Caching resolver: any string → list of public.artikuly.id.

Sheets reference articles in 4 formats. We try them in order:
  1. SKU with size:    "Wendy/black_S"   → match on artikul_ozon
  2. SKU without size: "Wendy/white"     → match on artikul
  3. WB nm-id:         "175569270"       → match on nomenklatura_wb
  4. Model name:       "Wendy"           → match on modeli.name
                                            → returns ALL artikuly of that model

Cached on first call so we don't hammer the DB inside loops.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


class ArticleResolver:
    def __init__(self, conn: Any) -> None:
        self.conn = conn
        self._by_artikul: dict[str, int] = {}
        self._by_artikul_ozon: dict[str, int] = {}
        self._by_nm_wb: dict[str, int] = {}
        self._by_model: dict[str, list[int]] = defaultdict(list)
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT a.id, a.artikul, a.artikul_ozon, a.nomenklatura_wb,
                       LOWER(m.name) AS model_name
                FROM public.artikuly a
                LEFT JOIN public.modeli m ON m.id = a.model_id
            """)
            for art_id, artikul, art_ozon, nm_wb, model_name in cur.fetchall():
                if artikul:
                    self._by_artikul[artikul.strip().lower()] = art_id
                if art_ozon:
                    self._by_artikul_ozon[art_ozon.strip().lower()] = art_id
                if nm_wb is not None:
                    self._by_nm_wb[str(nm_wb)] = art_id
                if model_name:
                    self._by_model[model_name].append(art_id)
        self._loaded = True

    def resolve_one(self, value: str) -> int | None:
        """Resolve a single SKU-shaped string → one artikul.id (or None)."""
        self._load()
        v = (value or "").strip().lower()
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
        if v.isdigit() and v in self._by_nm_wb:
            return self._by_nm_wb[v]
        return None

    def resolve_many(self, value: str) -> list[int]:
        """Resolve any reference → list of artikul.id.

        SKU-shaped (contains "/" or digits) → 0..1 ids.
        Model name → all artikuly of that model.
        """
        self._load()
        v = (value or "").strip().lower()
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
