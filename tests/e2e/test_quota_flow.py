# tests/e2e/test_quota_flow.py

import os
import pytest
import requests
from uuid import uuid4

# Import helper functions from the shared helpers file
from helpers import clear_redis_keys, wait_for_server_a_ready

# This line ensures that these tests only run when the RUN_E2E environment variable is set to 1
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)

# Test user settings
# These values should match what is defined in your .env file for CLIENT_CONFIG
API_KEY = "api_key_for_service_A"
# For faster tests, this value should be set to a small number (e.g., 5)
# in your server-a/.env file during the CI run.
DAILY_QUOTA = 5

def _send_quota_request(api_key=API_KEY):
    """Sends a simple request to test the quota."""
    payload = {"to": "+15555550100", "text": "quota test message"}
    headers = {"API-Key": api_key, "Idempotency-Key": str(uuid4())}
    return requests.post(
        "http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=10
    )


def test_daily_quota_enforcement():
    """
    Tests the full daily quota mechanism by:
    1. Waiting for the system to be fully ready.
    2. Consuming the entire quota.
    3. Verifying that the next request is correctly rejected.
    """
    # Step 1: Wait for the system to be fully initialized and synced
    wait_for_server_a_ready()

    # Step 2: Clear any previous Redis state to ensure the test is isolated
    clear_redis_keys(f"quota:{API_KEY}:*")
    
    # Step 3: Send requests up to the daily quota limit
    print(f"Sending {DAILY_QUOTA} requests to consume the daily quota...")
    for i in range(DAILY_QUOTA):
        resp = _send_quota_request()
        assert resp.status_code == 202, f"Request {i+1} failed with status {resp.status_code}: {resp.text}"

    print("Successfully consumed the daily quota.")

    # Step 4: Send one additional request that should be rejected
    print("Sending one more request, which should be rejected...")
    final_resp = _send_quota_request()

    # Step 5: Verify the 429 Too Many Requests error
    assert final_resp.status_code == 429, f"Expected status 429 but got {final_resp.status_code}"
    
    error_data = final_resp.json()
    assert error_data["error_code"] == "TOO_MANY_REQUESTS"
    assert error_data["message"] == "Daily SMS quota exceeded."
    
    print("Quota enforcement test passed successfully!")