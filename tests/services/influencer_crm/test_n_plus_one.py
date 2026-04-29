"""Assert each list endpoint executes ≤3 queries.

A non-paginated list endpoint loading 50 rows must do at most:
  1. SELECT main rows
  2. SELECT count for cursor heuristic (we avoided this)
  3. Optional aggregate JOIN

If a future change adds a per-row SELECT, this test catches it.
"""
from __future__ import annotations

from sqlalchemy import event

from shared.data_layer.influencer_crm._engine import get_engine


def _attach_counter():
    counter = {"n": 0}

    def _on_before_execute(*_args, **_kwargs):
        counter["n"] += 1

    event.listen(get_engine(), "before_cursor_execute", _on_before_execute)
    return counter, _on_before_execute


def test_list_bloggers_query_count(client, auth):
    counter, listener = _attach_counter()
    try:
        r = client.get("/api/bloggers", headers=auth, params={"limit": 50})
        assert r.status_code == 200
    finally:
        event.remove(get_engine(), "before_cursor_execute", listener)
    assert counter["n"] <= 3, f"too many queries: {counter['n']}"


def test_list_integrations_query_count(client, auth):
    counter, listener = _attach_counter()
    try:
        r = client.get("/api/integrations", headers=auth, params={"limit": 50})
        assert r.status_code == 200
    finally:
        event.remove(get_engine(), "before_cursor_execute", listener)
    assert counter["n"] <= 3, f"too many queries: {counter['n']}"


def test_get_blogger_detail_query_count(client, auth):
    """Detail = main SELECT + channels SELECT = 2 queries."""
    list_resp = client.get("/api/bloggers", headers=auth, params={"limit": 1}).json()
    if not list_resp["items"]:
        import pytest
        pytest.skip("DB empty")
    bid = list_resp["items"][0]["id"]
    counter, listener = _attach_counter()
    try:
        r = client.get(f"/api/bloggers/{bid}", headers=auth)
        assert r.status_code == 200
    finally:
        event.remove(get_engine(), "before_cursor_execute", listener)
    assert counter["n"] <= 3, f"too many queries: {counter['n']}"


def test_get_integration_detail_query_count(client, auth):
    """Detail = main SELECT + subs SELECT + posts SELECT = 3 queries."""
    list_resp = client.get("/api/integrations", headers=auth, params={"limit": 1}).json()
    if not list_resp["items"]:
        import pytest
        pytest.skip("DB empty")
    iid = list_resp["items"][0]["id"]
    counter, listener = _attach_counter()
    try:
        r = client.get(f"/api/integrations/{iid}", headers=auth)
        assert r.status_code == 200
    finally:
        event.remove(get_engine(), "before_cursor_execute", listener)
    assert counter["n"] <= 4, f"too many queries: {counter['n']}"
