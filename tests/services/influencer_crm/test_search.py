from __future__ import annotations


def test_search_returns_both_groups(client, auth):
    r = client.get("/search", headers=auth, params={"q": "instagram"})
    assert r.status_code == 200
    body = r.json()
    assert "bloggers" in body and "integrations" in body
    assert isinstance(body["bloggers"], list)
    assert isinstance(body["integrations"], list)


def test_search_requires_q(client, auth):
    r = client.get("/search", headers=auth)
    assert r.status_code == 422


def test_search_limit_param(client, auth):
    r = client.get("/search", headers=auth, params={"q": "a", "limit": 3})
    assert r.status_code == 200
    body = r.json()
    assert len(body["bloggers"]) <= 3
    assert len(body["integrations"]) <= 3
