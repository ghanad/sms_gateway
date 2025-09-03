import os
import subprocess
import time
import json
import pytest
import requests
from requests.exceptions import HTTPError

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)

def wait_for_server_a_ready(max_retries=10, delay_seconds=8):
    """
    به طور مداوم به سرور A درخواست ارسال می‌کند تا زمانی که به جای 503، پاسخ موفقیت‌آمیز دریافت کند.
    این تابع تضمین می‌کند که همگام‌سازی اولیه از server-b انجام شده است.
    """
    print("Waiting for Server A to become ready and sync with Server B...")
    for i in range(max_retries):
        try:
            headers = {"API-Key": "api_key_for_service_A"}
            payload = {"to": "+15555550100", "text": "readiness check"}
            
            resp = requests.post(
                "http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=5
            )
            
            resp.raise_for_status()
            
            print("Server A is ready!")
            return
        except HTTPError as e:
            if e.response.status_code == 503:
                print(f"Attempt {i + 1}/{max_retries}: Server A is not ready yet (503). Retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)
            else:
                pytest.fail(f"Received an unexpected error while waiting for Server A: {e}")
        except requests.exceptions.RequestException as e:
            print(f"Attempt {i + 1}/{max_retries}: Could not connect to Server A. Retrying in {delay_seconds}s...")
            time.sleep(delay_seconds)
            
    pytest.fail("Server A did not become ready within the specified timeout.")


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
    cmd = [
        "docker", "compose", 
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
    wait_for_server_a_ready()  

    requests.post("http://localhost:5005/config", json={"mode": "success"}, timeout=5)
    tracking_id = _send_request()
    time.sleep(20)
    message = _get_message(tracking_id)
    assert message["status"] == "SENT_TO_PROVIDER"
    logs = requests.get("http://localhost:5005/logs", timeout=5).json()
    assert len(logs) == 1


def test_full_retry_and_recovery():
    wait_for_server_a_ready() 

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