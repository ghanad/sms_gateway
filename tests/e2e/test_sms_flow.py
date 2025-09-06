# tests/e2e/test_sms_flow.py

import os
import subprocess
import time
import json
import pytest
import requests
from helpers import wait_for_server_a_ready, setup_test_user

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)

API_KEY = "e2e_flow_test_user"
USER_QUOTA = 1000

def _send_request():
    """Sends a standard request to send an SMS to Server A."""
    payload = {"to": "+15555550100", "text": "test message"}
    headers = {"API-Key": API_KEY}
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
        "docker", "compose", "exec", "-T", "server-b",
        "python", "manage.py", "shell", "--no-startup", "--command", command_to_run,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output_lines = result.stdout.strip().splitlines()
    json_output = output_lines[-1] if output_lines else "{}"
    return json.loads(json_output)

def test_successful_end_to_end_flow():
    """Tests a complete successful end-to-end scenario."""
    setup_test_user(api_key=API_KEY, daily_quota=USER_QUOTA)
    wait_for_server_a_ready(api_key=API_KEY)
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
    setup_test_user(api_key=API_KEY, daily_quota=USER_QUOTA)
    wait_for_server_a_ready(api_key=API_KEY)
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