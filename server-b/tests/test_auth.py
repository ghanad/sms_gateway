def test_login_success(client, seed_data):
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_invalid(client, seed_data):
    resp = client.post("/auth/login", json={"username": "admin", "password": "bad"})
    assert resp.status_code == 401


def test_role_guard(client, seed_data):
    resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    token = resp.json()["access_token"]
    resp2 = client.get("/admin/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 403
