import pytest
import json
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI, Request, Response, status
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.idempotency import idempotency_middleware, get_redis_client
from app.config import Settings
from app.schemas import SendSmsResponse, ErrorResponse
from datetime import datetime, timedelta

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
        IDEMPOTENCY_TTL_SECONDS=10, # Short TTL for testing
        QUOTA_PREFIX="quota",
        HEARTBEAT_INTERVAL_SECONDS=60,
        CLIENT_CONFIG='{"client_key_1":{"name":"Test Client 1","is_active":true,"daily_quota":100}}',
        PROVIDERS_CONFIG='{"ProviderA":{"is_active":true,"is_operational":true}}'
    )
    _ = settings.clients
    _ = settings.providers
    _ = settings.provider_alias_map
    return settings

# Mock Redis client
@pytest.fixture
def mock_redis_client():
    mock = AsyncMock(spec=Redis)
    mock.get.return_value = None
    mock.set.return_value = None
    mock.expire.return_value = None
    return mock

# Mock FastAPI app with idempotency middleware
@pytest.fixture
def test_app(mock_settings, mock_redis_client):
    app = FastAPI()

    # Patch get_settings and get_redis_client for the app
    with patch('app.config.get_settings', return_value=mock_settings), \
         patch('app.idempotency.get_redis_client', return_value=mock_redis_client), \
         patch('app.main.get_redis_client', return_value=mock_redis_client): # Also patch in main for send_sms endpoint

        @app.middleware("http")
        async def add_idempotency_middleware(request: Request, call_next):
            # Manually set client state for testing middleware in isolation
            request.state.client = AsyncMock()
            request.state.client.api_key = "client_key_1"
            return await idempotency_middleware(request, call_next)

        @app.post("/test-endpoint")
        async def test_endpoint(request: Request):
            # Simulate some processing
            await asyncio.sleep(0.01)
            return JSONResponse(
                content={"success": True, "message": "Processed successfully", "tracking_id": str(uuid4())},
                status_code=status.HTTP_200_OK
            )

        @app.post("/test-error-endpoint")
        async def test_error_endpoint(request: Request):
            await asyncio.sleep(0.01)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_PAYLOAD", "message": "Invalid input"}
            )

        # Custom exception handler for HTTPException to return ErrorResponse schema
        @app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            error_response = ErrorResponse(
                error_code=exc.detail.get("error_code", "INTERNAL_ERROR"),
                message=exc.detail.get("message", "An unexpected error occurred."),
                details=exc.detail.get("details")
            )
            return JSONResponse(
                status_code=exc.status_code,
                content=error_response.model_dump(exclude_none=True)
            )

        yield app

@pytest.mark.asyncio
async def test_first_request_stores_response(test_app, mock_redis_client, mock_settings):
    idempotency_key = "test-key-1"
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        response = await client.post(
            "/test-endpoint",
            headers={"Idempotency-Key": idempotency_key, "API-Key": "client_key_1"},
            json={"data": "some_data"}
        )

    assert response.status_code == status.HTTP_200_OK
    mock_redis_client.get.assert_called_once_with(f"idem:client_key_1:{idempotency_key}")
    mock_redis_client.set.assert_called_once()
    mock_redis_client.expire.assert_called_once_with(f"idem:client_key_1:{idempotency_key}", mock_settings.IDEMPOTENCY_TTL_SECONDS)

    # Verify the stored content
    stored_data = json.loads(mock_redis_client.set.call_args[0][1])
    assert stored_data["status_code"] == status.HTTP_200_OK
    assert json.loads(stored_data["body"])["success"] is True

