import subprocess
import time
import pytest
import requests
from requests.exceptions import RequestException

def wait_for_server_a_ready(max_retries=10, delay_seconds=8):
    """
    Continuously polls Server A until it's ready and has received its configuration from Server B.
    Success is defined as receiving any status code other than 503 (Service Unavailable).
    """
    print("Waiting for Server A to become ready and sync with Server B...")
    for i in range(max_retries):
        try:
            headers = {"API-Key": "api_key_for_service_A"}
            payload = {"to": "+15555550100", "text": "readiness check"}

            response = requests.post(
                "http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=5
            )

            if response.status_code != 503:
                print(f"Server A is ready! (Received status code: {response.status_code})")
                response.raise_for_status()
                return
            else:
                print(f"Attempt {i + 1}/{max_retries}: Server A is not ready yet (503). Retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)

        except RequestException as e:
            print(f"Attempt {i + 1}/{max_retries}: Could not connect to Server A ({e}). Retrying in {delay_seconds}s...")
            time.sleep(delay_seconds)

    pytest.fail("Server A did not become ready (did not stop returning 503) within the specified timeout.")


def clear_redis_keys(pattern):
    """
    Deletes keys from the Redis container matching a specific pattern.
    """
    command_to_run = f"redis-cli --scan --pattern '{pattern}' | xargs redis-cli DEL"
    
    cmd = [
        "docker", "compose",
        "exec",
        "-T",
        "redis",
        "sh",
        "-c", command_to_run
    ]
    
    subprocess.run(cmd, capture_output=True, text=True, check=False) # Use check=False to avoid errors if no keys are found
    print(f"Cleared Redis keys with pattern: {pattern}")

def setup_test_user(api_key, daily_quota, is_staff=False):
    """
    Creates or updates a user in server-b's database with a specific API key and quota.
    This ensures the state is correct before tests run.
    """
    print(f"Setting up test user: api_key={api_key}, daily_quota={daily_quota}")
    
    command_to_run = (
        "from django.contrib.auth.models import User; "
        "from user_management.models import Profile; "
        f"user, created = User.objects.update_or_create(username='{api_key}', defaults={{'is_staff': {is_staff}}}); "
        "profile, p_created = Profile.objects.update_or_create(user=user, defaults={'api_key': user.username, 'daily_quota': {daily_quota}});"
        "print(f'User {{user.username}} configured.')"
    )

    cmd = [
        "docker", "compose", "exec", "-T", "server-b",
        "python", "manage.py", "shell",
        "--command", command_to_run
    ]
    
    subprocess.run(cmd, capture_output=True, text=True, check=True)