# server-a/app/rabbit.py

import logging
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

import aio_pika
from aio_pika import Message, DeliveryMode

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

RABBITMQ_EXCHANGE_NAME = settings.outbound_sms_exchange
RABBITMQ_QUEUE_NAME = settings.outbound_sms_queue
RABBITMQ_ROUTING_KEY = settings.outbound_sms_routing_key

async def get_rabbitmq_connection() -> aio_pika.Connection:
    """Establishes and returns a RabbitMQ connection."""
    try:
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        logger.info("Successfully connected to RabbitMQ.")
        return connection
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")
        raise

async def publish_sms_message(
    user_id: int,
    client_key: str,
    to: str,
    text: str,
    ttl_seconds: int,
    providers_original: Optional[List[str]],
    providers_effective: List[str],
    tracking_id: uuid.UUID
) -> None:
    """
    Publishes an SMS message envelope to RabbitMQ.
    """
    connection = None
    try:
        connection = await get_rabbitmq_connection()
        async with connection.channel() as channel:
            exchange = await channel.declare_exchange(
                RABBITMQ_EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
            )

            queue = await channel.declare_queue(RABBITMQ_QUEUE_NAME, durable=True)

            await queue.bind(RABBITMQ_EXCHANGE_NAME, routing_key=RABBITMQ_ROUTING_KEY)
            
            envelope = {
                "tracking_id": str(tracking_id),
                "user_id": user_id,
                "client_key": client_key,
                "to": to,
                "text": text,
                "ttl_seconds": ttl_seconds,
                "providers_original": providers_original,
                "providers_effective": providers_effective,
                "created_at": datetime.utcnow().isoformat(),
            }

            message_body = json.dumps(envelope).encode('utf-8')
            message = Message(
                message_body,
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT
            )

            await exchange.publish(message, routing_key=RABBITMQ_ROUTING_KEY)
            logger.info(
                "SMS message published to RabbitMQ.",
                extra={"tracking_id": str(tracking_id), "client_api_key": client_key, "to": to}
            )
    except Exception as e:
        logger.error(
            f"Failed to publish SMS message to RabbitMQ: {e}",
            extra={"tracking_id": str(tracking_id), "client_api_key": client_key, "to": to}
        )
        raise
    finally:
        if connection:
            await connection.close()
