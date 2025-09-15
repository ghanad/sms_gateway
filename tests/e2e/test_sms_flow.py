import os
import subprocess
import time
import json
import pytest
import requests
from requests.exceptions import RequestException
from uuid import uuid4

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)

@pytest.fixture(scope="module", autouse=True)
def reset_server_a_cache():
    """
    Runs once before tests in this file. Deletes the server-a config cache file.
    This forces server-a to bootstrap its config from its .env file,
    making these tests independent of server-b's state and any previous tests.
    """
    print("\\n[Fixture] Deleting server-a cache to ensure fresh bootstrap from .env...")
    # The cache file is located at /app/app/state/config_cache.json inside the container
    delete_cache_cmd = [
        "docker", "compose", "exec", "-T", "server-a",
        "rm", "-f", "/app/app/state/config_cache.json"
    ]
    subprocess.run(delete_cache_cmd, check=True)
    
    # Also restart server-a to ensure it reloads config from scratch
    subprocess.run(["docker", "compose", "restart", "server-a"], check=True)
    
    # Give it a moment to start up cleanly
    time.sleep(10)
    print("[Fixture] Server-a state reset.")
    yield


def wait_for_server_a_ready(max_retries=10, delay_seconds=5):
    """Waits for server-a to be responsive by checking its health endpoint."""
    print("Waiting for Server A to become ready...")
    for i in range(max_retries):
        try:
            if requests.get("http://localhost:8001/healthz", timeout=5).status_code == 200:
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
        "providers": ["ProviderA"],
    }
    headers = {"API-Key": "api_key_for_service_A", "Idempotency-Key": str(uuid4())}
    resp = requests.post(
        "http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=10
    )
    resp.raise_for_status()
    return resp.json()["tracking_id"]


def _get_message(tracking_id: str) -> dict:
    """Retrieves message information from the server-b database."""
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


def poll_for_message_status(tracking_id: str, expected_status: str, timeout_seconds: int = 30, interval_seconds: int = 2) -> dict:
    """Actively polls the database for a specific message status."""
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        message_data = _get_message(tracking_id)
        if message_data.get('status') == expected_status:
            return message_data
        time.sleep(interval_seconds)
    pytest.fail(f"Timeout: Message {tracking_id} did not reach status '{expected_status}'.")


def test_successful_end_to_end_flow():
    """Tests a complete successful end-to-end scenario."""
    wait_for_server_a_ready()
    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)

    tracking_id = _send_request()
    message = poll_for_message_status(tracking_id, "SENT", timeout_seconds=25)
    assert message["status"] == "SENT"

    logs = requests.get("http://localhost:5005/logs", timeout=5).json()
    assert len(logs) == 1


def test_full_retry_and_recovery():
    """Tests the full retry mechanism in case of a transient failure."""
    wait_for_server_a_ready()
    requests.post("http://localhost:5005/config", json={"mode": "transient"}, timeout=5)
    
    tracking_id = _send_request()
    message = poll_for_message_status(tracking_id, "AWAITING_RETRY", timeout_seconds=20)
    assert message["status"] == "AWAITING_RETRY"
    assert message["error"] is not None

    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)
    final_message = poll_for_message_status(tracking_id, "SENT", timeout_seconds=70)
    assert final_message["status"] == "SENT"