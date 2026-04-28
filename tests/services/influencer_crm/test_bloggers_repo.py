"""Direct tests of the bloggers repository against the populated CRM dev DB.

These tests assume P2 ETL ran (≥10 bloggers exist). They use BEGIN+ROLLBACK so
mutations don't leak between tests.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from shared.data_layer.influencer_crm._engine import session_factory
from shared.data_layer.influencer_crm import bloggers as bloggers_repo


@pytest.fixture()
def session():
    s = session_factory().__enter__()
    s.begin_nested()  # SAVEPOINT
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_list_returns_at_least_one_blogger(session: Session):
    rows, next_cursor = bloggers_repo.list_bloggers(session, limit=5)
    assert len(rows) >= 1
    assert all(r.id and r.display_handle for r in rows)


def test_list_respects_limit(session: Session):
    rows, _ = bloggers_repo.list_bloggers(session, limit=2)
    assert len(rows) <= 2


def test_list_with_status_filter(session: Session):
    rows, _ = bloggers_repo.list_bloggers(session, limit=50, status="active")
    assert all(r.status == "active" for r in rows)


def test_get_by_id_returns_full_payload(session: Session):
    rows, _ = bloggers_repo.list_bloggers(session, limit=1)
    if not rows:
        pytest.skip("No bloggers in DB yet")
    blogger_id = rows[0].id
    detail = bloggers_repo.get_blogger(session, blogger_id)
    assert detail is not None
    assert detail.id == blogger_id


def test_get_missing_returns_none(session: Session):
    assert bloggers_repo.get_blogger(session, 999_999_999) is None


def test_create_then_get(session: Session):
    new_id = bloggers_repo.create_blogger(
        session,
        display_handle="@pytest_blogger",
        status="new",
    )
    fetched = bloggers_repo.get_blogger(session, new_id)
    assert fetched is not None
    assert fetched.display_handle == "@pytest_blogger"


def test_update_changes_field(session: Session):
    rows, _ = bloggers_repo.list_bloggers(session, limit=1)
    if not rows:
        pytest.skip("No bloggers in DB yet")
    blogger_id = rows[0].id
    bloggers_repo.update_blogger(session, blogger_id, {"notes": "marker-12345"})
    refreshed = bloggers_repo.get_blogger(session, blogger_id)
    assert refreshed.notes == "marker-12345"


def test_list_cursor_round_trip(session: Session):
    """Page 1 → next_cursor → page 2 yields disjoint, correctly-ordered rows."""
    page1, cursor = bloggers_repo.list_bloggers(session, limit=3)
    if cursor is None:
        pytest.skip("Need >3 bloggers to exercise pagination")

    page2, _ = bloggers_repo.list_bloggers(session, limit=3, cursor=cursor)

    page1_ids = {r.id for r in page1}
    page2_ids = {r.id for r in page2}
    assert page1_ids.isdisjoint(page2_ids), "page 2 must not repeat page 1 rows"

    # page 1 last row strictly newer than page 2 first row (DESC order on
    # updated_at, then id)
    assert (page1[-1].updated_at, page1[-1].id) > (page2[0].updated_at, page2[0].id)
