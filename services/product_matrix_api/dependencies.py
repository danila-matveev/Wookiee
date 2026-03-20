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
    search: Optional[str] = None


def common_params(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> CommonQueryParams:
    return CommonQueryParams(page=page, per_page=per_page, sort=sort, search=search)
