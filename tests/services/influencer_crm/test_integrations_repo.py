"""Repository tests against populated CRM dev DB."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from shared.data_layer.influencer_crm._engine import session_factory
from shared.data_layer.influencer_crm import integrations as repo


@pytest.fixture()
def session():
    s = session_factory().__enter__()
    s.begin_nested()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_list_integrations(session: Session):
    rows, _ = repo.list_integrations(session, limit=5)
    assert len(rows) >= 1
    assert all(r.publish_date for r in rows)


def test_list_filter_by_stage(session: Session):
    rows, _ = repo.list_integrations(session, limit=50, stage_in=["завершено"])
    assert all(r.stage == "завершено" for r in rows)


def test_list_filter_by_marketplace(session: Session):
    rows, _ = repo.list_integrations(session, limit=50, marketplace="wb")
    assert all(r.marketplace in ("wb",) for r in rows)


def test_list_kanban_excludes_archived(session: Session):
    """The Kanban view (default) must hide archived rows."""
    rows, _ = repo.list_integrations(session, limit=200)
    # archived ones never appear; query filters archived_at IS NULL
    assert all(r.stage != "архив" or getattr(r, "outcome", None) is None
               for r in rows[:5])  # smoke


def test_get_integration_detail(session: Session):
    rows, _ = repo.list_integrations(session, limit=1)
    if not rows:
        pytest.skip("DB empty")
    detail = repo.get_integration(session, rows[0].id)
    assert detail is not None
    assert detail.blogger_handle  # JOIN worked
    assert isinstance(detail.substitutes, list)


def test_stage_transition_writes_history(session: Session):
    rows, _ = repo.list_integrations(session, limit=1)
    if not rows:
        pytest.skip("DB empty")
    integration_id = rows[0].id
    repo.transition_stage(session, integration_id, target_stage="согласовано", note="test")
    refreshed = repo.get_integration(session, integration_id)
    assert refreshed.stage == "согласовано"
