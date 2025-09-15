import os
import subprocess
import time
import json
import pytest
import requests
from requests.exceptions import RequestException
from uuid import uuid4

# This line ensures that these tests only run when the RUN_E2E environment variable is set to 1
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)

# --- Helper Functions ---

def _get_message(tracking_id: str) -> dict:
    """Retrieves message information from the server-b database using a tracking_id."""
    command_to_run = (
        "import json; from messaging.models import Message; from django.core.exceptions import ObjectDoesNotExist; "
        "try: "
        f"    m=Message.objects.get(tracking_id='{tracking_id}'); "
        "    print(json.dumps({'status': m.status, 'error': m.error_message})); "
        "except ObjectDoesNotExist: "
        "    print(json.dumps({'status': 'NOT_FOUND'})); "
    )
    cmd = [
        "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell",
        "--no-startup", "--command", command_to_run,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output_lines = result.stdout.strip().splitlines()
    json_output = output_lines[-1] if output_lines else "{}"
    return json.loads(json_output)

def poll_for_message_status(tracking_id: str, expected_status: str, timeout_seconds: int = 30, interval_seconds: int = 2) -> dict:
    """Actively polls the database for a specific message status."""
    start_time = time.time()
    last_status = None
    while time.time() - start_time < timeout_seconds:
        message_data = _get_message(tracking_id)
        last_status = message_data.get('status')
        if last_status == expected_status:
            print(f"\\nMessage {tracking_id} reached status '{expected_status}' successfully.")
            return message_data
        time.sleep(interval_seconds)
    
    pytest.fail(f"Timeout: Message {tracking_id} did not reach status '{expected_status}' within {timeout_seconds}s. Last seen status: '{last_status}'.")


@pytest.fixture(scope="module", autouse=True)
def ensure_provider_is_active():
    """Ensures 'ProviderA' is active and synced before tests in this file run."""
    # ... (fixture from previous step remains the same)
    provider_name = "ProviderA"
    provider_slug = "provider-a"
    print(f"\\n[Fixture] Ensuring '{provider_name}' is active and config is synced...")
    enable_cmd = [
        "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c",
        (
            f"from providers.models import SmsProvider; "
            f"p, _ = SmsProvider.objects.get_or_create(slug='{provider_slug}'); "
            f"p.name='{provider_name}'; p.is_active=True; p.save()"
        ),
    ]
    subprocess.run(enable_cmd, check=True, capture_output=True)
    broadcast_cmd = [
        "docker", "compose", "exec", "-T", "server-b", "python", "manage.py", "shell", "-c",
        "from core.state_broadcaster import publish_full_state; publish_full_state.delay()"
    ]
    subprocess.run(broadcast_cmd, check=True, capture_output=True)
    time.sleep(10)
    print("Provider state reset and synced.")
    yield


def wait_for_server_a_ready(max_retries=10, delay_seconds=8):
    """Waits for server-a to be responsive."""
    # ... (this function can remain as it is from the previous step)
    print("Waiting for Server A to become ready...")
    for i in range(max_retries):
        try:
            response = requests.get("http://localhost:8001/healthz", timeout=5)
            if response.status_code == 200:
                print("Server A is ready!")
                return
        except RequestException as e:
            print(f"Attempt {i + 1}/{max_retries}: Could not connect to Server A ({e}). Retrying in {delay_seconds}s...")
            time.sleep(delay_seconds)
    pytest.fail("Server A did not become ready within the specified timeout.")


def _send_request():
    """Sends a standard request to send an SMS to Server A."""
    payload = {"to": "+15555550100", "text": "test message", "providers": ["ProviderA"]}
    headers = {"API-Key": "api_key_for_service_A", "Idempotency-Key": str(uuid4())}
    resp = requests.post("http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()["tracking_id"]

# --- Refactored Tests ---

def test_successful_end_to_end_flow():
    """Tests a complete successful end-to-end scenario."""
    wait_for_server_a_ready()
    
    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)

    tracking_id = _send_request()
    
    # Replace sleep with active polling
    message = poll_for_message_status(tracking_id, "SENT", timeout_seconds=25)
    assert message["status"] == "SENT"

    logs = requests.get("http://localhost:5005/logs", timeout=5).json()
    assert len(logs) == 1


def test_full_retry_and_recovery():
    """Tests the full retry mechanism in case of a transient failure."""
    wait_for_server_a_ready()

    # Configure mock for transient error and send the message
    requests.post("http://localhost:5005/config", json={"mode": "transient"}, timeout=5)
    tracking_id = _send_request()
    
    # Poll for AWAITING_RETRY status
    message = poll_for_message_status(tracking_id, "AWAITING_RETRY", timeout_seconds=20)
    assert message["status"] == "AWAITING_RETRY"
    assert message["error"] is not None

    # Reconfigure mock for success and poll for final SENT status
    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)
    
    # Timeout must be longer than the Celery backoff (60s for first retry)
    final_message = poll_for_message_status(tracking_id, "SENT", timeout_seconds=70)
    assert final_message["status"] == "SENT"