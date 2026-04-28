def test_list_returns_etag(client, auth):
    r = client.get("/bloggers", headers=auth, params={"limit": 5})
    assert r.status_code == 200
    assert "ETag" in r.headers
    etag = r.headers["ETag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_if_none_match_returns_304(client, auth):
    r1 = client.get("/bloggers", headers=auth, params={"limit": 5})
    etag = r1.headers["ETag"]

    r2 = client.get(
        "/bloggers",
        headers={**auth, "If-None-Match": etag},
        params={"limit": 5},
    )
    assert r2.status_code == 304


def test_health_no_etag(client):
    r = client.get("/health")
    assert "ETag" not in r.headers
