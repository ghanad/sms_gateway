import importlib
import os
import sys
from types import SimpleNamespace

import django
from django.apps import apps

import pytest
from prometheus_client import REGISTRY


TEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if TEST_ROOT not in sys.path:
    sys.path.insert(0, TEST_ROOT)


METRIC_NAMES = [
    "SMS_MESSAGES_PROCESSED_TOTAL",
    "SMS_MESSAGES_PENDING_GAUGE",
    "SMS_MESSAGE_FINAL_STATUS_TOTAL",
    "SMS_PROCESSING_DURATION_SECONDS",
    "SMS_PROVIDER_SEND_ATTEMPTS_TOTAL",
    "SMS_PROVIDER_SEND_LATENCY_SECONDS",
    "SMS_PROVIDER_FAILOVERS_TOTAL",
    "SMS_PROVIDER_BALANCE_GAUGE",
    "SMS_CELERY_TASK_RETRIES_TOTAL",
    "SMS_DLQ_MESSAGES_TOTAL",
]


def set_task_globals(task, monkeypatch, **overrides):
    wrapped = getattr(task, "__wrapped__", task)
    func = getattr(wrapped, "__func__", wrapped)
    globals_dict = func.__globals__
    for name, value in overrides.items():
        monkeypatch.setitem(globals_dict, name, value)


def import_provider_tasks(monkeypatch):
    module_name = "providers.tasks"
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "sms_gateway_project.settings")
    if not apps.ready:
        django.setup()

    if module_name in sys.modules:
        existing_module = sys.modules[module_name]
        for metric_name in METRIC_NAMES:
            metric = getattr(existing_module, metric_name, None)
            if metric is None:
                continue
            try:
                REGISTRY.unregister(metric)
            except KeyError:
                pass
        del sys.modules[module_name]

    return importlib.import_module(module_name)


def test_update_provider_balance_metrics_sets_values(monkeypatch):
    module = import_provider_tasks(monkeypatch)

    module.SMS_PROVIDER_BALANCE_GAUGE.clear()

    providers = [
        SimpleNamespace(slug="alpha", name="AlphaSMS", is_active=True),
        SimpleNamespace(slug="beta", name="BetaSMS", is_active=True),
    ]

    def fake_filter(**kwargs):
        if kwargs.get("is_active") is False:
            return []
        return providers

    def fake_adapter(provider):
        if provider.slug == "alpha":
            return SimpleNamespace(get_balance=lambda: {"balance": "100.5"})
        return SimpleNamespace(get_balance=lambda: {"credit": 42})

    set_task_globals(
        module.update_provider_balance_metrics,
        monkeypatch,
        SmsProvider=SimpleNamespace(objects=SimpleNamespace(filter=fake_filter)),
        get_provider_adapter=fake_adapter,
    )

    module.update_provider_balance_metrics.run()

    alpha_value = (
        module.SMS_PROVIDER_BALANCE_GAUGE.labels(provider="alpha")._value.get()
    )
    beta_value = (
        module.SMS_PROVIDER_BALANCE_GAUGE.labels(provider="beta")._value.get()
    )

    assert alpha_value == pytest.approx(100.5)
    assert beta_value == pytest.approx(42.0)


def test_update_provider_balance_metrics_handles_errors(monkeypatch):
    module = import_provider_tasks(monkeypatch)

    module.SMS_PROVIDER_BALANCE_GAUGE.clear()
    module.SMS_PROVIDER_BALANCE_GAUGE.labels(provider="alpha").set(75.0)

    providers = [
        SimpleNamespace(slug="alpha", name="AlphaSMS", is_active=True),
        SimpleNamespace(slug="gamma", name="GammaSMS", is_active=True),
    ]

    def fake_adapter(provider):
        if provider.slug == "alpha":
            raise RuntimeError("adapter failure")
        return SimpleNamespace(get_balance=lambda: {"message": "n/a"})

    set_task_globals(
        module.update_provider_balance_metrics,
        monkeypatch,
        SmsProvider=SimpleNamespace(objects=SimpleNamespace(filter=lambda **kwargs: providers)),
        get_provider_adapter=fake_adapter,
    )

    module.update_provider_balance_metrics.run()

    alpha_metric = (
        module.SMS_PROVIDER_BALANCE_GAUGE.labels(provider="alpha")._value.get()
    )
    assert alpha_metric == pytest.approx(75.0)
    assert set(module.SMS_PROVIDER_BALANCE_GAUGE._metrics.keys()) == {("alpha",)}
