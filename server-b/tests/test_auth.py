import pytest


@pytest.mark.asyncio
async def test_login_success(client):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})
    assert resp.status_code == 200
    assert resp.json() == {"access_token": "fake-token", "token_type": "bearer"}


@pytest.mark.asyncio
async def test_login_failure(client):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"
