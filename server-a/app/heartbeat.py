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
            exchange = await channel.declare_exchange(HEARTBEAT_EXCHANGE_NAME, aio_pika.ExchangeType.DIRECT, durable=True)
            
            queue = await channel.declare_queue(HEARTBEAT_QUEUE_NAME, durable=True)
            
            await queue.bind(exchange, routing_key=HEARTBEAT_QUEUE_NAME)

            heartbeat_payload = {
                "service": settings.app_name,
                "timestamp": datetime.utcnow().isoformat(),
            }

            message_body = json.dumps(heartbeat_payload).encode('utf-8')
            message = Message(
                message_body,
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT
            )

            await exchange.publish(
                message,
                routing_key=HEARTBEAT_QUEUE_NAME
            )
            logger.debug("Heartbeat sent successfully.", extra={"service": settings.app_name})
    except Exception as e:
        logger.error(f"Failed to send heartbeat to RabbitMQ: {e}")
    finally:
        if connection:
            await connection.close()

async def start_heartbeat_task():
    """
    Starts a background task to send heartbeats periodically.
    Includes retry logic with backoff.
    """
    logger.info(f"Starting heartbeat task with interval: {settings.heartbeat_interval_seconds} seconds.")
    while True:
        try:
            await send_heartbeat()
        except Exception as e:
            logger.error(f"Heartbeat task encountered an error: {e}. Retrying after backoff.")
            await asyncio.sleep(min(settings.heartbeat_interval_seconds * 2, 300))
        await asyncio.sleep(settings.heartbeat_interval_seconds)
