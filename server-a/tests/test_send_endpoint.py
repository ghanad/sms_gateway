import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock, ANY
from fastapi import FastAPI, status, HTTPException, Request
from fastapi.testclient import TestClient
from httpx import AsyncClient
from uuid import UUID, uuid4
from datetime import datetime

from app.main import app, http_exception_handler
from app.schemas import SendSmsRequest, SendSmsResponse, ErrorResponse
from app.config import Settings, ClientConfig
from app.auth import ClientContext

# Apply the exception handler to the test app instance
app.add_exception_handler(HTTPException, http_exception_handler)

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

# Mock dependencies for the send_sms endpoint
@pytest.fixture
def mock_dependencies(mock_settings):
    with patch('app.config.get_settings', return_value=mock_settings), \
         patch('app.idempotency.settings', mock_settings), \
         patch('app.quota.get_settings', return_value=mock_settings), \
         patch('app.rabbit.get_settings', return_value=mock_settings), \
         patch('app.heartbeat.get_settings', return_value=mock_settings):

        mock_get_client_context = AsyncMock(return_value=ClientContext(api_key="client_key_1", user_id=1, username="Test Client 1", is_active=True, daily_quota=100))
        mock_provider_gate_process_providers = MagicMock(return_value=["ProviderA"])
        mock_enforce_daily_quota = AsyncMock()
        mock_publish_sms_message = AsyncMock()
        mock_redis_client = AsyncMock()
        mock_redis_client.get.return_value = None # No cached response by default
        mock_redis_client.set.return_value = True
        mock_redis_client.expire.return_value = True
        mock_rabbitmq_connection = AsyncMock()
        mock_rabbitmq_channel = AsyncMock()
        mock_rabbitmq_connection.channel.return_value.__aenter__.return_value = mock_rabbitmq_channel
        mock_rabbitmq_connection.is_closed = False

        with patch('app.main.get_client_context', new=mock_get_client_context), \
             patch('app.main.provider_gate.process_providers', new=mock_provider_gate_process_providers), \
             patch('app.main.enforce_daily_quota', new=mock_enforce_daily_quota), \
             patch('app.main.publish_sms_message', new=mock_publish_sms_message), \
             patch('app.main.get_redis_client', return_value=mock_redis_client), \
             patch('app.idempotency.get_redis_client', return_value=mock_redis_client), \
             patch('app.quota.get_redis_client', return_value=mock_redis_client), \
             patch('app.rabbit.get_rabbitmq_connection', return_value=mock_rabbitmq_connection), \
             patch('app.heartbeat.aio_pika.connect_robust', return_value=mock_rabbitmq_connection), \
             patch('app.main.redis_client', new=mock_redis_client), \
             patch('app.main.rabbitmq_connection', new=mock_rabbitmq_connection), \
             patch('app.main.rabbitmq_channel', new=mock_rabbitmq_channel):
            yield {
                "get_client_context": mock_get_client_context,
                "provider_gate_process_providers": mock_provider_gate_process_providers,
                "enforce_daily_quota": mock_enforce_daily_quota,
                "publish_sms_message": mock_publish_sms_message,
                "redis_client": mock_redis_client,
                "rabbitmq_connection": mock_rabbitmq_connection,
                "rabbitmq_channel": mock_rabbitmq_channel
            }

