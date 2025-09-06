# tests/e2e/test_quota_flow.py

import os
import pytest
import requests
from uuid import uuid4
from helpers import clear_redis_keys, wait_for_server_a_ready, setup_test_user

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)

API_KEY = "e2e_quota_test_user"
DAILY_QUOTA = 5

def _send_quota_request(api_key=API_KEY):
    payload = {"to": "+15555550100", "text": "quota test message"}
    headers = {"API-Key": api_key, "Idempotency-Key": str(uuid4())}
    return requests.post(
        "http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=10
    )

def test_daily_quota_enforcement():
    # Step 1: Create the test user with the specific quota.
    setup_test_user(api_key=API_KEY, daily_quota=DAILY_QUOTA)

    # Step 2: Wait for the system to be fully synced.
    wait_for_server_a_ready(api_key=API_KEY)

    # Step 3: Clear any previous Redis state.
    clear_redis_keys(f"quota:{API_KEY}:*")
    
    # Step 4: Consume the quota.
    print(f"Sending {DAILY_QUOTA} requests to consume the daily quota...")
    for i in range(DAILY_QUOTA):
        resp = _send_quota_request()
        assert resp.status_code == 202, f"Request {i+1} failed with status {resp.status_code}: {resp.text}"

    print("Successfully consumed the daily quota.")

    # Step 5: Send one more request, which should be rejected.
    print("Sending one more request, which should be rejected...")
    final_resp = _send_quota_request()

    # Step 6: Verify the 429 error.
    assert final_resp.status_code == 429, f"Expected status 429 but got {final_resp.status_code}"
    
    error_data = final_resp.json()
    assert error_data["error_code"] == "TOO_MANY_REQUESTS"
    assert error_data["message"] == "Daily SMS quota exceeded."
    
    print("Quota enforcement test passed successfully!")