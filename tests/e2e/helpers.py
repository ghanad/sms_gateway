# tests/e2e/helpers.py

import subprocess
import time
import pytest
import requests
from requests.exceptions import RequestException

def setup_test_user(api_key, daily_quota, is_staff=False):
    """
    Creates or updates a user in server-b's database and configures their profile.
    This function relies on the application's post_save signal to create the initial
    profile, and then it updates that profile with the specific test data.
    """
    print(f"Setting up test user: api_key={api_key}, daily_quota={daily_quota}")

    # This command creates the user, lets the signal create the profile,
    # and then updates the profile's attributes. This avoids race conditions.
    command_to_run = (
        "from django.contrib.auth.models import User; "
        f"user, created = User.objects.update_or_create(username='{api_key}', defaults={{'is_staff': {is_staff}}}); "
        f"user.profile.api_key = '{api_key}'; "
        f"user.profile.daily_quota = {daily_quota}; "
        "user.profile.save(); "
        "print(f'User {{user.username}} configured.')"
    )

    cmd = [
        "docker", "compose", "exec", "-T", "server-b",
        "python", "manage.py", "shell",
        "--no-startup",
        "--command", command_to_run
    ]

    # `check=True` ensures that if this command fails, the entire test will stop immediately.
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def wait_for_server_a_ready(api_key, max_retries=15, delay_seconds=8):
    """
    Continuously polls Server A until it's ready and has received its configuration
    from Server B (both providers and users). Success is defined as receiving a 2xx
    status code, indicating the user is known and providers are available.
    """
    print("Waiting for Server A to become ready and sync with Server B...")
    for i in range(max_retries):
        try:
            headers = {"API-Key": api_key}
            payload = {"to": "+15555550100", "text": "readiness check"}

            response = requests.post(
                "http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=5
            )

            # A 503 means providers are not synced yet.
            # A 401 means providers might be synced, but the user is not.
            # We wait until we get a successful (2xx) response.
            if response.status_code not in [503, 401]:
                response.raise_for_status() # Check for other errors like 500 or 422
                print(f"Server A is ready! (Received status code: {response.status_code})")
                return
            else:
                print(f"Attempt {i + 1}/{max_retries}: Server A not ready ({response.status_code}). Retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)

        except RequestException as e:
            print(f"Attempt {i + 1}/{max_retries}: Could not connect to Server A ({e}). Retrying in {delay_seconds}s...")
            time.sleep(delay_seconds)

    pytest.fail("Server A did not become ready within the specified timeout.")


def clear_redis_keys(pattern):
    """
    Deletes keys from the Redis container matching a specific pattern.
    """
    # The `-r` flag for xargs prevents it from running DEL if no keys are found, avoiding an error.
    command_to_run = f"redis-cli --scan --pattern '{pattern}' | xargs -r redis-cli DEL"
    
    cmd = [
        "docker", "compose",
        "exec",
        "-T",
        "redis",
        "sh",
        "-c", command_to_run
    ]
    
    subprocess.run(cmd, capture_output=True, text=True, check=False)
    print(f"Cleared Redis keys with pattern: {pattern}")