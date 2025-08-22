import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI, status
from httpx import AsyncClient

from app.main import app
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
        mock_rabbitmq_connection.channel.return_value.__aenter__.return_value = AsyncMock()
        mock_rabbitmq_connection.channel.return_value.__aenter__.return_value.declare_exchange.return_value = None
        mock_rabbitmq_connection.channel.return_value.__aenter__.return_value.declare_queue.return_value = None
        mock_rabbitmq_connection.channel.return_value.__aenter__.return_value.bind.return_value = None
        mock_rabbitmq_connection.close.return_value = None

        with patch('app.main.get_redis_client', return_value=mock_redis_client), \
             patch('app.main.get_rabbitmq_connection', return_value=mock_rabbitmq_connection), \
             patch('app.idempotency.get_redis_client', return_value=mock_redis_client), \
             patch('app.quota.get_redis_client', return_value=mock_redis_client), \
             patch('app.rabbit.get_rabbitmq_connection', return_value=mock_rabbitmq_connection), \
             patch('app.heartbeat.aio_pika.connect_robust', return_value=mock_rabbitmq_connection), \
             patch('app.main.start_heartbeat_task', AsyncMock()): # Mock heartbeat task to prevent it from running
            
            # Manually call lifespan events for testing
            await app.router.lifespan_context(app).__aenter__()
            yield app
            await app.router.lifespan_context(app).__aexit__(None, None, None)

@pytest.mark.asyncio
async def test_healthz_endpoint(test_app_with_mocked_lifespan):
    async with AsyncClient(app=test_app_with_mocked_lifespan, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_readyz_endpoint_success(test_app_with_mocked_lifespan):
    # Redis and RabbitMQ are mocked to be reachable by default in test_app_with_mocked_lifespan
    async with AsyncClient(app=test_app_with_mocked_lifespan, base_url="http://test") as client:
        response = await client.get("/readyz")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_readyz_endpoint_redis_unreachable():
    # Create a new app instance to control mocks specifically for this test
    app_redis_down = FastAPI()
    mock_settings = Settings(
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
    _ = mock_settings.clients
    _ = mock_settings.providers
    _ = mock_settings.provider_alias_map

    mock_redis_client_down = AsyncMock()
    mock_redis_client_down.ping.side_effect = Exception("Redis connection failed")
    mock_redis_client_down.close.return_value = None

    mock_rabbitmq_connection_up = AsyncMock()
    mock_rabbitmq_connection_up.is_closed = False
    mock_rabbitmq_connection_up.channel.return_value.__aenter__.return_value = AsyncMock()
    mock_rabbitmq_connection_up.channel.return_value.__aenter__.return_value.declare_queue.return_value = None
    mock_rabbitmq_connection_up.close.return_value = None

    with patch('app.config.get_settings', return_value=mock_settings), \
         patch('app.main.get_settings', return_value=mock_settings), \
         patch('app.main.get_redis_client', return_value=mock_redis_client_down), \
         patch('app.main.get_rabbitmq_connection', return_value=mock_rabbitmq_connection_up), \
         patch('app.idempotency.get_redis_client', return_value=mock_redis_client_down), \
         patch('app.quota.get_redis_client', return_value=mock_redis_client_down), \
         patch('app.rabbit.get_rabbitmq_connection', return_value=mock_rabbitmq_connection_up), \
         patch('app.heartbeat.aio_pika.connect_robust', return_value=mock_rabbitmq_connection_up), \
         patch('app.main.start_heartbeat_task', AsyncMock()):
        
        # Manually call lifespan events for testing
        await app_redis_down.router.lifespan_context(app_redis_down).__aenter__()
        
        async with AsyncClient(app=app_redis_down, base_url="http://test") as client:
            response = await client.get("/readyz")
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["error_code"] == "SERVICE_UNAVAILABLE"
        assert "Redis not reachable" in response.json()["message"]
        
        await app_redis_down.router.lifespan_context(app_redis_down).__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_readyz_endpoint_rabbitmq_unreachable():
    # Create a new app instance to control mocks specifically for this test
    app_rabbitmq_down = FastAPI()
    mock_settings = Settings(
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
    _ = mock_settings.clients
    _ = mock_settings.providers
    _ = mock_settings.provider_alias_map

    mock_redis_client_up = AsyncMock()
    mock_redis_client_up.ping.return_value = True
    mock_redis_client_up.close.return_value = None

    mock_rabbitmq_connection_down = AsyncMock()
    mock_rabbitmq_connection_down.is_closed = True # Simulate closed connection
    mock_rabbitmq_connection_down.channel.side_effect = Exception("RabbitMQ channel error") # Simulate channel failure
    mock_rabbitmq_connection_down.close.return_value = None

    with patch('app.config.get_settings', return_value=mock_settings), \
         patch('app.main.get_settings', return_value=mock_settings), \
         patch('app.main.get_redis_client', return_value=mock_redis_client_up), \
         patch('app.main.get_rabbitmq_connection', return_value=mock_rabbitmq_connection_down), \
         patch('app.idempotency.get_redis_client', return_value=mock_redis_client_up), \
         patch('app.quota.get_redis_client', return_value=mock_redis_client_up), \
         patch('app.rabbit.get_rabbitmq_connection', return_value=mock_rabbitmq_connection_down), \
         patch('app.heartbeat.aio_pika.connect_robust', return_value=mock_rabbitmq_connection_down), \
         patch('app.main.start_heartbeat_task', AsyncMock()):
        
        # Manually call lifespan events for testing
        await app_rabbitmq_down.router.lifespan_context(app_rabbitmq_down).__aenter__()
        
        async with AsyncClient(app=app_rabbitmq_down, base_url="http://test") as client:
            response = await client.get("/readyz")
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["error_code"] == "SERVICE_UNAVAILABLE"
        assert "RabbitMQ not connected" in response.json()["message"] or "RabbitMQ channel error" in response.json()["message"]
        
        await app_rabbitmq_down.router.lifespan_context(app_rabbitmq_down).__aexit__(None, None, None)