@pytest.mark.asyncio
async def test_second_request_returns_cached_success_response(test_app, mock_redis_client, mock_settings):
    idempotency_key = "test-key-2"
    cached_body = json.dumps({"success": True, "message": "Cached success", "tracking_id": str(uuid4())})
    cached_data = {
        "status_code": status.HTTP_200_OK,
        "body": cached_body,
        "media_type": "application/json",
        "cached_at": datetime.utcnow().isoformat()
    }
    mock_redis_client.get.return_value = json.dumps(cached_data).encode('utf-8')

    async with AsyncClient(app=test_app, base_url="http://test") as client:
        response = await client.post(
            "/test-endpoint",
            headers={"Idempotency-Key": idempotency_key, "API-Key": "client_key_1"},
            json={"data": "some_data"}
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == json.loads(cached_body)
    mock_redis_client.get.assert_called_once_with(f"idem:client_key_1:{idempotency_key}")
    mock_redis_client.set.assert_not_called() # Should not call set again
    mock_redis_client.expire.assert_called_once_with(f"idem:client_key_1:{idempotency_key}", mock_settings.IDEMPOTENCY_TTL_SECONDS)


@pytest.mark.asyncio
async def test_second_request_returns_cached_error_response(test_app, mock_redis_client, mock_settings):
    idempotency_key = "test-key-3"
    error_body = ErrorResponse(
        error_code="INVALID_PAYLOAD",
        message="Cached error",
        tracking_id=uuid4()
    ).model_dump_json()
    cached_data = {
        "status_code": status.HTTP_400_BAD_REQUEST,
        "body": error_body,
        "media_type": "application/json",
        "cached_at": datetime.utcnow().isoformat()
    }
    mock_redis_client.get.return_value = json.dumps(cached_data).encode('utf-8')

    async with AsyncClient(app=test_app, base_url="http://test") as client:
        response = await client.post(
            "/test-error-endpoint",
            headers={"Idempotency-Key": idempotency_key, "API-Key": "client_key_1"},
            json={"data": "invalid_data"}
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == json.loads(error_body)
    mock_redis_client.get.assert_called_once_with(f"idem:client_key_1:{idempotency_key}")
    mock_redis_client.set.assert_not_called()
    mock_redis_client.expire.assert_called_once_with(f"idem:client_key_1:{idempotency_key}", mock_settings.IDEMPOTENCY_TTL_SECONDS)

@pytest.mark.asyncio
async def test_request_without_idempotency_key_is_not_cached(test_app, mock_redis_client):
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        response = await client.post(
            "/test-endpoint",
            headers={"API-Key": "client_key_1"},
            json={"data": "some_data"}
        )

    assert response.status_code == status.HTTP_200_OK
    mock_redis_client.get.assert_not_called()
    mock_redis_client.set.assert_not_called()
    mock_redis_client.expire.assert_not_called()

@pytest.mark.asyncio
async def test_idempotency_key_with_different_client_api_key_is_different_key(test_app, mock_redis_client, mock_settings):
    idempotency_key = "shared-key"
    
    # First request with client_key_1
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        response1 = await client.post(
            "/test-endpoint",
            headers={"Idempotency-Key": idempotency_key, "API-Key": "client_key_1"},
            json={"data": "client1_data"}
        )
    assert response1.status_code == status.HTTP_200_OK
    mock_redis_client.set.assert_called_once_with(
        f"idem:client_key_1:{idempotency_key}",
        json.dumps(json.loads(mock_redis_client.set.call_args[0][1])), # Re-parse to compare content
        ex=mock_settings.IDEMPOTENCY_TTL_SECONDS,
        nx=True
    )
    mock_redis_client.set.reset_mock() # Reset mock for next assertion

    # Second request with a different client_key (assuming it's valid and set up in mock_settings)
    # For this test, we'll simulate a different client_key by changing the request.state.client.api_key
    # In a real scenario, this would come from a different auth dependency call.
    with patch('app.idempotency.get_settings', return_value=mock_settings):
        with patch('app.idempotency.get_redis_client', return_value=mock_redis_client):
            app = FastAPI()
            @app.middleware("http")
            async def add_idempotency_middleware_for_client2(request: Request, call_next):
                request.state.client = AsyncMock()
                request.state.client.api_key = "client_key_2" # Different client key
                return await idempotency_middleware(request, call_next)

            @app.post("/test-endpoint")
            async def test_endpoint_client2(request: Request):
                await asyncio.sleep(0.01)
                return JSONResponse(
                    content={"success": True, "message": "Processed by client 2", "tracking_id": str(uuid4())},
                    status_code=status.HTTP_200_OK
                )
            
            async with AsyncClient(app=app, base_url="http://test") as client2:
                response2 = await client2.post(
                    "/test-endpoint",
                    headers={"Idempotency-Key": idempotency_key, "API-Key": "client_key_2"},
                    json={"data": "client2_data"}
                )
    
    assert response2.status_code == status.HTTP_200_OK
    mock_redis_client.set.assert_called_once_with(
        f"idem:client_key_2:{idempotency_key}", # Key should be different
        json.dumps(json.loads(mock_redis_client.set.call_args[0][1])),
        ex=mock_settings.IDEMPOTENCY_TTL_SECONDS,
        nx=True
    )