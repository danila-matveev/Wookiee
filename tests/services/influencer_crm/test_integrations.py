"""HTTP tests for /integrations."""
from __future__ import annotations


def test_list_requires_auth(client):
    r = client.get("/integrations")
    assert r.status_code == 403


def test_list_returns_page(client, auth):
    r = client.get("/integrations", headers=auth, params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "next_cursor" in body


def test_kanban_filter_stage_in(client, auth):
    r = client.get(
        "/integrations",
        headers=auth,
        params={"stage_in": ["done", "paid"], "limit": 50},
    )
    assert r.status_code == 200
    for it in r.json()["items"]:
        assert it["stage"] in {"done", "paid"}


def test_get_404(client, auth):
    r = client.get("/integrations/999999999", headers=auth)
    assert r.status_code == 404


def test_get_detail_includes_substitutes(client, auth):
    list_resp = client.get("/integrations", headers=auth, params={"limit": 1}).json()
    if not list_resp["items"]:
        import pytest
        pytest.skip("DB empty")
    iid = list_resp["items"][0]["id"]
    r = client.get(f"/integrations/{iid}", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert "substitutes" in body
    assert "blogger_handle" in body


def test_stage_transition(client, auth):
    list_resp = client.get(
        "/integrations", headers=auth, params={"limit": 1, "stage_in": ["done"]}
    ).json()
    if not list_resp["items"]:
        import pytest
        pytest.skip("DB has no done integrations")
    iid = list_resp["items"][0]["id"]
    original_stage = list_resp["items"][0]["stage"]
    r = client.post(
        f"/integrations/{iid}/stage",
        headers=auth,
        json={"target_stage": "paid", "note": "marker"},
    )
    assert r.status_code == 200
    assert r.json()["stage"] == "paid"
    # restore
    client.post(
        f"/integrations/{iid}/stage",
        headers=auth,
        json={"target_stage": original_stage},
    )
