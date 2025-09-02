import json
import os
import subprocess
import time

import pytest
import requests

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)


COMPOSE_CMD = ["docker", "compose"]


@pytest.fixture(scope="module", autouse=True)
def compose_environment():
    subprocess.run(COMPOSE_CMD + ["up", "-d", "--build"], check=True)

    start = time.time()
    while time.time() - start < 60:
        try:
            resp = requests.get("http://localhost:8001/readyz", timeout=5)
            if resp.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        subprocess.run(COMPOSE_CMD + ["down", "-v"], check=False)
        raise RuntimeError("Services did not become ready in time")
    yield
    subprocess.run(COMPOSE_CMD + ["down", "-v"], check=True)



def _send_request():
    payload = {
        "to": "+15555550100",
        "text": "test message",
    }
    headers = {"API-Key": "api_key_for_service_A"}
    resp = requests.post(
        "http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=10
    )
    resp.raise_for_status()
    return resp.json()["tracking_id"]


def _get_message(tracking_id: str) -> dict:
    cmd = COMPOSE_CMD + [
        "exec",
        "-T",
        "server-b",
        "python",
        "manage.py",
        "shell",
        "-c",
        (
            "import json; from messaging.models import Message; "
            f"m=Message.objects.get(tracking_id='{tracking_id}'); "
            "print(json.dumps({'status': m.status, 'error': m.error_message}))"
        ),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout.strip())


def test_successful_end_to_end_flow():
    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)
    tracking_id = _send_request()
    time.sleep(20)
    message = _get_message(tracking_id)
    assert message["status"] == "SENT_TO_PROVIDER"
    logs = requests.get("http://localhost:5005/logs", timeout=5).json()
    assert len(logs) == 1


def test_full_retry_and_recovery():
    requests.post("http://localhost:5005/config", json={"mode": "transient"}, timeout=5)
    tracking_id = _send_request()
    time.sleep(15)
    message = _get_message(tracking_id)
    assert message["status"] == "AWAITING_RETRY"
    assert message["error"]
    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)
    time.sleep(65)
    message = _get_message(tracking_id)
    assert message["status"] == "SENT_TO_PROVIDER"
