"""Shared FastAPI dependencies.

Auth is disabled for now (open testing access).
All actions are logged as user="anonymous".
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Query


@dataclass
class CurrentUser:
    id: int = 0
    email: str = "anonymous"
    name: str = "Anonymous"
    role: str = "admin"  # everyone is admin during testing


def get_current_user() -> CurrentUser:
    """Stub — returns anonymous admin user."""
    return CurrentUser()


@dataclass
class CommonQueryParams:
    page: int = 1
    per_page: int = 50
    sort: Optional[str] = None
    order: Optional[str] = None
    search: Optional[str] = None


def parse_multi_param(value: Optional[str]):
    """Parse a comma-joined filter param into scalar or list.

    Examples:
        '1'   -> 1       (scalar int — equality filter)
        '1,5' -> [1, 5]  (list of ints — IN-clause filter)
        None  -> None    (no filter)
    """
    if value is None:
        return None
    value = value.strip()
    if "," in value:
        return [int(x.strip()) for x in value.split(",") if x.strip()]
    return int(value)


def common_params(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort: Optional[str] = Query(None),
    order: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> CommonQueryParams:
    # Validate order — only accept "asc" or "desc", fall back to None
    if order and order not in ("asc", "desc"):
        order = None
    return CommonQueryParams(page=page, per_page=per_page, sort=sort, order=order, search=search)
