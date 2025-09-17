import importlib
import os
import sys
from types import SimpleNamespace


TEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if TEST_ROOT not in sys.path:
    sys.path.insert(0, TEST_ROOT)


def import_state_broadcaster():
    module_name = "core.state_broadcaster"
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def test_publish_full_state_skips_when_disabled(monkeypatch, caplog):
    module = import_state_broadcaster()

    monkeypatch.setattr(
        module,
        "settings",
        SimpleNamespace(CONFIG_STATE_SYNC_ENABLED=False),
    )

    called = False

    def fake_connection():
        nonlocal called
        called = True
        raise AssertionError("_get_connection should not be called when sync is disabled")

    monkeypatch.setattr(module, "_get_connection", fake_connection)

    with caplog.at_level("INFO"):
        module.publish_full_state.run()

    assert called is False
    assert "Configuration state sync disabled" in caplog.text
