import asyncio
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from app.main import create_app
from app.db import get_session
from app import models
from app.repositories import create_user


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture()
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture()
async def app(db_session):
    application = create_app()

    async def override_get_session():
        yield db_session

    application.dependency_overrides[get_session] = override_get_session
    return application


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest_asyncio.fixture()
async def seed_data(db_session):
    admin = await create_user(db_session, "admin", "admin", "admin")
    user = await create_user(db_session, "alice", "secret", "user")
    db_session.add_all(
        [
            models.Message(to="100", text="hi", provider="p1", status="SENT"),
            models.Message(to="101", text="yo", provider="p2", status="FAILED"),
            models.Message(to="100", text="hey", provider="p1", status="QUEUED"),
        ]
    )
    await db_session.commit()
    return {"admin": admin, "user": user}
