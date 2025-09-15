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


def test_real_time_sync_of_disabled_provider():
    provider_name_for_api = "ProviderA"
    provider_slug_for_db = "provider-a"

    disable_cmd = [
        "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell",
        "-c",
        (
            f"from providers.models import SmsProvider; "
            f"p=SmsProvider.objects.get(slug='{provider_slug_for_db}'); "
            "p.is_active=False; p.save()"
        ),
    ]
    subprocess.run(disable_cmd, check=True)
    time.sleep(70)  # Wait for config broadcast
    response = _send_request(provider_name_for_api)
    assert response.status_code == 409
    body = response.json()
    assert body.get("error_code") == "PROVIDER_DISABLED"
    
    # Clean up state for other tests by re-enabling the provider
    enable_cmd = [
        "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c",
        (
            f"from providers.models import SmsProvider; "
            f"p=SmsProvider.objects.get(slug='{provider_slug_for_db}'); "
            "p.is_active=True; p.save()"
        ),
    ]
    subprocess.run(enable_cmd, check=True)
    time.sleep(1) # Small delay to ensure command completes


def test_startup_recovery_from_file_cache():
    provider_name_for_api = "ProviderA"
    provider_slug_for_db = "provider-a"

    # Step 1: Ensure the provider is disabled so server-a gets and caches this state
    disable_cmd = [
        "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c",
        (
            f"from providers.models import SmsProvider; "
            f"p=SmsProvider.objects.get(slug='{provider_slug_for_db}'); "
            "p.is_active=False; p.save()"
        ),
    ]
    subprocess.run(disable_cmd, check=True)
    time.sleep(70) # Wait for server-a to receive and cache the 'disabled' state

    # Step 2: Restart server-a. It should now load the disabled state from its file cache.
    subprocess.run(["docker", "compose", "restart", "server-a"], check=True)
    time.sleep(15) # Give server-a more time to start up properly

    # Step 3: Send a request. It should be rejected because the cached state is 'disabled'.
    response = _send_request(provider_name_for_api)
    assert response.status_code == 409
    body = response.json()
    assert body.get("error_code") == "PROVIDER_DISABLED"
    
    # Step 4: CLEANUP! Re-enable the provider so other test files are not affected.
    enable_cmd = [
        "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c",
        (
            f"from providers.models import SmsProvider; "
            f"p=SmsProvider.objects.get(slug='{provider_slug_for_db}'); "
            "p.is_active=True; p.save()"
        ),
    ]
    subprocess.run(enable_cmd, check=True)
    # No need to wait for broadcast here, as the next test file will have its own delays.