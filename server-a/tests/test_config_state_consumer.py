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


def test_start_consumer_disabled(monkeypatch, caplog, reset_settings):
    created_tasks = []

    def fake_create_task(coro):
        created_tasks.append(coro)
        return object()

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(main.settings, "CONFIG_STATE_SYNC_ENABLED", False)

    with caplog.at_level("INFO"):
        main.start_config_state_consumer_if_enabled()

    assert created_tasks == []
    assert "Remote configuration sync disabled" in caplog.text


def test_start_consumer_enabled(monkeypatch, caplog, reset_settings):
    dummy_consumer = _DummyConsumer()
    created_tasks = []

    def fake_create_task(coro):
        created_tasks.append(coro)
        return object()

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(main, "consume_config_state", dummy_consumer)
    monkeypatch.setattr(main.settings, "CONFIG_STATE_SYNC_ENABLED", True)

    with caplog.at_level("INFO"):
        main.start_config_state_consumer_if_enabled()

    assert dummy_consumer.called == 1
    assert len(created_tasks) == 1
    assert created_tasks[0] is dummy_consumer.coros[0]
    assert "Configuration state consumer started" in caplog.text

    for coro in created_tasks:
        coro.close()
