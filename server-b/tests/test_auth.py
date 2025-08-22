import pytest
from app.repositories import UserRepository
from sqlalchemy import delete
from app import models


@pytest.mark.asyncio
async def test_login_success(client, session):
    await session.execute(delete(models.User))
    await session.commit()
    repo = UserRepository(session)
    await repo.create_user(
        name="Admin",
        username="admin",
        daily_quota=1000,
        api_key="key",
        password="changeme",
        note=None,
    )
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})
    assert resp.status_code == 200
    assert resp.json() == {"access_token": "fake-token", "token_type": "bearer"}


@pytest.mark.asyncio
async def test_login_failure(client, session):
    await session.execute(delete(models.User))
    await session.commit()
    repo = UserRepository(session)
    await repo.create_user(
        name="Admin",
        username="admin",
        daily_quota=1000,
        api_key="key",
        password="changeme",
        note=None,
    )
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"
