import hashlib
import importlib
import json
import os
import sys
from types import SimpleNamespace

import django
from django.apps import apps


TEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if TEST_ROOT not in sys.path:
    sys.path.insert(0, TEST_ROOT)


def import_utils_module(monkeypatch):
    module_name = "user_management.utils"
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "sms_gateway_project.settings")
    if not apps.ready:
        django.setup()
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def import_tasks_module(monkeypatch):
    module_name = "user_management.tasks"
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "sms_gateway_project.settings")
    if not apps.ready:
        django.setup()
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def test_generate_server_a_config_data(monkeypatch):
    module = import_utils_module(monkeypatch)

    users = [
        SimpleNamespace(
            id=1,
            username="alice",
            is_active=True,
            profile=SimpleNamespace(api_key="alpha-key", daily_quota=5),
        ),
        SimpleNamespace(
            id=2,
            username="bob",
            is_active=False,
            profile=SimpleNamespace(api_key=None, daily_quota=10),
        ),
        SimpleNamespace(
            id=3,
            username="carol",
            is_active=True,
            profile=SimpleNamespace(api_key="carol-key", daily_quota=None),
        ),
    ]

    providers = [
        SimpleNamespace(
            name="PrimarySMS",
            is_active=True,
            is_operational=False,
            aliases=["primary"],
            slug="primary",
            note=None,
        ),
        SimpleNamespace(
            name="BackupSMS",
            is_active=True,
            aliases=None,
            slug="backup",
            note="Fallback route",
        ),
    ]

    class FakeUserQuerySet:
        def __init__(self, data):
            self._data = data

        def all(self):
            return list(self._data)

    class FakeUserManager:
        def __init__(self, data):
            self._data = data

        def select_related(self, related):
            assert related == "profile"
            return FakeUserQuerySet(self._data)

    class FakeProviderManager:
        def __init__(self, data):
            self._data = data

        def all(self):
            return list(self._data)

    monkeypatch.setattr(
        module,
        "User",
        SimpleNamespace(objects=FakeUserManager(users)),
    )
    monkeypatch.setattr(
        module,
        "SmsProvider",
        SimpleNamespace(objects=FakeProviderManager(providers)),
    )

    payload = module.generate_server_a_config_data()

    assert payload == {
        "users": {
            "alpha-key": {
                "user_id": 1,
                "username": "alice",
                "is_active": True,
                "daily_quota": 5,
            },
            "carol-key": {
                "user_id": 3,
                "username": "carol",
                "is_active": True,
                "daily_quota": 0,
            },
        },
        "providers": {
            "PrimarySMS": {
                "is_active": True,
                "is_operational": False,
                "aliases": ["primary"],
            },
            "BackupSMS": {
                "is_active": True,
                "is_operational": True,
                "aliases": ["backup"],
                "note": "Fallback route",
            },
        },
    }


def test_update_expected_config_fingerprint_metric(monkeypatch):
    module = import_tasks_module(monkeypatch)

    sample_payload = {"providers": {"Example": {"is_active": True}}, "users": {}}
    monkeypatch.setattr(
        module,
        "generate_server_a_config_data",
        lambda: sample_payload,
    )

    module.EXPECTED_CONFIG_FINGERPRINT.clear()
    module._last_fingerprint = "seed"
    module.EXPECTED_CONFIG_FINGERPRINT.labels(
        service=module.EXPECTED_CONFIG_FINGERPRINT_SERVICE_LABEL_VALUE,
        fingerprint=module._last_fingerprint,
    ).set(1)

    module.update_expected_config_fingerprint_metric.run()

    serialized = json.dumps(sample_payload, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    metric_families = module.EXPECTED_CONFIG_FINGERPRINT.collect()
    samples = [
        sample
        for family in metric_families
        for sample in family.samples
        if "fingerprint" in sample.labels
    ]

    assert module._last_fingerprint == expected_hash

    labels_to_values = {sample.labels["fingerprint"]: sample.value for sample in samples}
    assert labels_to_values["seed"] == 0.0
    assert labels_to_values[expected_hash] == 1.0

    for sample in samples:
        assert sample.labels["service"] == module.EXPECTED_CONFIG_FINGERPRINT_SERVICE_LABEL_VALUE

