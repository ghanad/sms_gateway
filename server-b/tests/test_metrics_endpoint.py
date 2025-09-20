import importlib
import os
import sys

import django
from django.apps import apps
from django.conf import settings
from django.test import Client


TEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if TEST_ROOT not in sys.path:
    sys.path.insert(0, TEST_ROOT)


def test_metrics_endpoint_serves_multiprocess_data(monkeypatch, tmp_path):
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "sms_gateway_project.settings")
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))

    if not apps.ready:
        django.setup()

    allowed_hosts = list(getattr(settings, "ALLOWED_HOSTS", []))
    if "testserver" not in allowed_hosts:
        allowed_hosts.append("testserver")
        settings.ALLOWED_HOSTS = allowed_hosts

    for module_name_prefix in [
        name for name in list(sys.modules) if name.startswith("prometheus_client")
    ]:
        del sys.modules[module_name_prefix]

    from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY

    module_name = "sms_gateway_project.metrics"
    existing_module = sys.modules.get(module_name)
    if existing_module is not None:
        try:
            REGISTRY.unregister(existing_module.SMS_MESSAGES_PROCESSED_TOTAL)
        except KeyError:
            pass
        del sys.modules[module_name]

    metrics_module = importlib.import_module(module_name)
    metrics_module.SMS_MESSAGES_PROCESSED_TOTAL.inc()

    client = Client()
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response["Content-Type"] == CONTENT_TYPE_LATEST
    assert b"sms_messages_processed_total" in response.content

    try:
        REGISTRY.unregister(metrics_module.SMS_MESSAGES_PROCESSED_TOTAL)
    except KeyError:
        pass