@pytest.mark.asyncio
async def test_send_sms_success(mock_dependencies):
    sms_request_payload = {
        "to": "+1234567890",
        "text": "Hello, world!",
        "providers": ["ProviderA"],
        "ttl_seconds": 3600
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sms/send",
            headers={"API-Key": "client_key_1"},
            json=sms_request_payload
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["message"] == "Request accepted for processing."
    assert "tracking_id" in response_data
    assert UUID(response_data["tracking_id"]) # Ensure it's a valid UUID

    mock_dependencies["get_client_context"].assert_called_once()
    mock_dependencies["provider_gate_process_providers"].assert_called_once_with(
        ANY, sms_request_payload["providers"]
    )
    mock_dependencies["enforce_daily_quota"].assert_called_once()
    mock_dependencies["publish_sms_message"].assert_called_once()
    
    # Verify arguments to publish_sms_message
    args, kwargs = mock_dependencies["publish_sms_message"].call_args
    assert kwargs["client_key"] == "client_key_1"
    assert kwargs["to"] == sms_request_payload["to"]
    assert kwargs["text"] == sms_request_payload["text"]
    assert kwargs["ttl_seconds"] == sms_request_payload["ttl_seconds"]
    assert kwargs["providers_original"] == sms_request_payload["providers"]
    assert kwargs["providers_effective"] == ["ProviderA"]
    assert isinstance(kwargs["tracking_id"], UUID)

@pytest.mark.asyncio
async def test_send_sms_idempotency_key_stores_response(mock_dependencies, mock_settings):
    idempotency_key = "unique-idempotency-key"
    sms_request_payload = {
        "to": "+1234567890",
        "text": "Hello, world!",
        "providers": ["ProviderA"],
        "ttl_seconds": 3600
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sms/send",
            headers={"API-Key": "client_key_1", "Idempotency-Key": idempotency_key},
            json=sms_request_payload
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    mock_dependencies["redis_client"].set.assert_called_once()
    
    # Verify the key and expiration
    set_args, set_kwargs = mock_dependencies["redis_client"].set.call_args
    assert set_args[0] == f"idem:client_key_1:{idempotency_key}"
    assert set_kwargs["ex"] == mock_settings.IDEMPOTENCY_TTL_SECONDS

    # Verify the stored content
    stored_data = json.loads(set_args[1])
    assert stored_data["status_code"] == status.HTTP_202_ACCEPTED
    assert json.loads(stored_data["body"])["success"] is True
    assert "tracking_id" in json.loads(stored_data["body"])

@pytest.mark.asyncio
async def test_send_sms_idempotency_key_returns_cached_response(mock_dependencies):
    idempotency_key = "cached-key"
    cached_tracking_id = uuid4()
    cached_response_body = SendSmsResponse(
        success=True,
        message="Request accepted for processing.",
        tracking_id=cached_tracking_id
    ).model_dump_json()
    cached_data = {
        "status_code": status.HTTP_202_ACCEPTED,
        "body": cached_response_body,
        "media_type": "application/json",
        "cached_at": datetime.utcnow().isoformat()
    }
    mock_dependencies["redis_client"].get.return_value = json.dumps(cached_data).encode('utf-8')

    sms_request_payload = {
        "to": "+1234567890",
        "text": "Hello, world!",
        "providers": ["ProviderA"],
        "ttl_seconds": 3600
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sms/send",
            headers={"API-Key": "client_key_1", "Idempotency-Key": idempotency_key},
            json=sms_request_payload
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["tracking_id"] == str(cached_tracking_id)
    mock_dependencies["redis_client"].get.assert_called_once_with(f"idem:client_key_1:{idempotency_key}")
    mock_dependencies["publish_sms_message"].assert_not_called() # Should not publish again
    mock_dependencies["enforce_daily_quota"].assert_not_called() # Should not enforce quota again

@pytest.mark.asyncio
async def test_send_sms_unauthorized(mock_dependencies):
    sms_request_payload = {
        "to": "+1234567890",
        "text": "Hello, world!",
    }
    mock_dependencies["get_client_context"].side_effect = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error_code": "UNAUTHORIZED", "message": "Invalid API key"}
    )

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sms/send",
            headers={"API-Key": "invalid_key"},
            json=sms_request_payload
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["error_code"] == "UNAUTHORIZED"
    mock_dependencies["get_client_context"].assert_called_once()
    mock_dependencies["provider_gate_process_providers"].assert_not_called()
    mock_dependencies["enforce_daily_quota"].assert_not_called()
    mock_dependencies["publish_sms_message"].assert_not_called()

@pytest.mark.asyncio
async def test_send_sms_invalid_payload(mock_dependencies):
    sms_request_payload = {
        "to": "invalid-phone-number", # Invalid E.164 format
        "text": "Hello, world!",
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sms/send",
            headers={"API-Key": "client_key_1"},
            json=sms_request_payload
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY # Pydantic validation error
    assert response.json()["error_code"] == "INVALID_PAYLOAD" # Our custom handler maps 422 to INVALID_PAYLOAD
    mock_dependencies["get_client_context"].assert_called_once()
    mock_dependencies["provider_gate_process_providers"].assert_not_called()
    mock_dependencies["enforce_daily_quota"].assert_not_called()
    mock_dependencies["publish_sms_message"].assert_not_called()

@pytest.mark.asyncio
async def test_send_sms_provider_gate_rejection(mock_dependencies):
    sms_request_payload = {
        "to": "+1234567890",
        "text": "Hello, world!",
        "providers": ["UnknownProvider"]
    }
    mock_dependencies["provider_gate_process_providers"].side_effect = HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"error_code": "UNKNOWN_PROVIDER", "message": "Unknown provider"}
    )

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sms/send",
            headers={"API-Key": "client_key_1"},
            json=sms_request_payload
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["error_code"] == "UNKNOWN_PROVIDER"
    mock_dependencies["provider_gate_process_providers"].assert_called_once()
    mock_dependencies["enforce_daily_quota"].assert_not_called() # Quota should not be checked
    mock_dependencies["publish_sms_message"].assert_not_called()

@pytest.mark.asyncio
async def test_send_sms_quota_rejection(mock_dependencies):
    sms_request_payload = {
        "to": "+1234567890",
        "text": "Hello, world!",
        "providers": ["ProviderA"]
    }
    mock_dependencies["enforce_daily_quota"].side_effect = HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"error_code": "TOO_MANY_REQUESTS", "message": "Daily SMS quota exceeded."}
    )

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sms/send",
            headers={"API-Key": "client_key_1"},
            json=sms_request_payload
        )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.json()["error_code"] == "TOO_MANY_REQUESTS"
    mock_dependencies["provider_gate_process_providers"].assert_called_once()
    mock_dependencies["enforce_daily_quota"].assert_called_once()
    mock_dependencies["publish_sms_message"].assert_not_called()

@pytest.mark.asyncio
async def test_send_sms_rabbitmq_failure(mock_dependencies):
    sms_request_payload = {
        "to": "+1234567890",
        "text": "Hello, world!",
        "providers": ["ProviderA"]
    }
    mock_dependencies["publish_sms_message"].side_effect = Exception("RabbitMQ connection error")

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sms/send",
            headers={"API-Key": "client_key_1"},
            json=sms_request_payload
        )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["error_code"] == "INTERNAL_ERROR"
    mock_dependencies["publish_sms_message"].assert_called_once()