import subprocess
import time
from uuid import uuid4

import pytest
import requests


@pytest.fixture(scope="module", autouse=True)
def compose_environment():
    """Create env files, start services, and seed required data."""
    env_setup = (
        "sed -n '1,/^# Server B/{/^#/!p}' .env.example > server-a/.env && "
        "{ sed -n '/^# Server B/,/^# Frontend/{/^#/!p}' .env.example; "
        "grep -E '^(CLIENT_CONFIG|PROVIDERS_CONFIG)=' .env.example; } > server-b/.env"
    )
    subprocess.run(["bash", "-c", env_setup], check=True)

    subprocess.run(["docker", "compose", "up", "-d", "--build", "--wait"], check=True)

    init_script = (
        "from django.contrib.auth.models import User;"
        "from user_management.models import Profile;"
        "from providers.models import SmsProvider;"
        "user,_=User.objects.get_or_create(username='testuser');"
        "Profile.objects.update_or_create(user=user, defaults={'api_key': 'api_key_for_e2e_tests'});"
        "SmsProvider.objects.get_or_create(name='ProviderA', defaults={'is_active': True, 'is_operational': True})"
    )
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "server-b",
            "python",
            "manage.py",
            "shell",
            "-c",
            init_script,
        ],
        check=True,
    )

    yield
    subprocess.run(["docker", "compose", "down", "-v"], check=True)


def _send_request(provider_name: str) -> requests.Response:
    payload = {
        "to": "+15555550100",
        "text": "test message",
        "providers": [provider_name],
        "ttl_seconds": 3600,
    }
    headers = {
        "API-Key": "api_key_for_e2e_tests",
        "Idempotency-Key": str(uuid4()),
    }
    return requests.post(
        "http://localhost:8001/api/v1/sms/send",
        json=payload,
        headers=headers,
        timeout=10,
    )


def test_real_time_sync_of_disabled_provider():
    provider_name = "ProviderA"

    enable_cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "server-b",
        "python",
        "manage.py",
        "shell",
        "-c",
        (
            "from providers.models import SmsProvider; "
            "p,_=SmsProvider.objects.get_or_create(name='ProviderA', defaults={'is_active': True, 'is_operational': True}); "
            "p.is_active=True; p.save()"
        ),
    ]
    subprocess.run(enable_cmd, check=True)
    time.sleep(70)
    ok_response = _send_request(provider_name)
    assert ok_response.status_code == 202

    disable_cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "server-b",
        "python",
        "manage.py",
        "shell",
        "-c",
        (
            "from providers.models import SmsProvider; "
            "p=SmsProvider.objects.get(name='ProviderA'); "
            "p.is_active=False; p.save()"
        ),
    ]
    subprocess.run(disable_cmd, check=True)
    time.sleep(70)
    fail_response = _send_request(provider_name)
    assert fail_response.status_code == 409
    body = fail_response.json()
    assert body.get("error_code") == "PROVIDER_DISABLED"


def test_startup_recovery_from_file_cache():
    provider_name = "ProviderA"

    check_cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "server-b",
        "python",
        "manage.py",
        "shell",
        "-c",
        (
            "from providers.models import SmsProvider; import sys; "
            "sys.exit(0 if not SmsProvider.objects.get(name='ProviderA').is_active else 1)"
        ),
    ]
    subprocess.run(check_cmd, check=True)

    subprocess.run(["docker", "compose", "restart", "server-a"], check=True)
    time.sleep(10)
    response = _send_request(provider_name)
    assert response.status_code == 409
    body = response.json()
    assert body.get("error_code") == "PROVIDER_DISABLED"

    enable_cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "server-b",
        "python",
        "manage.py",
        "shell",
        "-c",
        (
            "from providers.models import SmsProvider; "
            "p=SmsProvider.objects.get(name='ProviderA'); "
            "p.is_active=True; p.save()"
        ),
    ]
    subprocess.run(enable_cmd, check=True)

