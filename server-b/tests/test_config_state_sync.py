import importlib
import os
import sys

TEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if TEST_ROOT not in sys.path:
    sys.path.insert(0, TEST_ROOT)


def import_settings(monkeypatch, flag_value: str):
    module_name = "sms_gateway_project.settings"
    monkeypatch.setenv("CONFIG_STATE_SYNC_ENABLED", flag_value)
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def test_config_sync_enabled_default_true(monkeypatch):
    module_name = "sms_gateway_project.settings"
    monkeypatch.delenv("CONFIG_STATE_SYNC_ENABLED", raising=False)
    if module_name in sys.modules:
        del sys.modules[module_name]
    settings_module = importlib.import_module(module_name)
    try:
        assert settings_module.CONFIG_STATE_SYNC_ENABLED is True
        assert "publish-full-state" in settings_module.CELERY_BEAT_SCHEDULE
    finally:
        if module_name in sys.modules:
            del sys.modules[module_name]


def test_celery_schedule_respects_flag(monkeypatch):
    settings_module = import_settings(monkeypatch, "false")
    assert settings_module.CONFIG_STATE_SYNC_ENABLED is False
    assert "publish-full-state" not in settings_module.CELERY_BEAT_SCHEDULE

    settings_module = import_settings(monkeypatch, "true")
    assert settings_module.CONFIG_STATE_SYNC_ENABLED is True
    assert "publish-full-state" in settings_module.CELERY_BEAT_SCHEDULE
