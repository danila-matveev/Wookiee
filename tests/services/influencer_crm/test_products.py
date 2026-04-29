"""Slices view — products with integration aggregates."""
from __future__ import annotations


def test_list_products_requires_auth(client):
    r = client.get("/products")
    assert r.status_code == 403


def test_list_products_returns_aggregates(client, auth):
    r = client.get("/products", headers=auth, params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    if body["items"]:
        item = body["items"][0]
        assert "model_osnova_id" in item
        assert "integrations_count" in item


def test_get_product_detail_404(client, auth):
    r = client.get("/products/999999999", headers=auth)
    assert r.status_code == 404
