def test_substitute_articles_list(client, auth):
    r = client.get("/substitute-articles", headers=auth, params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body


def test_promo_codes_list(client, auth):
    r = client.get("/promo-codes", headers=auth, params={"limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    if body["items"]:
        assert "code" in body["items"][0]


def test_filter_by_active_only(client, auth):
    r = client.get(
        "/promo-codes", headers=auth, params={"status": "active", "limit": 50}
    )
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["status"] == "active"
