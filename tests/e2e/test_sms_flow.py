# tests/e2e/test_sms_flow.py

import os
import subprocess
import time
import json
import pytest
import requests
from requests.exceptions import RequestException

# Import all necessary helper functions from the shared helpers file
from helpers import wait_for_server_a_ready, setup_test_user

# This line ensures that these tests only run when the RUN_E2E environment variable is set to 1
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)

# Use a dedicated API key for this test suite to ensure isolation
API_KEY = "e2e_flow_test_user"
# A high quota so that these tests are not affected by quota limits
USER_QUOTA = 1000

def _send_request():
    """Sends a standard request to send an SMS to Server A."""
    payload = {
        "to": "+15555550100",
        "text": "test message",
    }
    headers = {"API-Key": API_KEY}
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
        "docker", "compose",
        "exec",
        "-T",
        "server-b",
        "python",
        "manage.py",
        "shell",
        "--no-startup",
        "--command", command_to_run,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    output_lines = result.stdout.strip().splitlines()
    json_output = output_lines[-1] if output_lines else "{}"

    return json.loads(json_output)


def test_successful_end_to_end_flow():
    """Tests a complete successful end-to-end scenario."""
    # Step 1: Programmatically create the user in server-b to ensure a known state
    setup_test_user(api_key=API_KEY, daily_quota=USER_QUOTA)

    # Step 2: Wait for server-a to sync with the newly created user data
    wait_for_server_a_ready()

    # Step 3: Wait for any in-flight readiness messages to clear and reset the mock provider
    time.sleep(15)
    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)
    
    # Step 4: The system is now in a clean state. Send the actual test SMS.
    tracking_id = _send_request()
    
    # Step 5: Wait for the message to be processed.
    time.sleep(20)
    
    # Step 6: Check the final status of the message in the database.
    message = _get_message(tracking_id)
    assert message["status"] == "SENT"
    
    # Step 7: Check the mock provider's logs.
    logs = requests.get("http://localhost:5005/logs", timeout=5).json()
    assert len(logs) == 1


def test_full_retry_and_recovery():
    """Tests the full retry mechanism in case of a transient failure."""
    # Step 1: Programmatically create the user in server-b to ensure a known state
    setup_test_user(api_key=API_KEY, daily_quota=USER_QUOTA)
    
    # Step 2: Wait for server-a to sync with the newly created user data
    wait_for_server_a_ready()

    # Step 3: Wait for readiness messages to clear and set the mock provider to fail
    time.sleep(15)
    requests.post("http://localhost:5005/config", json={"mode": "transient"}, timeout=5)
    
    # Step 4: Send the SMS
    tracking_id = _send_request()
    
    # Step 5: Wait for the first failed attempt to be registered.
    time.sleep(15)
    
    # Step 6: Check that the message status has changed to AWAITING_RETRY.
    message = _get_message(tracking_id)
    assert message["status"] == "AWAITING_RETRY"
    assert message["error"] is not None
    
    # Step 7: Reconfigure the mock provider for a successful response.
    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)
    
    # Step 8: Wait for Celery to perform the retry.
    time.sleep(65)
    
    # Step 9: Check the final status of the message after a successful retry.
    message = _get_message(tracking_id)
    assert message["status"] == "SENT"