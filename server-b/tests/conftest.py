import asyncio
import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import httpx
from app.main import app
from app import models
from app.db import get_session


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def async_sessionmaker_fixture():
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def override_get_session(async_sessionmaker_fixture):
    async def _get_session():
        async with async_sessionmaker_fixture() as session:
            yield session
    app.dependency_overrides[get_session] = _get_session


@pytest.fixture()
async def session(async_sessionmaker_fixture):
    async with async_sessionmaker_fixture() as s:
        yield s


@pytest.fixture()
async def client():
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
