import asyncio
import logging
import json
from datetime import datetime

import aio_pika
from aio_pika import Message, DeliveryMode

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

HEARTBEAT_EXCHANGE_NAME = "sms_gateway_heartbeat_exchange"
HEARTBEAT_QUEUE_NAME = "sms_heartbeat_queue"

async def send_heartbeat():
    """
    Sends a heartbeat message to a dedicated RabbitMQ queue.
    Includes service name, timestamp, and config fingerprints.
    """
    connection = None
    try:
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        async with connection.channel() as channel:
            await channel.declare_exchange(HEARTBEAT_EXCHANGE_NAME, aio_pika.ExchangeType.DIRECT, durable=True)
            queue = await channel.declare_queue(HEARTBEAT_QUEUE_NAME, durable=True)
            await queue.bind(HEARTBEAT_EXCHANGE_NAME, routing_key=HEARTBEAT_QUEUE_NAME)

            heartbeat_payload = {
                "service": settings.SERVICE_NAME,
                "timestamp": datetime.utcnow().isoformat(),
                "config_fingerprint": {
                    "clients": settings.client_config_fingerprint,
                    "providers": settings.providers_config_fingerprint,
                },
            }

            message_body = json.dumps(heartbeat_payload).encode('utf-8')
            message = Message(
                message_body,
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT
            )

            await channel.publish(
                message,
                exchange=HEARTBEAT_EXCHANGE_NAME,
                routing_key=HEARTBEAT_QUEUE_NAME
            )
            logger.debug("Heartbeat sent successfully.", extra={"service": settings.SERVICE_NAME})
    except Exception as e:
        logger.error(f"Failed to send heartbeat to RabbitMQ: {e}", extra={"service": settings.SERVICE_NAME})
    finally:
        if connection:
            await connection.close()

async def start_heartbeat_task():
    """
    Starts a background task to send heartbeats periodically.
    Includes retry logic with backoff.
    """
    logger.info(f"Starting heartbeat task with interval: {settings.HEARTBEAT_INTERVAL_SECONDS} seconds.")
    while True:
        try:
            await send_heartbeat()
        except Exception as e:
            logger.error(f"Heartbeat task encountered an error: {e}. Retrying after backoff.")
            # Implement a simple backoff strategy
            await asyncio.sleep(min(settings.HEARTBEAT_INTERVAL_SECONDS * 2, 300)) # Max 5 min backoff
        await asyncio.sleep(settings.HEARTBEAT_INTERVAL_SECONDS)