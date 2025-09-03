import os
import subprocess
import time
from uuid import uuid4

import pytest
import requests

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="E2E tests require docker compose environment",
)


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
