import asyncio
import json
import logging

import aio_pika

from app.cache import apply_state, save_state_to_file
from app.config import get_settings

logger = logging.getLogger(__name__)


async def consume_config_state() -> None:
    """Background task that listens for full configuration state broadcasts."""

    settings = get_settings()
    connection = await aio_pika.connect_robust(
        settings.RABBITMQ_URL
    )

    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            "config_state_exchange", aio_pika.ExchangeType.FANOUT, durable=True
        )
        queue = await channel.declare_queue(exclusive=True)
        await queue.bind(exchange)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        payload = json.loads(message.body.decode())
                        apply_state(payload)
                        save_state_to_file(payload)
                        logger.info("Configuration state updated from broadcast.")
                    except Exception:
                        logger.exception("Failed to process configuration state message")


__all__ = ["consume_config_state"]
