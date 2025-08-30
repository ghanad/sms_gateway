import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest
import requests


@pytest.fixture(scope="module", autouse=True)
def compose_environment():
    """Create env files, start services, and seed required data."""
    root = Path(__file__).resolve().parents[2]
    env_example = root / ".env.example"
    server_a_env = root / "server-a" / ".env"
    server_b_env = root / "server-b" / ".env"

    server_a_lines = []
    server_b_lines = []
    section = "server_a"
    with env_example.open() as fh:
        for line in fh:
            if line.startswith("# Server B"):
                section = "server_b"
                continue
            if line.startswith("# Frontend"):
                section = None
                continue
            if line.startswith("#") or not line.strip():
                continue
            if section == "server_a":
                server_a_lines.append(line)
            elif section == "server_b":
                server_b_lines.append(line)

    # Append shared client/provider config to server-b env
    for line in server_a_lines:
        if line.startswith("CLIENT_CONFIG") or line.startswith("PROVIDERS_CONFIG"):
            server_b_lines.append(line)

    server_a_env.write_text("".join(server_a_lines))
    server_b_env.write_text("".join(server_b_lines))

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
def test_real_time_sync_and_recovery_flow():
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

    subprocess.run(["docker", "compose", "restart", "server-a"], check=True)
    time.sleep(10)
    fail_response = _send_request(provider_name)
    assert fail_response.status_code == 409
    body = fail_response.json()
    assert body.get("error_code") == "PROVIDER_DISABLED"

    cleanup_cmd = [
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
    subprocess.run(cleanup_cmd, check=True)

