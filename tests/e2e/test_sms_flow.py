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


def wait_for_server_a_ready(max_retries=10, delay_seconds=8):
    """
    Continuously polls Server A until it's ready.
    Success is defined as receiving any status code other than 503 (Service Unavailable).
    """
    print("Waiting for Server A to become ready...")
    for i in range(max_retries):
        try:
            # We use the /healthz endpoint as it's lightweight and has no dependencies
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
    payload = {
        "to": "+15555550100",
        "text": "test message",
        "providers": ["ProviderA"],  # Explicitly use the provider from .env
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
    
    # Configure mock provider and reset its logs
    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)

    # Send the test SMS
    tracking_id = _send_request()
    time.sleep(20) # Wait for processing

    # Assert final status
    message = _get_message(tracking_id)
    assert message["status"] == "SENT"

    logs = requests.get("http://localhost:5005/logs", timeout=5).json()
    assert len(logs) == 1


def test_full_retry_and_recovery():
    """Tests the full retry mechanism in case of a transient failure."""
    wait_for_server_a_ready()

    # Configure mock for transient error
    requests.post("http://localhost:5005/config", json={"mode": "transient"}, timeout=5)
    tracking_id = _send_request()
    time.sleep(15) # Wait for first attempt

    # Assert awaiting retry status
    message = _get_message(tracking_id)
    assert message["status"] == "AWAITING_RETRY"
    assert message["error"] is not None

    # Reconfigure mock for success
    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)
    time.sleep(65) # Wait for Celery's exponential backoff retry

    # Assert final status
    message = _get_message(tracking_id)
    assert message["status"] == "SENT"