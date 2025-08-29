# tests/e2e/test_config_sync.py
import subprocess
import time
from uuid import uuid4
import pytest
import requests

@pytest.fixture(scope="module", autouse=True)
def compose_environment():
    """Brings up the Docker Compose environment, waits for it to be healthy, and seeds required data."""
    print("Starting Docker Compose environment...")
    # The --wait flag uses the healthchecks in docker-compose.yml to ensure services are ready.
    subprocess.run(["docker", "compose", "up", "-d", "--build", "--wait"], check=True)
    print("Services are up and healthy.")

    # A single, robust script to create all necessary data for tests.
    init_script = (
        "from django.contrib.auth.models import User;"
        "from user_management.models import Profile;"
        "from providers.models import SmsProvider;"
        "user, _ = User.objects.get_or_create(username='testuser');"
        "Profile.objects.update_or_create(user=user, defaults={'api_key': 'api_key_for_e2e_tests'});"
        "SmsProvider.objects.get_or_create("
        "    name='ProviderA', "
        "    defaults={"
        "        'slug': 'provider-a',"
        "        'send_url': 'http://example.com/send',"
        "        'balance_url': 'http://example.com/balance',"
        "        'default_sender': '12345',"
        "        'is_active': True"
        "    }"
        ")"
    )

    # Retry loop in case the app needs a moment to be fully ready after health check passes
    for i in range(5):
        result = subprocess.run(
            [
                "docker", "compose", "exec", "-T", "server-b",
                "python", "manage.py", "shell", "-c", init_script
            ]
        )
        if result.returncode == 0:
            print("Initial data seeded successfully.")
            break
        print(f"Attempt {i+1}/5 to seed data failed. Retrying in 2 seconds...")
        time.sleep(2)
    else:
        raise RuntimeError("Failed to seed initial data into server-b after multiple attempts.")

    yield
    
    print("Tearing down Docker Compose environment...")
    subprocess.run(["docker", "compose", "down", "-v", "--remove-orphans"], check=True)


def _send_request(provider_name: str) -> requests.Response:
    """Helper function to send a standard API request to server-a."""
    payload = {
        "to": "+15555550100",
        "text": "test message",
        "providers": [provider_name],
    }
    headers = {
        "API-Key": "api_key_for_e2e_tests",  # Use the consistent API key
        "Idempotency-Key": str(uuid4()),
    }
    return requests.post(
        "http://localhost:8001/api/v1/sms/send",
        json=payload,
        headers=headers,
        timeout=10,
    )


def _set_provider_active_status(provider_name: str, is_active: bool):
    """Helper function to enable or disable a provider via a manage.py command."""
    py_script = (
        f"from providers.models import SmsProvider; "
        f"p = SmsProvider.objects.get(name='{provider_name}'); "
        f"p.is_active={is_active}; p.save()"
    )
    subprocess.run(
        ["docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c", py_script],
        check=True
    )


def test_real_time_sync_and_recovery_flow():
    """
    This combined test validates both real-time sync and startup recovery in a single, logical flow.
    """
    provider_name = "ProviderA"

    # --- Part 1: Test Real-time Sync ---

    # 1a. Ensure provider is active and wait for sync
    print("\n[TEST] Ensuring provider is active...")
    _set_provider_active_status(provider_name, True)
    time.sleep(65)  # Wait for Celery Beat to run and server-a to consume

    # 1b. Verify that requests succeed when provider is active
    print("[TEST] Verifying API call succeeds when provider is active...")
    ok_response = _send_request(provider_name)
    assert ok_response.status_code == 202, f"Expected 202, got {ok_response.status_code}. Body: {ok_response.text}"

    # 1c. Disable the provider and wait for sync
    print("[TEST] Disabling provider...")
    _set_provider_active_status(provider_name, False)
    time.sleep(65)

    # 1d. Verify that requests now fail
    print("[TEST] Verifying API call fails when provider is disabled...")
    fail_response = _send_request(provider_name)
    assert fail_response.status_code == 409
    assert fail_response.json().get("error_code") == "PROVIDER_DISABLED"
    print("✅ Real-time sync test passed.")

    # --- Part 2: Test Startup Recovery ---
    # The provider is currently disabled, and server-a's local cache file should reflect this.
    
    # 2a. Restart server-a to force it to read from its local cache
    print("[TEST] Restarting server-a to test recovery from cache...")
    subprocess.run(["docker", "compose", "restart", "server-a"], check=True)
    time.sleep(10) # Give it time to start up

    # 2b. Immediately send the request. It should fail because it loaded the "disabled" state from the file.
    print("[TEST] Verifying API call still fails immediately after restart...")
    recovery_response = _send_request(provider_name)
    assert recovery_response.status_code == 409
    assert recovery_response.json().get("error_code") == "PROVIDER_DISABLED"
    print("✅ Startup recovery test passed.")

    # --- Cleanup ---
    # Re-enable the provider for a clean state in case of local test reruns.
    _set_provider_active_status(provider_name, True)