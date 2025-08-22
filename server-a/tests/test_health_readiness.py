import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI, status, HTTPException
from httpx import AsyncClient

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
        CLIENT_CONFIG='{"client_key_1":{"name":"Test Client 1","is_active":true,"daily_quota":100}}',
        PROVIDERS_CONFIG='{"ProviderA":{"is_active":true,"is_operational":true}}'
    )
    _ = settings.clients
    _ = settings.providers
    _ = settings.provider_alias_map
    return settings

@pytest.fixture
async def test_app_with_mocked_lifespan(mock_settings):
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
        mock_rabbitmq_connection.channel.return_value.__aenter__.return_value = channel_mock
        mock_rabbitmq_connection.close.return_value = None

        with patch('app.main.redis_client', mock_redis_client), \
             patch('app.main.rabbitmq_connection', mock_rabbitmq_connection), \
             patch('app.main.start_heartbeat_task', AsyncMock()): # Mock heartbeat task
            
            # Yield the fully configured app
            yield app

@pytest.mark.asyncio
async def test_healthz_endpoint(test_app_with_mocked_lifespan):
    async with AsyncClient(app=test_app_with_mocked_lifespan, base_url="http://test") as client:
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
async def test_readyz_endpoint_redis_unreachable(mock_settings):
    # Mock Redis to be unreachable
    mock_redis_client_down = AsyncMock()
    mock_redis_client_down.ping.side_effect = ConnectionError("Redis connection failed")

    # Mock RabbitMQ to be reachable
    mock_rabbitmq_up = AsyncMock()
    mock_rabbitmq_up.is_closed = False
    mock_rabbitmq_up.channel.return_value.__aenter__.return_value = AsyncMock()

    with patch('app.main.redis_client', mock_redis_client_down), \
         patch('app.main.rabbitmq_connection', mock_rabbitmq_up):
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/readyz")
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["error_code"] == "SERVICE_UNAVAILABLE"
        assert "Redis not reachable" in response.json()["message"]

@pytest.mark.asyncio
async def test_readyz_endpoint_rabbitmq_unreachable(mock_settings):
    # Mock Redis to be reachable
    mock_redis_up = AsyncMock()
    mock_redis_up.ping.return_value = True

    # Mock RabbitMQ to be unreachable
    mock_rabbitmq_down = AsyncMock()
    mock_rabbitmq_down.is_closed = True

    with patch('app.main.redis_client', mock_redis_up), \
         patch('app.main.rabbitmq_connection', mock_rabbitmq_down):

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/readyz")
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["error_code"] == "SERVICE_UNAVAILABLE"
        assert "RabbitMQ not connected" in response.json()["message"]