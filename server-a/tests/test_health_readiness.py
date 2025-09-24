import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI, status, HTTPException
from httpx import AsyncClient

import app.main as main
from app.main import app, readyz, healthz # Import the endpoints
from app.config import Settings

# Mock settings for testing
@pytest.fixture
def mock_settings():
    settings = Settings(
        SERVICE_NAME="test-server-a",
        SERVER_A_HOST="0.0.0.0",
        SERVER_A_PORT=8000,
        REDIS_URL="redis://localhost:6379/0",
        RABBITMQ_URL="amqp://guest:guest@localhost:5672/",
        PROVIDER_GATE_ENABLED=True,
        IDEMPOTENCY_TTL_SECONDS=10,
        QUOTA_PREFIX="test-quota",
        HEARTBEAT_INTERVAL_SECONDS=60,
    )
    return settings

@pytest.fixture
def test_app_with_mocked_lifespan(mock_settings):
    # Patch get_settings globally for the app
    with patch('app.config.get_settings', return_value=mock_settings), \
         patch('app.main.get_settings', return_value=mock_settings):
        
        # Mock Redis and RabbitMQ clients for lifespan and readiness checks
        mock_redis_client = AsyncMock()
        mock_redis_client.ping.return_value = True # Redis is reachable by default
        mock_redis_client.close.return_value = None

        mock_rabbitmq_connection = AsyncMock()
        mock_rabbitmq_connection.is_closed = False
        # Make sure the channel context manager works
        channel_mock = AsyncMock()
        mock_rabbitmq_connection.channel = MagicMock(return_value=channel_mock)
        channel_mock.__aenter__.return_value = channel_mock
        mock_rabbitmq_connection.close.return_value = None

        with patch('app.main.redis_client', mock_redis_client), \
             patch('app.main.rabbitmq_connection', mock_rabbitmq_connection), \
             patch('app.main.start_heartbeat_task', AsyncMock()): # Mock heartbeat task
            
            # Yield the fully configured app
            yield app

@pytest.mark.asyncio
async def test_healthz_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_readyz_endpoint_success(test_app_with_mocked_lifespan):
    async with AsyncClient(app=test_app_with_mocked_lifespan, base_url="http://test") as client:
        response = await client.get("/readyz")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_readyz_endpoint_redis_unreachable(test_app_with_mocked_lifespan):
    with patch('app.main.redis_client.ping', side_effect=ConnectionError("Redis connection failed")):
        async with AsyncClient(app=test_app_with_mocked_lifespan, base_url="http://test") as client:
            response = await client.get("/readyz")
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["error_code"] == "SERVICE_UNAVAILABLE"
        assert "Redis connection failed" in response.json()["message"]

@pytest.mark.asyncio
async def test_readyz_endpoint_rabbitmq_unreachable(test_app_with_mocked_lifespan):
    with patch('app.main.rabbitmq_connection.is_closed', True):
        async with AsyncClient(app=test_app_with_mocked_lifespan, base_url="http://test") as client:
            response = await client.get("/readyz")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["error_code"] == "SERVICE_UNAVAILABLE"
        assert "RabbitMQ not connected" in response.json()["message"]


@pytest.mark.asyncio
async def test_lifespan_cancels_background_tasks(monkeypatch):
    heartbeat_started = asyncio.Event()
    heartbeat_cancelled = asyncio.Event()
    consumer_started = asyncio.Event()
    consumer_cancelled = asyncio.Event()

    async def heartbeat_stub():
        heartbeat_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            heartbeat_cancelled.set()
            raise

    async def consume_stub():
        consumer_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            consumer_cancelled.set()
            raise

    mock_redis_client = AsyncMock()
    mock_redis_client.ping = AsyncMock(return_value=True)
    mock_redis_client.close = AsyncMock()

    mock_channel = AsyncMock()
    mock_channel.declare_exchange = AsyncMock()
    mock_channel.declare_queue = AsyncMock()

    mock_rabbitmq_connection = AsyncMock()
    mock_rabbitmq_connection.channel = AsyncMock(return_value=mock_channel)
    mock_rabbitmq_connection.close = AsyncMock()

    monkeypatch.setattr(main, "redis_client", None)
    monkeypatch.setattr(main, "rabbitmq_connection", None)
    monkeypatch.setattr(main, "rabbitmq_channel", None)
    monkeypatch.setattr(main, "get_redis_client", AsyncMock(return_value=mock_redis_client))
    monkeypatch.setattr(main, "get_rabbitmq_connection", AsyncMock(return_value=mock_rabbitmq_connection))
    monkeypatch.setattr(main, "start_heartbeat_task", heartbeat_stub)
    monkeypatch.setattr(main, "consume_config_state", consume_stub)
    monkeypatch.setattr(main.settings, "CONFIG_STATE_SYNC_ENABLED", True, raising=False)
    monkeypatch.setattr(main, "load_state_from_file", MagicMock(return_value=True))

    async with app.router.lifespan_context(app):
        await asyncio.wait_for(heartbeat_started.wait(), timeout=1)
        await asyncio.wait_for(consumer_started.wait(), timeout=1)

    assert heartbeat_cancelled.is_set()
    assert consumer_cancelled.is_set()
    mock_rabbitmq_connection.close.assert_awaited_once()
    mock_redis_client.close.assert_awaited_once()
