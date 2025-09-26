import base64

import pytest
from fastapi.testclient import TestClient

from app.main import app, settings


def _encode_basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
    return f"Basic {token}"


def _set_metrics_credentials(username: str, password: str):
    settings.metrics_username = username
    settings.metrics_password = password


@pytest.fixture(autouse=True)
def restore_metrics_credentials():
    original_username = settings.metrics_username
    original_password = settings.metrics_password
    try:
        yield
    finally:
        settings.metrics_username = original_username
        settings.metrics_password = original_password


def test_metrics_endpoint_requires_authentication():
    _set_metrics_credentials("metrics-user", "metrics-pass")
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Basic"


def test_metrics_endpoint_rejects_invalid_credentials():
    _set_metrics_credentials("metrics-user", "metrics-pass")
    client = TestClient(app)
    headers = {"Authorization": _encode_basic_auth("wrong", "credentials")}

    response = client.get("/metrics", headers=headers)

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Basic"


def test_metrics_endpoint_returns_metrics_for_valid_credentials():
    _set_metrics_credentials("metrics-user", "metrics-pass")
    client = TestClient(app)
    headers = {"Authorization": _encode_basic_auth("metrics-user", "metrics-pass")}

    response = client.get("/metrics", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/plain")
    assert "sms_send_requests_total" in response.text
