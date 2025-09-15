import os
import subprocess
import time
import json
import pytest
import requests
from requests.exceptions import RequestException

# This line ensures that these tests only run when the RUN_E2E environment variable is set to 1
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)

@pytest.fixture(scope="module", autouse=True)
def ensure_provider_is_active():
    """
    This fixture runs once before any test in this file. It ensures that
    the primary test provider ('ProviderA') is active and that this state
    has been broadcasted to server-a. This prevents state pollution from
    previous test files.
    """
    provider_slug_for_db = "provider-a"
    print("\\nEnsuring 'ProviderA' is active and config is synced for sms_flow tests...")

    # Command to enable the provider, using get_or_create for safety
    enable_cmd = [
        "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c",
        (
            f"from providers.models import SmsProvider; "
            f"p, _ = SmsProvider.objects.get_or_create(slug='{provider_slug_for_db}', defaults={{'name':'ProviderA', 'send_url':'http://mock-provider-api:8000/send', 'balance_url':'http://mock-provider-api:8000/balance', 'default_sender':'100'}}); "
            f"p.is_active=True; p.save()"
        ),
    ]
    subprocess.run(enable_cmd, check=True, capture_output=True)

    # Command to immediately trigger a state broadcast from server-b
    broadcast_cmd = [
        "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c",
        "from core.state_broadcaster import publish_full_state; publish_full_state.delay()"
    ]
    subprocess.run(broadcast_cmd, check=True, capture_output=True)

    # Wait a few seconds for the broadcast message to be processed by server-a
    time.sleep(10)
    print("Provider state reset and synced.")
    yield


def wait_for_server_a_ready(max_retries=15, delay_seconds=8):
    """
    Continuously polls Server A until it's ready and has received its configuration from Server B.
    Success is defined as receiving any status code other than 503 (Service Unavailable).
    """
    print("Waiting for Server A to become ready and sync with Server B...")
    for i in range(max_retries):
        try:
            headers = {"API-Key": "api_key_for_service_A"}
            payload = {
                "to": "+15555550100", 
                "text": "readiness check",
                "providers": ["ProviderA"] 
            }

            response = requests.post(
                "http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=5
            )

            if response.status_code != 503:
                print(f"Server A is ready! (Received status code: {response.status_code})")
                return
            else:
                print(f"Attempt {i + 1}/{max_retries}: Server A is not ready yet (503). Retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)

        except RequestException as e:
            print(f"Attempt {i + 1}/{max_retries}: Could not connect to Server A ({e}). Retrying in {delay_seconds}s...")
            time.sleep(delay_seconds)

    pytest.fail("Server A did not become ready (did not stop returning 503) within the specified timeout.")


def _send_request():
    """Sends a standard request to send an SMS to Server A."""
    payload = {
        "to": "+15555550100",
        "text": "test message",
        "providers": ["ProviderA"],
    }
    headers = {"API-Key": "api_key_for_service_A"}
    resp = requests.post(
        "http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=10
    )
    resp.raise_for_status()
    return resp.json()["tracking_id"]


def _get_message(tracking_id: str) -> dict:
    """Retrieves message information from the server-b database using a tracking_id."""
    command_to_run = (
        "import json; from messaging.models import Message; "
        f"m=Message.objects.get(tracking_id='{tracking_id}'); "
        "print(json.dumps({'status': m.status, 'error': m.error_message}))"
    )

    cmd = [
        "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell",
        "--no-startup", "--command", command_to_run,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output_lines = result.stdout.strip().splitlines()
    json_output = output_lines[-1] if output_lines else "{}"
    return json.loads(json_output)


def test_successful_end_to_end_flow():
    """Tests a complete successful end-to-end scenario."""
    wait_for_server_a_ready()

    # The fixture has already ensured the provider is active.
    # Give a brief moment for any in-flight readiness check messages to clear.
    time.sleep(15)

    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)
    tracking_id = _send_request()
    time.sleep(20)

    message = _get_message(tracking_id)
    assert message["status"] == "SENT"

    logs = requests.get("http://localhost:5005/logs", timeout=5).json()
    assert len(logs) == 1


def test_full_retry_and_recovery():
    """Tests the full retry mechanism in case of a transient failure."""
    wait_for_server_a_ready()

    time.sleep(15)

    requests.post("http://localhost:5005/config", json={"mode": "transient"}, timeout=5)
    tracking_id = _send_request()
    time.sleep(15)

    message = _get_message(tracking_id)
    assert message["status"] == "AWAITING_RETRY"
    assert message["error"] is not None

    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)
    time.sleep(65)

    message = _get_message(tracking_id)
    assert message["status"] == "SENT"