# tests/e2e/test_config_sync.py

import os
import subprocess
import time
from uuid import uuid4
import pytest
import requests
from helpers import setup_test_user, wait_for_server_a_ready

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)

API_KEY = "e2e_config_sync_user"
USER_QUOTA = 100

def _send_config_request(provider_name: str) -> requests.Response:
    payload = {
        "to": "+15555550100",
        "text": "test message",
        "providers": [provider_name],
    }
    headers = {"API-Key": API_KEY, "Idempotency-Key": str(uuid4())}
    return requests.post("http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=10)

def _toggle_provider_status(provider_name: str, is_active: bool):
    """A helper to enable or disable a provider in server-b's database."""
    print(f"Setting provider '{provider_name}' is_active status to {is_active}")
    command_to_run = (
        f"from providers.models import SmsProvider; "
        f"p=SmsProvider.objects.get(slug='{provider_name.lower()}'); " # Using slug for consistency
        f"p.is_active={is_active}; p.save()"
    )
    cmd = [
        "docker", "compose", "exec", "-T", "server-b",
        "python", "manage.py", "shell", "--no-startup", "--command", command_to_run
    ]
    subprocess.run(cmd, check=True)

def test_real_time_sync_of_disabled_provider():
    """
    Tests that disabling a provider in server-b is reflected in server-a after the sync interval.
    """
    # Step 1: Set up the test user and a known initial state
    provider_slug = "magfa-default" # Assuming this is the slug for the default provider
    setup_test_user(api_key=API_KEY, daily_quota=USER_QUOTA)
    _toggle_provider_status(provider_slug, is_active=True) # Ensure it's active initially

    # Step 2: Wait for the system to be fully synced
    wait_for_server_a_ready(api_key=API_KEY)
    
    # Step 3: Verify that requests initially succeed
    print("Verifying provider is initially active...")
    response = _send_config_request(provider_slug)
    assert response.status_code == 202, f"Provider should be active, but got {response.status_code}"

    # Step 4: Disable the provider in the database
    _toggle_provider_status(provider_slug, is_active=False)

    # Step 5: Wait for longer than the Celery Beat schedule (60s) for the change to propagate
    print("Waiting for config state to sync (70 seconds)...")
    time.sleep(70)

    # Step 6: Send another request and expect it to be rejected
    print("Sending request to now-disabled provider...")
    response_after_sync = _send_config_request(provider_slug)
    assert response_after_sync.status_code == 409
    body = response_after_sync.json()
    assert body.get("error_code") == "PROVIDER_DISABLED"
    print("Test successful: server-a correctly rejected request.")

    # Step 7: Clean up by re-enabling the provider for other tests
    _toggle_provider_status(provider_slug, is_active=True)