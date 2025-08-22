def admin_headers(client):
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def user_headers(client):
    resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_list_users_requires_admin(client, seed_data):
    resp = client.get("/users", headers=user_headers(client))
    assert resp.status_code == 403
    resp2 = client.get("/users", headers=admin_headers(client))
    assert resp2.status_code == 200
    assert len(resp2.json()) >= 2


def test_create_and_associate_user(client, seed_data):
    hdrs = admin_headers(client)
    resp = client.post(
        "/users",
        json={"username": "bob", "password": "pw", "role": "user"},
        headers=hdrs,
    )
    assert resp.status_code == 201
    user_id = resp.json()["id"]
    resp2 = client.post(
        f"/users/{user_id}/associations",
        json={"provider": "p1"},
        headers=hdrs,
    )
    assert resp2.status_code == 200
    assert "p1" in resp2.json()["providers"]
