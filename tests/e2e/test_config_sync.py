import os
import subprocess
import time
from uuid import uuid4

import pytest
import requests

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)


def _send_request(provider_name: str) -> requests.Response:
    payload = {
        "to": "+15555550100",
        "text": "test message",
        "providers": [provider_name],
        "ttl_seconds": 3600,
    }
    headers = {
        "API-Key": "api_key_for_service_A",
        "Idempotency-Key": str(uuid4()),
    }
    return requests.post("http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=10)


def _trigger_broadcast():
    """Explicitly triggers the state broadcast task on server-b."""
    broadcast_cmd = [
        "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c",
        "from core.state_broadcaster import publish_full_state; publish_full_state.delay()"
    ]
    subprocess.run(broadcast_cmd, check=True, capture_output=True)


def test_real_time_sync_of_disabled_provider():
    provider_name = "ProviderA"
    provider_slug = "provider-a"

    try:
        # Step 1: Disable the provider
        disable_cmd = [
            "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c",
            f"from providers.models import SmsProvider; p=SmsProvider.objects.get(slug='{provider_slug}'); p.is_active=False; p.save()"
        ]
        subprocess.run(disable_cmd, check=True)

        # Step 2: Trigger broadcast and wait for sync
        _trigger_broadcast()
        time.sleep(10)

        # Step 3: Assert the provider is seen as disabled by server-a
        response = _send_request(provider_name)
        assert response.status_code == 409
        assert response.json().get("error_code") == "PROVIDER_DISABLED"
    finally:
        # Step 4: Cleanup - ALWAYS re-enable the provider
        enable_cmd = [
            "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c",
            f"from providers.models import SmsProvider; p=SmsProvider.objects.get(slug='{provider_slug}'); p.is_active=True; p.save()"
        ]
        subprocess.run(enable_cmd, check=True)
        _trigger_broadcast() # Broadcast the cleaned-up state
        time.sleep(5)


def test_startup_recovery_from_file_cache():
    provider_name = "ProviderA"
    provider_slug = "provider-a"
    try:
        # Step 1: Disable the provider and ensure server-a caches this state
        disable_cmd = [
            "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c",
            f"from providers.models import SmsProvider; p=SmsProvider.objects.get(slug='{provider_slug}'); p.is_active=False; p.save()"
        ]
        subprocess.run(disable_cmd, check=True)
        _trigger_broadcast()
        time.sleep(10)

        # Step 2: Restart server-a. It should load the 'disabled' state from its file cache.
        subprocess.run(["docker", "compose", "restart", "server-a"], check=True)
        time.sleep(15)

        # Step 3: Assert requests are rejected based on the cached 'disabled' state
        response = _send_request(provider_name)
        assert response.status_code == 409
        assert response.json().get("error_code") == "PROVIDER_DISABLED"
    finally:
        # Step 4: Cleanup - ALWAYS re-enable the provider
        enable_cmd = [
            "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c",
            f"from providers.models import SmsProvider; p=SmsProvider.objects.get(slug='{provider_slug}'); p.is_active=True; p.save()"
        ]
        subprocess.run(enable_cmd, check=True)
        _trigger_broadcast() # Broadcast the cleaned-up state