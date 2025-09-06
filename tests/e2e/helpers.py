# tests/e2e/helpers.py

import subprocess
import time
import pytest
import requests
from requests.exceptions import RequestException

def setup_test_user(api_key, daily_quota, is_staff=False):
    """
    Creates or updates a user in server-b's database and configures their profile.
    This version uses a more robust method to avoid database race conditions.
    """
    print(f"Setting up test user: api_key={api_key}, daily_quota={daily_quota}")

    # This more explicit command is stabler than update_or_create in a shell context.
    command_to_run = (
        "from django.contrib.auth.models import User; "
        "from user_management.models import Profile; "
        f"user, created = User.objects.get_or_create(username='{api_key}', defaults={{'is_staff': {is_staff}}}); "
        "if created: user.set_password('password'); " # Set a default password for new users
        f"user.profile.api_key = '{api_key}'; "
        f"user.profile.daily_quota = {daily_quota}; "
        "user.profile.save(); "
        "user.save();"
        "print(f'User {{user.username}} configured.')"
    )

    cmd = [
        "docker", "compose", "exec", "-T", "server-b",
        "python", "manage.py", "shell",
        "--no-startup",
        "--command", command_to_run
    ]

    subprocess.run(cmd, capture_output=True, text=True, check=True)

def wait_for_server_a_ready(api_key, max_retries=15, delay_seconds=8):
    """
    Continuously polls Server A until it's ready and has received its configuration
    from Server B (both providers and users). Success is defined as receiving a 2xx
    status code.
    """
    print("Waiting for Server A to become ready and sync with Server B...")
    for i in range(max_retries):
        try:
            headers = {"API-Key": api_key}
            payload = {"to": "+15555550100", "text": "readiness check"}

            response = requests.post(
                "http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=5
            )

            if response.status_code not in [503, 401]:
                response.raise_for_status()
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
    command_to_run = f"redis-cli --scan --pattern '{pattern}' | xargs -r redis-cli DEL"
    
    cmd = [
        "docker", "compose", "exec", "-T", "redis",
        "sh", "-c", command_to_run
    ]
    
    subprocess.run(cmd, capture_output=True, text=True, check=False)
    print(f"Cleared Redis keys with pattern: {pattern}")