import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.testclient import TestClient
from httpx import AsyncClient
from datetime import datetime, timedelta

from app.quota import enforce_daily_quota, get_redis_client
from app.config import Settings
from app.auth import ClientContext

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
        IDEMPOTENCY_TTL_SECONDS=86400,
        QUOTA_PREFIX="test-quota",
        HEARTBEAT_INTERVAL_SECONDS=60,
        CLIENT_CONFIG='{"client_key_1":{"name":"Test Client 1","is_active":true,"daily_quota":10}, "client_key_unlimited":{"name":"Unlimited Client","is_active":true,"daily_quota":0}}',
        PROVIDERS_CONFIG='{"ProviderA":{"is_active":true,"is_operational":true}}'
    )
    _ = settings.clients
    _ = settings.providers
    _ = settings.provider_alias_map
    return settings

# Mock Redis client
@pytest.fixture
def mock_redis_client():
    mock = AsyncMock()
    mock.incr.return_value = 1 # Default to first increment
    mock.expire.return_value = True
    return mock

# Mock FastAPI app for testing the dependency
@pytest.fixture
def test_app_quota(mock_settings, mock_redis_client):
    app = FastAPI()

    with patch('app.config.get_settings', return_value=mock_settings), \
         patch('app.quota.get_redis_client', return_value=mock_redis_client):

        @app.get("/test-quota")
        async def test_endpoint_with_quota(request: Request, client: ClientContext = Depends(lambda: ClientContext(api_key="client_key_1", name="Test Client 1", is_active=True, daily_quota=10))):
            request.state.client = client # Manually set client context
            await enforce_daily_quota(request)
            return {"message": "Quota check passed"}

        @app.get("/test-quota-unlimited")
        async def test_endpoint_unlimited_quota(request: Request, client: ClientContext = Depends(lambda: ClientContext(api_key="client_key_unlimited", name="Unlimited Client", is_active=True, daily_quota=0))):
            request.state.client = client
            await enforce_daily_quota(request)
            return {"message": "Quota check passed for unlimited client"}

        @app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"error_code": exc.detail["error_code"], "message": exc.detail["message"]}
            )
        yield app

@pytest.mark.asyncio
async def test_quota_enforced_below_limit(test_app_quota, mock_redis_client, mock_settings):
    mock_redis_client.incr.return_value = 5 # Current usage is 5, limit is 10
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    quota_key = f"{mock_settings.QUOTA_PREFIX}:client_key_1:{today_str}"

    async with AsyncClient(app=test_app_quota, base_url="http://test") as client:
        response = await client.get("/test-quota")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Quota check passed"}
    mock_redis_client.incr.assert_called_once_with(quota_key)
    mock_redis_client.expire.assert_not_called() # Not called if not first increment

@pytest.mark.asyncio
async def test_quota_enforced_at_limit(test_app_quota, mock_redis_client, mock_settings):
    mock_redis_client.incr.return_value = 10 # Current usage is 10, limit is 10
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    quota_key = f"{mock_settings.QUOTA_PREFIX}:client_key_1:{today_str}"

    async with AsyncClient(app=test_app_quota, base_url="http://test") as client:
        response = await client.get("/test-quota")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Quota check passed"}
    mock_redis_client.incr.assert_called_once_with(quota_key)
    mock_redis_client.expire.assert_not_called()

@pytest.mark.asyncio
async def test_quota_exceeded_rejection(test_app_quota, mock_redis_client, mock_settings):
    mock_redis_client.incr.return_value = 11 # Current usage is 11, limit is 10
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    quota_key = f"{mock_settings.QUOTA_PREFIX}:client_key_1:{today_str}"

    async with AsyncClient(app=test_app_quota, base_url="http://test") as client:
        response = await client.get("/test-quota")

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.json()["error_code"] == "TOO_MANY_REQUESTS"
    mock_redis_client.incr.assert_called_once_with(quota_key)
    mock_redis_client.expire.assert_not_called()

@pytest.mark.asyncio
async def test_quota_first_increment_sets_expiration(test_app_quota, mock_redis_client, mock_settings):
    mock_redis_client.incr.return_value = 1 # First increment
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    quota_key = f"{mock_settings.QUOTA_PREFIX}:client_key_1:{today_str}"

    async with AsyncClient(app=test_app_quota, base_url="http://test") as client:
        response = await client.get("/test-quota")

    assert response.status_code == status.HTTP_200_OK
    mock_redis_client.incr.assert_called_once_with(quota_key)
    mock_redis_client.expire.assert_called_once_with(quota_key, mock_settings.IDEMPOTENCY_TTL_SECONDS)

@pytest.mark.asyncio
async def test_unlimited_quota_client(test_app_quota, mock_redis_client, mock_settings):
    # For unlimited quota, incr should not be called
    mock_redis_client.incr.reset_mock()

    async with AsyncClient(app=test_app_quota, base_url="http://test") as client:
        response = await client.get("/test-quota-unlimited")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Quota check passed for unlimited client"}
    mock_redis_client.incr.assert_not_called()
    mock_redis_client.expire.assert_not_called()

# Test integration with Provider Gate (ensure rejections don't consume quota)
@pytest.fixture
def test_app_with_provider_gate_and_quota(mock_settings, mock_redis_client):
    app = FastAPI()

    with patch('app.config.get_settings', return_value=mock_settings), \
         patch('app.quota.get_redis_client', return_value=mock_redis_client):

        # Mock provider_gate to raise an HTTPException
        mock_provider_gate = AsyncMock()
        mock_provider_gate.process_providers.side_effect = HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "UNKNOWN_PROVIDER", "message": "Unknown provider"}
        )
        with patch('app.main.provider_gate', mock_provider_gate):
            @app.post("/send-sms-with-gate")
            async def send_sms_endpoint(request: Request, client: ClientContext = Depends(lambda: ClientContext(api_key="client_key_1", name="Test Client 1", is_active=True, daily_quota=10))):
                request.state.client = client
                # Simulate the pipeline order: Provider Gate -> Quota
                effective_providers = mock_provider_gate.process_providers(request, ["UnknownProvider"])
                await enforce_daily_quota(request) # This should not be reached if Provider Gate rejects
                return {"message": "Should not reach here"}

            @app.exception_handler(HTTPException)
            async def http_exception_handler(request: Request, exc: HTTPException):
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"error_code": exc.detail["error_code"], "message": exc.detail["message"]}
                )
            yield app

@pytest.mark.asyncio
async def test_provider_gate_rejection_does_not_consume_quota(test_app_with_provider_gate_and_quota, mock_redis_client):
    mock_redis_client.incr.reset_mock() # Ensure incr is not called

    async with AsyncClient(app=test_app_with_provider_gate_and_quota, base_url="http://test") as client:
        response = await client.post("/send-sms-with-gate", json={}) # Payload doesn't matter for this test

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["error_code"] == "UNKNOWN_PROVIDER"
    mock_redis_client.incr.assert_not_called() # Quota should not be incremented