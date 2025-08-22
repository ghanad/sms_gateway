def auth_headers(client):
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_messages(client, seed_data):
    hdrs = auth_headers(client)
    resp = client.get("/messages", headers=hdrs)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_filter_and_paging(client, seed_data):
    hdrs = auth_headers(client)
    resp = client.get("/messages?to=100&limit=1", headers=hdrs)
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 1
    resp2 = client.get("/messages?provider=p2", headers=hdrs)
    assert resp2.json()["total"] == 1
