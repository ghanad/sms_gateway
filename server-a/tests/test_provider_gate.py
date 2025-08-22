import pytest
from fastapi import HTTPException, Request, status
from unittest.mock import MagicMock, AsyncMock

from app.provider_gate import ProviderGate
from app.config import Settings, ProviderConfig

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
        QUOTA_PREFIX="quota",
        HEARTBEAT_INTERVAL_SECONDS=60,
        CLIENT_CONFIG='{"client_key_1":{"name":"Test Client 1","is_active":true,"daily_quota":100}}',
        PROVIDERS_CONFIG='''{
            "ProviderA":{"is_active":true,"is_operational":true,"aliases":["provider-a"]},
            "ProviderB":{"is_active":false,"is_operational":true},
            "ProviderC":{"is_active":true,"is_operational":false},
            "ProviderD":{"is_active":true,"is_operational":true,"aliases":["provider-d-alias"]},
            "ProviderE":{"is_active":true,"is_operational":true}
        }'''
    )
    # Manually trigger computed fields to ensure they are populated
    _ = settings.clients
    _ = settings.providers
    _ = settings.provider_alias_map
    return settings

@pytest.fixture
def provider_gate_instance(mock_settings):
    # Temporarily override get_settings to return our mock settings
    # This is a bit hacky but works for testing dependencies
    from app import config
    original_get_settings = config.get_settings
    config.get_settings = lambda: mock_settings
    
    gate = ProviderGate()
    
    # Restore original get_settings after test
    config.get_settings = original_get_settings
    return gate

@pytest.fixture
def mock_request():
    request = MagicMock(spec=Request)
    request.state.client = MagicMock()
    request.state.client.api_key = "client_key_1"
    return request

def test_smart_selection_no_providers_available(provider_gate_instance, mock_request):
    # Temporarily disable all providers in the mock settings
    for provider_name in provider_gate_instance.providers_config:
        provider_gate_instance.providers_config[provider_name].is_active = False
        provider_gate_instance.providers_config[provider_name].is_operational = False

    with pytest.raises(HTTPException) as exc_info:
        provider_gate_instance.process_providers(mock_request, None)
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc_info.value.detail["error_code"] == "NO_PROVIDER_AVAILABLE"

def test_smart_selection_with_providers_available(provider_gate_instance, mock_request):
    # Ensure some providers are active and operational
    provider_gate_instance.providers_config["ProviderA"].is_active = True
    provider_gate_instance.providers_config["ProviderA"].is_operational = True
    provider_gate_instance.providers_config["ProviderE"].is_active = True
    provider_gate_instance.providers_config["ProviderE"].is_operational = True

    result = provider_gate_instance.process_providers(mock_request, None)
    assert result == [] # Smart selection returns empty list for Server B to choose

def test_unknown_provider_rejection(provider_gate_instance, mock_request):
    with pytest.raises(HTTPException) as exc_info:
        provider_gate_instance.process_providers(mock_request, ["UnknownProvider"])
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert exc_info.value.detail["error_code"] == "UNKNOWN_PROVIDER"
    assert "UnknownProvider" in exc_info.value.detail["message"]

def test_exclusive_provider_disabled_rejection(provider_gate_instance, mock_request):
    with pytest.raises(HTTPException) as exc_info:
        provider_gate_instance.process_providers(mock_request, ["ProviderB"]) # ProviderB is inactive
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.detail["error_code"] == "PROVIDER_DISABLED"
    assert "ProviderB" in exc_info.value.detail["message"]

def test_exclusive_provider_operational_rejection(provider_gate_instance, mock_request):
    with pytest.raises(HTTPException) as exc_info:
        provider_gate_instance.process_providers(mock_request, ["ProviderC"]) # ProviderC is not operational
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.detail["error_code"] == "PROVIDER_DISABLED"
    assert "ProviderC" in exc_info.value.detail["message"]

def test_exclusive_provider_success(provider_gate_instance, mock_request):
    result = provider_gate_instance.process_providers(mock_request, ["ProviderA"])
    assert result == ["ProviderA"]

def test_prioritized_failover_filters_disabled(provider_gate_instance, mock_request):
    # ProviderB is inactive, ProviderC is not operational
    result = provider_gate_instance.process_providers(mock_request, ["ProviderA", "ProviderB", "ProviderC", "ProviderD"])
    assert result == ["ProviderA", "ProviderD"]

def test_prioritized_failover_all_disabled_rejection(provider_gate_instance, mock_request):
    with pytest.raises(HTTPException) as exc_info:
        provider_gate_instance.process_providers(mock_request, ["ProviderB", "ProviderC"])
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.detail["error_code"] == "ALL_PROVIDERS_DISABLED"

def test_provider_gate_disabled_bypasses_validation(mock_settings, mock_request):
    mock_settings.PROVIDER_GATE_ENABLED = False
    provider_gate_instance = ProviderGate() # Re-initialize with disabled gate

    # Should return requested providers (canonicalized) even if they are technically inactive/non-operational
    result = provider_gate_instance.process_providers(mock_request, ["ProviderB", "ProviderC", "ProviderA"])
    assert sorted(result) == sorted(["ProviderB", "ProviderC", "ProviderA"]) # Order might be preserved, but content is key

    # Unknown providers should still be filtered out if gate is disabled, but not raise an error
    result_with_unknown = provider_gate_instance.process_providers(mock_request, ["ProviderA", "UnknownProvider"])
    assert result_with_unknown == ["ProviderA"] # Unknown is simply ignored, no error

    # If no providers requested and gate disabled, return empty list
    result_no_providers = provider_gate_instance.process_providers(mock_request, None)
    assert result_no_providers == []

def test_provider_alias_mapping(provider_gate_instance, mock_request):
    result = provider_gate_instance.process_providers(mock_request, ["provider-a"])
    assert result == ["ProviderA"]

    result = provider_gate_instance.process_providers(mock_request, ["PROVIDER_A"])
    assert result == ["ProviderA"]

    result = provider_gate_instance.process_providers(mock_request, ["provider-d-alias"])
    assert result == ["ProviderD"]

def test_provider_alias_collision_detection():
    # This test specifically targets the config loading, not the gate itself
    with pytest.raises(ValueError, match="Alias collision"):
        Settings(
            SERVICE_NAME="test-server-a",
            SERVER_A_HOST="0.0.0.0",
            SERVER_A_PORT=8000,
            REDIS_URL="redis://localhost:6379/0",
            RABBITMQ_URL="amqp://guest:guest@localhost:5672/",
            PROVIDER_GATE_ENABLED=True,
            IDEMPOTENCY_TTL_SECONDS=86400,
            QUOTA_PREFIX="quota",
            HEARTBEAT_INTERVAL_SECONDS=60,
            CLIENT_CONFIG='{"client_key_1":{"name":"Test Client 1","is_active":true,"daily_quota":100}}',
            PROVIDERS_CONFIG='''{
                "ProviderX":{"is_active":true,"is_operational":true,"aliases":["common-alias"]},
                "ProviderY":{"is_active":true,"is_operational":true,"aliases":["common-alias"]}
            }'''
        )