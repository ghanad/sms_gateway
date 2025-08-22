import pytest
from app import models
from app.repositories import MessageRepository
from app.provider_registry import ProviderRegistry
from app.providers.base import BaseProvider, SendResult, SendStatus
from app.schemas import MessageIn
from app import rabbit_consumer


class TempFailProvider(BaseProvider):
    name = "temp"

    async def send_sms(self, to: str, text: str) -> SendResult:
        return SendResult(SendStatus.TEMP_FAILURE, {})


class SuccessProvider(BaseProvider):
    name = "succ"

    async def send_sms(self, to: str, text: str) -> SendResult:
        return SendResult(SendStatus.SUCCESS, {})


class PermFailProvider(BaseProvider):
    name = "perm"

    async def send_sms(self, to: str, text: str) -> SendResult:
        return SendResult(SendStatus.PERM_FAILURE, {})


@pytest.mark.asyncio
async def test_temp_failure_schedules_retry(session):
    repo = MessageRepository(session)
    reg = ProviderRegistry()
    reg.register("temp", TempFailProvider())
    message = MessageIn(
        tracking_id="t1",
        client_key="c",
        to="123",
        text="hi",
        providers=["temp"],
        policy="prioritized",
    )
    await repo.create_message(models.Message(tracking_id="t1", client_key="c", to="123", text="hi", ttl_seconds=60))
    result = await rabbit_consumer.process_message(message, repo, reg, "priority")
    assert result["status"] == "retry"


@pytest.mark.asyncio
async def test_success_updates_status(session):
    repo = MessageRepository(session)
    reg = ProviderRegistry()
    reg.register("succ", SuccessProvider())
    message = MessageIn(
        tracking_id="t2",
        client_key="c",
        to="123",
        text="hi",
        providers=["succ"],
        policy="prioritized",
    )
    await repo.create_message(models.Message(tracking_id="t2", client_key="c", to="123", text="hi", ttl_seconds=60))
    result = await rabbit_consumer.process_message(message, repo, reg, "priority")
    assert result["status"] == "sent"
    msg = await repo.get_message_with_events("t2")
    assert msg.status == models.MessageStatus.SENT


@pytest.mark.asyncio
async def test_perm_failure_switches_provider(session):
    repo = MessageRepository(session)
    reg = ProviderRegistry()
    reg.register("perm", PermFailProvider())
    reg.register("succ", SuccessProvider())
    message = MessageIn(
        tracking_id="t3",
        client_key="c",
        to="123",
        text="hi",
        providers=["perm", "succ"],
        policy="prioritized",
    )
    await repo.create_message(models.Message(tracking_id="t3", client_key="c", to="123", text="hi", ttl_seconds=60))
    result = await rabbit_consumer.process_message(message, repo, reg, "priority")
    assert result["status"] == "sent"
    msg = await repo.get_message_with_events("t3")
    assert msg.provider_final == "succ"
    fail_events = [e for e in msg.events if e.event_type == models.EventType.FAILED]
    assert any(e.provider == "perm" for e in fail_events)
