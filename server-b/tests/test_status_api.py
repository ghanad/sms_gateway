import pytest
from app.repositories import MessageRepository
from app import models


@pytest.mark.asyncio
async def test_status_api_returns_events_ordered(client, session):
    repo = MessageRepository(session)
    await repo.create_message(
        models.Message(tracking_id="s1", client_key="c", to="123", text="hi", ttl_seconds=60)
    )
    await repo.add_event("s1", models.EventType.PROCESSING, "p1")
    await repo.add_event("s1", models.EventType.SENT, "p1")
    resp = await client.get("/messages/s1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tracking_id"] == "s1"
    assert [e["event_type"] for e in data["events"]] == ["PROCESSING", "SENT"]
