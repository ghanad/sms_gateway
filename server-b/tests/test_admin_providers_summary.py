def admin_headers(client):
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_providers_summary(client, seed_data):
    hdrs = admin_headers(client)
    resp = client.get("/admin/providers", headers=hdrs)
    assert resp.status_code == 200
    data = {p['name']: p['message_count'] for p in resp.json()['providers']}
    assert data["p1"] == 2
    assert data["p2"] == 1


def test_summary_endpoint(client, seed_data):
    hdrs = admin_headers(client)
    resp = client.get("/admin/summary", headers=hdrs)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_messages"] == 3
    assert body["total_users"] >= 2
