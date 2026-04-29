def test_create_brief_returns_id(client, auth):
    r = client.post("/api/briefs",
        headers=auth,
        json={"title": "PyTest brief", "content_md": "# header\n\nbody"},
    )
    assert r.status_code == 201
    assert r.json()["id"]


def test_create_brief_then_version(client, auth):
    r1 = client.post("/api/briefs", headers=auth, json={"title": "v1", "content_md": "v1"})
    bid = r1.json()["id"]
    r2 = client.post(f"/api/briefs/{bid}/versions",
        headers=auth,
        json={"content_md": "v2-content"},
    )
    assert r2.status_code == 201
    assert r2.json()["version"] >= 2


def test_list_versions(client, auth):
    r1 = client.post("/api/briefs", headers=auth, json={"title": "vlist", "content_md": "1"})
    bid = r1.json()["id"]
    client.post(f"/api/briefs/{bid}/versions", headers=auth, json={"content_md": "2"})
    client.post(f"/api/briefs/{bid}/versions", headers=auth, json={"content_md": "3"})
    r = client.get(f"/api/briefs/{bid}/versions", headers=auth)
    assert r.status_code == 200
    versions = r.json()
    assert len(versions) >= 3
