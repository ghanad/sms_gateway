import asyncio

import pytest

from app import main


class _DummyConsumer:
    def __init__(self):
        self.called = 0
        self.coros = []

    def __call__(self):
        self.called += 1

        async def _runner():
            return None

        coro = _runner()
        self.coros.append(coro)
        return coro


@pytest.fixture
def reset_settings(monkeypatch):
    original = main.settings.CONFIG_STATE_SYNC_ENABLED
    yield
    monkeypatch.setattr(main.settings, "CONFIG_STATE_SYNC_ENABLED", original)


def test_config_sync_enabled_default_true(reset_settings):
    assert main.settings.CONFIG_STATE_SYNC_ENABLED is True


def test_start_consumer_disabled(monkeypatch, caplog, reset_settings):
    created_tasks = []

    def fake_create_task(coro, *args, **kwargs):
        created_tasks.append((coro, kwargs))
        return object()

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(main.settings, "CONFIG_STATE_SYNC_ENABLED", False)

    with caplog.at_level("INFO"):
        task = main.start_config_state_consumer_if_enabled()

    assert created_tasks == []
    assert task is None
    assert "Remote configuration sync disabled" in caplog.text


def test_start_consumer_enabled(monkeypatch, caplog, reset_settings):
    dummy_consumer = _DummyConsumer()
    created_tasks = []

    fake_task = object()

    def fake_create_task(coro, *args, **kwargs):
        created_tasks.append((coro, kwargs))
        return fake_task

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(main, "consume_config_state", dummy_consumer)
    monkeypatch.setattr(main.settings, "CONFIG_STATE_SYNC_ENABLED", True)

    with caplog.at_level("INFO"):
        task = main.start_config_state_consumer_if_enabled()

    assert dummy_consumer.called == 1
    assert len(created_tasks) == 1
    coro, kwargs = created_tasks[0]
    assert coro is dummy_consumer.coros[0]
    assert kwargs.get("name") == "config-state-consumer"
    assert task is fake_task
    assert "Configuration state consumer started" in caplog.text

    for coro, _ in created_tasks:
        coro.close()
