import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI, Request, status, HTTPException, Depends
from fastapi.responses import JSONResponse
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

    # Patch settings and redis client at the module level for consistency
    with patch('app.quota.settings', mock_settings), \
         patch('app.quota.get_redis_client', return_value=mock_redis_client):

        # Dummy auth dependency to simulate getting a client context
        async def get_test_client_context(request: Request) -> ClientContext:
            client = ClientContext(api_key="client_key_1", name="Test Client 1", is_active=True, daily_quota=10)
            request.state.client = client # Attach to request state
            return client

        async def get_unlimited_client_context(request: Request) -> ClientContext:
            client = ClientContext(api_key="client_key_unlimited", name="Unlimited Client", is_active=True, daily_quota=0)
            request.state.client = client
            return client

        @app.get("/test-quota", dependencies=[Depends(get_test_client_context), Depends(enforce_daily_quota)])
        async def test_endpoint_with_quota():
            return {"message": "Quota check passed"}

        @app.get("/test-quota-unlimited", dependencies=[Depends(get_unlimited_client_context), Depends(enforce_daily_quota)])
        async def test_endpoint_unlimited_quota():
            return {"message": "Quota check passed for unlimited client"}

        # The exception handler is crucial for testing rejection cases
        @app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail
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
def test_app_rejection(mock_settings, mock_redis_client):
    app = FastAPI()

    # Mock the provider gate dependency to raise a specific exception
    async def mock_provider_gate_rejection():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "UNKNOWN_PROVIDER", "message": "Unknown provider"}
        )

    # Mock client context dependency
    async def get_test_client_context(request: Request) -> ClientContext:
        client = ClientContext(api_key="client_key_1", name="Test Client 1", is_active=True, daily_quota=10)
        request.state.client = client
        return client

    with patch('app.quota.settings', mock_settings), \
         patch('app.quota.get_redis_client', return_value=mock_redis_client):

        # The endpoint depends on the client, the (failing) provider gate, and then the quota
        @app.post("/send-sms", dependencies=[
            Depends(get_test_client_context),
            Depends(mock_provider_gate_rejection),
            Depends(enforce_daily_quota) # This dependency should not be executed
        ])
        async def protected_endpoint():
            return {"message": "Should not be reached"}

        # Add the exception handler to the app
        @app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)

        yield app


@pytest.mark.asyncio
async def test_provider_gate_rejection_does_not_consume_quota(test_app_rejection, mock_redis_client):
    """
    Verify that if the ProviderGate rejects a request, the quota is not incremented.
    FastAPI's dependency system should stop processing dependencies after one raises an HTTPException.
    """
    mock_redis_client.incr.reset_mock()

    async with AsyncClient(app=test_app_rejection, base_url="http://test") as client:
        response = await client.post("/send-sms", json={"body": "test"})

    # Assert that the response is the one from the raised HTTPException
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["error_code"] == "UNKNOWN_PROVIDER"

    # Assert that the quota was not touched
    mock_redis_client.incr.assert_not_called()
