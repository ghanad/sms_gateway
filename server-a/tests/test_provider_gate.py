import pytest
from fastapi import HTTPException, Request, status
from unittest.mock import MagicMock, patch

from app.provider_gate import ProviderGate
from app.config import Settings, ProviderConfig
from app.cache import PROVIDER_CONFIG_CACHE, PROVIDER_ALIAS_MAP_CACHE, build_provider_alias_map

@pytest.fixture
def mock_providers_config() -> dict:
    """Provides a baseline, mutable provider configuration for tests."""
    return {
        "ProviderA": ProviderConfig(is_active=True, is_operational=True, aliases=["provider-a"]),
        "ProviderB": ProviderConfig(is_active=False, is_operational=True),
        "ProviderC": ProviderConfig(is_active=True, is_operational=False),
        "ProviderD": ProviderConfig(is_active=True, is_operational=True, aliases=["provider-d-alias"]),
        "ProviderE": ProviderConfig(is_active=True, is_operational=True),
    }

@pytest.fixture
def provider_gate_instance(mock_providers_config: dict) -> ProviderGate:
    """
    Creates a ProviderGate instance with a mocked configuration.
    This fixture allows tests to modify the provider config on the fly.
    """
    PROVIDER_CONFIG_CACHE.clear()
    PROVIDER_CONFIG_CACHE.update(mock_providers_config)
    PROVIDER_ALIAS_MAP_CACHE.clear()
    PROVIDER_ALIAS_MAP_CACHE.update(build_provider_alias_map(mock_providers_config))

    with patch('app.config.get_settings') as mock_get_settings:
        mock_settings = MagicMock(spec=Settings)
        mock_settings.PROVIDER_GATE_ENABLED = True
        mock_get_settings.return_value = mock_settings
        gate = ProviderGate()
        return gate

@pytest.fixture
def mock_request() -> Request:
    """Creates a mock FastAPI request with a client context."""
    request = MagicMock(spec=Request)
    request.state.client = MagicMock()
    request.state.client.api_key = "client_key_1"
    return request

def test_smart_selection_no_providers_available(provider_gate_instance: ProviderGate, mock_request: Request):
    # Disable all providers for this specific test
    for config in provider_gate_instance.providers_config.values():
        config.is_active = False

    with pytest.raises(HTTPException) as exc_info:
        provider_gate_instance.process_providers(mock_request, None)
    
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc_info.value.detail["error_code"] == "NO_PROVIDER_AVAILABLE"

def test_smart_selection_with_providers_available(provider_gate_instance: ProviderGate, mock_request: Request):
    # The default fixture state has active providers
    result = provider_gate_instance.process_providers(mock_request, None)
    assert result == []  # Smart selection returns an empty list

def test_unknown_provider_rejection(provider_gate_instance: ProviderGate, mock_request: Request):
    with pytest.raises(HTTPException) as exc_info:
        provider_gate_instance.process_providers(mock_request, ["UnknownProvider"])
    
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert exc_info.value.detail["error_code"] == "UNKNOWN_PROVIDER"
    assert "UnknownProvider" in exc_info.value.detail["message"]

def test_exclusive_provider_disabled_rejection(provider_gate_instance: ProviderGate, mock_request: Request):
    # ProviderB is inactive in the default fixture
    with pytest.raises(HTTPException) as exc_info:
        provider_gate_instance.process_providers(mock_request, ["ProviderB"])
    
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.detail["error_code"] == "PROVIDER_DISABLED"

def test_exclusive_provider_operational_rejection(provider_gate_instance: ProviderGate, mock_request: Request):
    # ProviderC is not operational in the default fixture
    with pytest.raises(HTTPException) as exc_info:
        provider_gate_instance.process_providers(mock_request, ["ProviderC"])
        
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.detail["error_code"] == "PROVIDER_DISABLED"

def test_exclusive_provider_success(provider_gate_instance: ProviderGate, mock_request: Request):
    result = provider_gate_instance.process_providers(mock_request, ["ProviderA"])
    assert result == ["ProviderA"]

def test_prioritized_failover_filters_disabled(provider_gate_instance: ProviderGate, mock_request: Request):
    # ProviderB is inactive, ProviderC is not operational
    result = provider_gate_instance.process_providers(mock_request, ["ProviderA", "ProviderB", "ProviderC", "ProviderD"])
    assert result == ["ProviderA", "ProviderD"]

def test_prioritized_failover_all_disabled_rejection(provider_gate_instance: ProviderGate, mock_request: Request):
    with pytest.raises(HTTPException) as exc_info:
        provider_gate_instance.process_providers(mock_request, ["ProviderB", "ProviderC"])
        
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.detail["error_code"] == "ALL_PROVIDERS_DISABLED"

def test_provider_gate_disabled_bypasses_validation(provider_gate_instance: ProviderGate, mock_request: Request):
    provider_gate_instance.settings.PROVIDER_GATE_ENABLED = False

    # Should return canonical names even if inactive
    result = provider_gate_instance.process_providers(mock_request, ["ProviderB", "ProviderC", "ProviderA"])
    assert sorted(result) == sorted(["ProviderA", "ProviderB", "ProviderC"])

    # Unknown providers are still filtered out, but no error is raised
    result_with_unknown = provider_gate_instance.process_providers(mock_request, ["ProviderA", "UnknownProvider"])
    assert result_with_unknown == ["ProviderA"]

    # No providers requested should return an empty list
    result_no_providers = provider_gate_instance.process_providers(mock_request, None)
    assert result_no_providers == []

def test_provider_alias_mapping(provider_gate_instance: ProviderGate, mock_request: Request):
    result = provider_gate_instance.process_providers(mock_request, ["provider-a"])
    assert result == ["ProviderA"]

    result_upper = provider_gate_instance.process_providers(mock_request, ["PROVIDER_A"])
    assert result_upper == ["ProviderA"]

    result_alias = provider_gate_instance.process_providers(mock_request, ["provider-d-alias"])
    assert result_alias == ["ProviderD"]

def test_provider_alias_collision_detection():
    """Duplicate aliases should raise an error when building the map."""
    with pytest.raises(ValueError, match="Alias collision: 'alias-a' already maps to 'provider-a', cannot map to 'provider-b'"):
        build_provider_alias_map({
            'provider-a': ProviderConfig(is_active=True, is_operational=True, aliases=['alias-a']),
            'provider-b': ProviderConfig(is_active=True, is_operational=True, aliases=['ALIAS-A'])
        })