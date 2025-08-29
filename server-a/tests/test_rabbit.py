import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

import aio_pika

from app.rabbit import publish_sms_message, RABBITMQ_EXCHANGE_NAME, RABBITMQ_QUEUE_NAME


class DummyChannelContext:
    def __init__(self, channel):
        self._channel = channel

    async def __aenter__(self):
        return self._channel

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_publish_sms_message_publishes_and_closes_connection():
    tracking_id = uuid4()
    fixed_time = datetime(2023, 1, 1, 12, 0, 0)

    mock_channel = MagicMock()
    mock_channel.declare_exchange = AsyncMock()
    mock_channel.declare_queue = AsyncMock()
    mock_channel.publish = AsyncMock()
    mock_queue = MagicMock()
    mock_queue.bind = AsyncMock()
    mock_channel.declare_queue.return_value = mock_queue

    mock_connection = MagicMock()
    mock_connection.channel.return_value = DummyChannelContext(mock_channel)
    mock_connection.close = AsyncMock()

    with patch('app.rabbit.get_rabbitmq_connection', new=AsyncMock(return_value=mock_connection)), \
         patch('app.rabbit.Message') as mock_message, \
         patch('app.rabbit.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = fixed_time

        await publish_sms_message(
            user_id=1,
            client_key="client1",
            to="+1234567890",
            text="Hello",
            ttl_seconds=60,
            providers_original=["ProviderA"],
            providers_effective=["ProviderA"],
            tracking_id=tracking_id,
        )

    mock_channel.declare_exchange.assert_called_once_with(
        RABBITMQ_EXCHANGE_NAME, aio_pika.ExchangeType.DIRECT, durable=True
    )
    mock_channel.declare_queue.assert_called_once_with(RABBITMQ_QUEUE_NAME, durable=True)
    mock_queue.bind.assert_called_once_with(RABBITMQ_EXCHANGE_NAME, routing_key=RABBITMQ_QUEUE_NAME)

    args, kwargs = mock_message.call_args
    body = args[0]
    payload = json.loads(body)
    assert payload == {
        "tracking_id": str(tracking_id),
        "user_id": 1,
        "client_key": "client1",
        "to": "+1234567890",
        "text": "Hello",
        "ttl_seconds": 60,
        "providers_original": ["ProviderA"],
        "providers_effective": ["ProviderA"],
        "created_at": fixed_time.isoformat(),
    }
    assert kwargs["content_type"] == "application/json"
    assert kwargs["delivery_mode"] == aio_pika.DeliveryMode.PERSISTENT

    mock_channel.publish.assert_called_once_with(
        mock_message.return_value,
        exchange=RABBITMQ_EXCHANGE_NAME,
        routing_key=RABBITMQ_QUEUE_NAME,
    )
    mock_connection.close.assert_awaited_once()
