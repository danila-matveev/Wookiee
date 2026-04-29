def test_list_tags(client, auth):
    r = client.get("/api/tags", headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_tag_idempotent(client, auth):
    r1 = client.post("/api/tags", headers=auth, json={"name": "test-tag-pytest"})
    assert r1.status_code in (200, 201)
    tag_id = r1.json()["id"]
    r2 = client.post("/api/tags", headers=auth, json={"name": "test-tag-pytest"})
    assert r2.status_code in (200, 201)
    assert r2.json()["id"] == tag_id  # find-or-create


def test_create_tag_requires_name(client, auth):
    r = client.post("/api/tags", headers=auth, json={})
    assert r.status_code == 422
