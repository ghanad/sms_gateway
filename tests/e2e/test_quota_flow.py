# tests/e2e/test_quota_flow.py

import os
import time
import pytest
import requests
from uuid import uuid4

# Import the helper file created in the previous step
from helpers import clear_redis_keys

# Run these tests only in the E2E environment
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)

# Initial test user settings
# These values must match what is defined for CLIENT_CONFIG in your .env file
API_KEY = "api_key_for_service_A"
DAILY_QUOTA = 100  # Assume the quota for this user is 100

def _send_quota_request(api_key=API_KEY):
    """Sends a simple request to test the quota."""
    payload = {"to": "+15555550100", "text": "quota test message"}
    headers = {"API-Key": api_key, "Idempotency-Key": str(uuid4())}
    return requests.post(
        "http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=10
    )


def test_daily_quota_enforcement():
    """
    Comprehensive test of the daily quota mechanism:
    1. First, it consumes the quota.
    2. Then, it verifies that additional requests are rejected with a 429 error.
    """
    # Step 1: Clear previous state to ensure test isolation
    # Redis key pattern is based on QUOTA_PREFIX setting in server-a/.env
    clear_redis_keys(f"quota:{API_KEY}:*")
    
    # Step 2: Send requests up to the daily quota limit
    print(f"Sending {DAILY_QUOTA} requests to consume the daily quota...")
    for i in range(DAILY_QUOTA):
        resp = _send_quota_request()
        # Verify that each request is successfully accepted
        assert resp.status_code == 202, f"Request {i+1} failed with status {resp.status_code}: {resp.text}"

    print("Successfully consumed the daily quota.")

    # Step 3: Send one more request that should be rejected
    print("Sending one more request, which should be rejected...")
    final_resp = _send_quota_request()

    # Step 4: Verify 429 error
    assert final_resp.status_code == 429, f"Expected status 429 but got {final_resp.status_code}"
    
    error_data = final_resp.json()
    assert error_data["error_code"] == "TOO_MANY_REQUESTS"
    assert error_data["message"] == "Daily SMS quota exceeded."
    
    print("Quota enforcement test passed successfully!")