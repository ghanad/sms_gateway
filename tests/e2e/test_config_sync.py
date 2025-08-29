import subprocess
import time
from uuid import uuid4

import pytest
import requests


@pytest.fixture(scope="module", autouse=True)
def compose_environment():
    """Create env files, start services, and ensure providers are loaded."""
    # Build per-service env files from the example configuration
    env_setup = (
        "sed -n '1,/^# Server B/{/^#/!p}' .env.example > server-a/.env && "
        "{ sed -n '/^# Server B/,/^# Frontend/{/^#/!p}' .env.example; "
        "grep -E '^(CLIENT_CONFIG|PROVIDERS_CONFIG)=' .env.example; } > server-b/.env"
    )
    subprocess.run(["bash", "-c", env_setup], check=True)

    subprocess.run(["docker", "compose", "up", "-d", "--build"], check=True)
    # Wait for server-a to become ready
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
        raise RuntimeError("Services did not become ready in time")

    # Ensure ProviderA exists in server-b (create it if necessary)
    start = time.time()
    init_cmd = [
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
            "SmsProvider.objects.get_or_create(" 
            "name='ProviderA', defaults={'is_active': True, 'is_operational': True})"
        ),
    ]
    while time.time() - start < 60:
        if subprocess.run(init_cmd).returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError("ProviderA was not initialized in time")

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
        "API-Key": "api_key_for_service_A",
        "Idempotency-Key": str(uuid4()),
    }
    return requests.post("http://localhost:8001/api/v1/sms/send", json=payload, headers=headers, timeout=10)


def test_real_time_sync_of_disabled_provider():
    provider_name = "ProviderA"
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
            f"from providers.models import SmsProvider; "
            f"p=SmsProvider.objects.get(name='{provider_name}'); "
            "p.is_active=False; p.save()"
        ),
    ]
    subprocess.run(disable_cmd, check=True)
    time.sleep(70)
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
            f"from providers.models import SmsProvider; "
            f"p=SmsProvider.objects.get(name='{provider_name}'); "
            "p.is_active=True; p.save()"
        ),
    ]
    subprocess.run(enable_cmd, check=True)


def test_startup_recovery_from_file_cache():
    provider_name = "ProviderA"
    subprocess.run(["docker", "compose", "restart", "server-a"], check=True)
    time.sleep(10)
    response = _send_request(provider_name)
    assert response.status_code == 409
    body = response.json()
    assert body.get("error_code") == "PROVIDER_DISABLED"
