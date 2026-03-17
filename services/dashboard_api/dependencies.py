"""Common query-parameter dependencies for dashboard routes."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import Query


class CommonParams:
    """Inject via ``Depends(CommonParams)`` to get validated date range + mp filter.

    ``end_date`` from the client is **inclusive** (the last day of the range).
    SQL queries use ``date < end_date`` (exclusive upper bound), so we add +1 day
    internally.  ``self.end_date`` is always the exclusive bound for SQL.

    Automatically computes ``prev_start`` — the start of a same-length
    period immediately before ``start_date`` (for period-over-period comparisons).
    """

    def __init__(
        self,
        start_date: str = Query(..., description="Start date YYYY-MM-DD"),
        end_date: str = Query(..., description="End date YYYY-MM-DD (inclusive)"),
        mp: Literal["wb", "ozon", "all"] = Query("all", description="Marketplace filter"),
    ):
        self.start_date = start_date
        self.mp = mp

        # end_date from client is inclusive; SQL needs exclusive upper bound (+1 day)
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end_inclusive = datetime.strptime(end_date, "%Y-%m-%d")
        end_exclusive = end_inclusive + timedelta(days=1)
        self.end_date = end_exclusive.strftime("%Y-%m-%d")

        # Previous period of the same length
        delta = end_exclusive - start
        self.prev_start = (start - delta).strftime("%Y-%m-%d")
