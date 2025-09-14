import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI, Request, Response, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from httpx import AsyncClient
from uuid import uuid4
import asyncio
import dataclasses

from redis.asyncio import Redis

from app.idempotency import idempotency_middleware, get_redis_client
from app.config import Settings
from app.schemas import SendSmsResponse, ErrorResponse
from app.main import custom_json_serializer
from datetime import datetime, timedelta

# Mock settings for testing
@pytest.fixture
def mock_settings():
    settings = Settings(
        app_name="test-server-a",
        redis_url="redis://localhost:6379/0",
        rabbit_host="localhost",
        rabbit_port=5672,
        rabbit_user="guest",
        rabbit_pass="guest",
        outbound_sms_exchange="sms_outbound_exchange",
        outbound_sms_queue="sms_outbound_queue",
        idempotency_ttl_seconds=10,  # Short TTL for testing
        heartbeat_interval_seconds=60,
        PROVIDER_GATE_ENABLED=True,
        QUOTA_PREFIX="quota",
    )
    return settings

# Mock Redis client
@pytest.fixture
def mock_redis_client():
    mock = AsyncMock(spec=Redis)
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=None)
    mock.expire = AsyncMock(return_value=None)
    return mock

# Mock FastAPI app with idempotency middleware
@pytest.fixture
def test_app(mock_settings, mock_redis_client):
    app = FastAPI()

    # Since we are testing the middleware in isolation, we don't need the full app setup.
    # We just need to patch the dependencies used by the middleware.
    with patch('app.idempotency.settings', mock_settings), \
         patch('app.idempotency.get_redis_client', return_value=mock_redis_client):

        app.middleware("http")(idempotency_middleware)

        @app.post("/test-endpoint")
        async def test_endpoint(request: Request):
            return JSONResponse(content={"status": "ok"})

        @app.post("/test-error-endpoint")
        async def test_error_endpoint(request: Request):
            raise HTTPException(status_code=400, detail={"error_code": "TEST_ERROR", "message": "This is a test error"})

        # Add a minimal client object to the request state for the middleware to use.
        @app.middleware("http")
        async def add_client_to_state(request: Request, call_next):
            request.state.client = MagicMock()
            request.state.client.api_key = "client_key_1"
            response = await call_next(request)
            return response

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
    mock_redis_client.expire.assert_called_once_with(f"idem:client_key_1:{idempotency_key}", mock_settings.idempotency_ttl_seconds)

    # Verify the stored content
    stored_data = json.loads(mock_redis_client.set.call_args[0][1])
    assert stored_data["status_code"] == status.HTTP_200_OK
    assert json.loads(stored_data["body"])["status"] == "ok"

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
    mock_redis_client.expire.assert_not_called()


@pytest.mark.asyncio
async def test_second_request_returns_cached_error_response(test_app, mock_redis_client, mock_settings):
    idempotency_key = "test-key-3"
    error_body = json.dumps(dataclasses.asdict(ErrorResponse(
        error_code="INVALID_PAYLOAD",
        message="Cached error",
        tracking_id=uuid4()
    )), default=custom_json_serializer)
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
    mock_redis_client.expire.assert_called_once_with(f"idem:client_key_1:{idempotency_key}", mock_settings.idempotency_ttl_seconds)

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
        ex=mock_settings.idempotency_ttl_seconds,
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
        ex=mock_settings.idempotency_ttl_seconds,
        nx=True
    )