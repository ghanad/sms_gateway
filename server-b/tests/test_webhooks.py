import pytest
from app.repositories import MessageRepository
from app import models


@pytest.mark.asyncio
async def test_webhook_marks_delivered(client, session):
    repo = MessageRepository(session)
    await repo.create_message(
        models.Message(tracking_id="w1", client_key="c", to="123", text="hi", ttl_seconds=60, status=models.MessageStatus.SENT)
    )
    resp = await client.post("/webhook/provider_a", json={"tracking_id": "w1"})
    assert resp.status_code == 200
    msg = await repo.get_message_with_events("w1")
    assert msg.status == models.MessageStatus.DELIVERED
    assert any(e.event_type == models.EventType.DELIVERED for e in msg.events)
