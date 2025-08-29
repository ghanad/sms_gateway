import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import aio_pika

from app.heartbeat import send_heartbeat, HEARTBEAT_EXCHANGE_NAME, HEARTBEAT_QUEUE_NAME
from app.config import Settings


class DummyChannelContext:
    def __init__(self, channel):
        self._channel = channel

    async def __aenter__(self):
        return self._channel

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_send_heartbeat_publishes_payload_and_closes_connection():
    fixed_time = datetime(2023, 1, 1, 12, 0, 0)
    mock_settings = Settings(app_name="test-service", heartbeat_interval_seconds=30)

    mock_channel = MagicMock()
    mock_channel.declare_exchange = AsyncMock()
    mock_channel.declare_queue = AsyncMock()
    mock_exchange = MagicMock()
    mock_channel.declare_exchange.return_value = mock_exchange
    mock_queue = MagicMock()
    mock_queue.bind = AsyncMock()
    mock_channel.declare_queue.return_value = mock_queue

    mock_connection = MagicMock()
    mock_connection.channel.return_value = DummyChannelContext(mock_channel)
    mock_connection.close = AsyncMock()

    with patch('app.heartbeat.aio_pika.connect_robust', return_value=mock_connection), \
         patch('app.heartbeat.settings', mock_settings), \
         patch('app.heartbeat.Message') as mock_message, \
         patch('app.heartbeat.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = fixed_time
        await send_heartbeat()

    mock_channel.declare_exchange.assert_called_once_with(
        HEARTBEAT_EXCHANGE_NAME, aio_pika.ExchangeType.DIRECT, durable=True
    )
    mock_channel.declare_queue.assert_called_once_with(HEARTBEAT_QUEUE_NAME, durable=True)
    mock_queue.bind.assert_called_once_with(mock_exchange, routing_key=HEARTBEAT_QUEUE_NAME)

    args, kwargs = mock_message.call_args
    body = args[0]
    payload = json.loads(body)
    assert payload == {
        "service": mock_settings.app_name,
        "timestamp": fixed_time.isoformat(),
    }
    assert kwargs["content_type"] == "application/json"
    assert kwargs["delivery_mode"] == aio_pika.DeliveryMode.PERSISTENT

    mock_exchange.publish.assert_called_once_with(
        mock_message.return_value, routing_key=HEARTBEAT_QUEUE_NAME
    )
    mock_connection.close.assert_awaited_once()
