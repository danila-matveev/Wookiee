"""Tests for /bloggers endpoints + schemas."""
from __future__ import annotations

from decimal import Decimal


def test_blogger_out_serializes_money_as_string():
    from services.influencer_crm.schemas.blogger import BloggerOut

    b = BloggerOut(
        id=1,
        display_handle="@user",
        status="active",
        default_marketer_id=2,
        price_story_default=Decimal("1500.00"),
        price_reels_default=None,
    )
    d = b.model_dump(mode="json")
    assert d["price_story_default"] == "1500.00"
    assert d["price_reels_default"] is None


def test_blogger_create_requires_handle():
    import pytest
    from pydantic import ValidationError
    from services.influencer_crm.schemas.blogger import BloggerCreate

    with pytest.raises(ValidationError):
        BloggerCreate()  # type: ignore[call-arg]


def test_list_bloggers_requires_auth(client):
    r = client.get("/api/bloggers")
    assert r.status_code == 403


def test_list_bloggers_returns_page(client, auth):
    r = client.get("/api/bloggers", headers=auth, params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "next_cursor" in body
    assert len(body["items"]) <= 5


def test_get_blogger_404_for_missing(client, auth):
    r = client.get("/api/bloggers/999999999", headers=auth)
    assert r.status_code == 404


def test_get_blogger_returns_drawer_payload(client, auth):
    import pytest
    list_resp = client.get("/api/bloggers", headers=auth, params={"limit": 1}).json()
    if not list_resp["items"]:
        pytest.skip("DB empty")
    blogger_id = list_resp["items"][0]["id"]
    r = client.get(f"/api/bloggers/{blogger_id}", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == blogger_id
    assert "channels" in body
    assert "integrations_count" in body


def test_create_blogger(client, auth):
    r = client.post("/api/bloggers",
        headers=auth,
        json={"display_handle": "@pytest_create_user", "status": "new"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["display_handle"] == "@pytest_create_user"
    new_id = body["id"]
    # Cleanup so test is idempotent
    client.patch(f"/api/bloggers/{new_id}", headers=auth, json={"display_handle": f"deleted-{new_id}"})


def test_patch_blogger_partial_update(client, auth):
    import pytest
    list_resp = client.get("/api/bloggers", headers=auth, params={"limit": 1}).json()
    if not list_resp["items"]:
        pytest.skip("DB empty")
    blogger_id = list_resp["items"][0]["id"]
    original_notes = list_resp["items"][0].get("notes")
    r = client.patch(f"/api/bloggers/{blogger_id}",
        headers=auth,
        json={"notes": "patched-by-test"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("notes") == "patched-by-test" or "notes" not in body
    # Restore
    client.patch(f"/api/bloggers/{blogger_id}", headers=auth, json={"notes": original_notes})
