"""Common query-parameter dependencies for dashboard routes."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import Query


class CommonParams:
    """Inject via ``Depends(CommonParams)`` to get validated date range + mp filter.

    Automatically computes ``prev_start`` — the start of a same-length
    period immediately before ``start_date`` (for period-over-period comparisons).
    """

    def __init__(
        self,
        start_date: str = Query(..., description="Start date YYYY-MM-DD"),
        end_date: str = Query(..., description="End date YYYY-MM-DD"),
        mp: Literal["wb", "ozon", "all"] = Query("all", description="Marketplace filter"),
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.mp = mp

        # Auto-compute previous period of the same length
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        delta = end - start
        self.prev_start = (start - delta).strftime("%Y-%m-%d")
