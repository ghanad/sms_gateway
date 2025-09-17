import importlib
import os
import sys
from types import SimpleNamespace

import django
from django.apps import apps


TEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if TEST_ROOT not in sys.path:
    sys.path.insert(0, TEST_ROOT)


def import_messaging_tasks(monkeypatch):
    module_name = "messaging.tasks"
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "sms_gateway_project.settings")
    if not apps.ready:
        django.setup()
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def test_publish_to_dlq_uses_configured_virtual_host(monkeypatch):
    module = import_messaging_tasks(monkeypatch)

    captured = {}

    def fake_plain_credentials(user, password):
        captured["credentials"] = (user, password)
        return SimpleNamespace(user=user, password=password)

    def fake_connection_parameters(*args, **kwargs):
        captured["connection_kwargs"] = kwargs
        return SimpleNamespace(**kwargs)

    class DummyChannel:
        def queue_declare(self, **kwargs):
            captured["queue_declared"] = kwargs

        def basic_publish(self, **kwargs):
            captured["published"] = kwargs

    class DummyConnection:
        def channel(self):
            return DummyChannel()

        def close(self):
            captured["closed"] = True

    def fake_blocking_connection(params):
        captured["params_obj"] = params
        return DummyConnection()

    monkeypatch.setattr(
        module,
        "pika",
        SimpleNamespace(
            PlainCredentials=fake_plain_credentials,
            ConnectionParameters=fake_connection_parameters,
            BlockingConnection=fake_blocking_connection,
        ),
    )

    monkeypatch.setattr(
        module,
        "settings",
        SimpleNamespace(
            RABBITMQ_USER="guest",
            RABBITMQ_PASS="guestpass",
            RABBITMQ_HOST="rabbitmq",
            RABBITMQ_VHOST="sms_pipeline_vhost",
        ),
    )

    message = SimpleNamespace(id=1, tracking_id="abc", error_message="oops")

    module.publish_to_dlq(message)

    assert captured["credentials"] == ("guest", "guestpass")
    assert captured["connection_kwargs"]["host"] == "rabbitmq"
    assert captured["connection_kwargs"]["virtual_host"] == "sms_pipeline_vhost"
    assert "queue_declared" in captured
    assert "published" in captured
    assert captured.get("closed") is True
