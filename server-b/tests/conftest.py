import asyncio
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import httpx

# Ensure that the application package is importable when tests are executed
# from the repository root by adding the ``server-b`` directory to ``sys.path``.
SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

# Provide a default in-memory database URL so ``app`` can import settings
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.main import app
from app import models
from app.db import get_session


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def async_sessionmaker_fixture():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def override_get_session(async_sessionmaker_fixture):
    async def _get_session():
        async with async_sessionmaker_fixture() as session:
            yield session
    app.dependency_overrides[get_session] = _get_session


@pytest_asyncio.fixture()
async def session(async_sessionmaker_fixture):
    async with async_sessionmaker_fixture() as s:
        yield s


@pytest_asyncio.fixture()
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
