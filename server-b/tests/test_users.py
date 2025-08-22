import pytest
from sqlalchemy import delete
from app import models


@pytest.mark.asyncio
async def test_user_crud(client, session):
    await session.execute(delete(models.User))
    await session.commit()
    # create
    payload = {
        "name": "User1",
        "username": "user1",
        "daily_quota": 100,
        "api_key": "key1",
        "password": "pass1",
        "note": "note1"
    }
    resp = await client.post("/api/users", json=payload)
    assert resp.status_code == 200
    user_id = resp.json()["id"]

    # list
    resp = await client.get("/api/users")
    assert len(resp.json()) == 1

    # update
    resp = await client.put(f"/api/users/{user_id}", json={"name": "User1-upd"})
    assert resp.json()["name"] == "User1-upd"

    # deactivate
    resp = await client.post(f"/api/users/{user_id}/deactivate")
    assert resp.json()["active"] is False

    # change password
    resp = await client.post(f"/api/users/{payload['username']}/password", json={"password": "newpass"})
    assert resp.status_code == 200

    # delete
    resp = await client.delete(f"/api/users/{user_id}")
    assert resp.status_code == 200

    # final list
    resp = await client.get("/api/users")
    assert resp.json() == []
