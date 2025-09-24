import asyncio
import hashlib
import json
import logging
from datetime import datetime
from typing import Optional

import aio_pika
from aio_pika import Message, DeliveryMode

from app import cache
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

HEARTBEAT_EXCHANGE_NAME = settings.heartbeat_exchange_name
HEARTBEAT_QUEUE_NAME = settings.heartbeat_queue_name


def compute_config_cache_fingerprint() -> Optional[str]:
    """Return the SHA256 fingerprint of the config cache file if available."""
    cache_path = cache.CONFIG_CACHE_PATH
    try:
        with cache_path.open("r", encoding="utf-8") as cache_file:
            payload = json.load(cache_file)
    except FileNotFoundError:
        logger.debug("Config cache file missing when computing fingerprint.")
        return None
    except json.JSONDecodeError as exc:
        logger.warning("Unable to parse config cache for fingerprint: %s", exc)
        return None
    except OSError as exc:
        logger.warning("Unable to read config cache for fingerprint: %s", exc)
        return None

    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _refresh_heartbeat_names() -> None:
    """Synchronize exported constants with the active settings instance."""
    global HEARTBEAT_EXCHANGE_NAME, HEARTBEAT_QUEUE_NAME
    HEARTBEAT_EXCHANGE_NAME = settings.heartbeat_exchange_name
    HEARTBEAT_QUEUE_NAME = settings.heartbeat_queue_name


async def send_heartbeat():
    """
    Sends a heartbeat message to a dedicated RabbitMQ queue.
    Includes service name, timestamp, and config fingerprints.
    """
    connection = None
    try:
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        async with connection.channel() as channel:
            _refresh_heartbeat_names()

            exchange = await channel.declare_exchange(
                HEARTBEAT_EXCHANGE_NAME,
                aio_pika.ExchangeType.DIRECT,
                durable=True,
            )

            queue = await channel.declare_queue(HEARTBEAT_QUEUE_NAME, durable=True)

            await queue.bind(exchange, routing_key=HEARTBEAT_QUEUE_NAME)

            heartbeat_payload = {
                "service": settings.app_name,
                "timestamp": datetime.utcnow().isoformat(),
                "config_cache_fingerprint": compute_config_cache_fingerprint(),
            }

            message_body = json.dumps(heartbeat_payload).encode('utf-8')
            message = Message(
                message_body,
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT
            )
            
            await exchange.publish(message, routing_key=HEARTBEAT_QUEUE_NAME)
            
            logger.debug("Heartbeat sent successfully.", extra={"service": settings.app_name})
    except Exception as e:
        logger.error(f"Failed to send heartbeat to RabbitMQ: {e}")
    finally:
        if connection:
            await connection.close()

async def start_heartbeat_task():
    """Run the periodic heartbeat sender until cancelled."""

    async def _cancellable_sleep(delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise

    logger.info(
        "Starting heartbeat task with interval: %s seconds.",
        settings.heartbeat_interval_seconds,
    )

    try:
        while True:
            try:
                await send_heartbeat()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(
                    "Heartbeat task encountered an error: %s. Retrying after backoff.",
                    e,
                )
                await _cancellable_sleep(min(settings.heartbeat_interval_seconds * 2, 300))
            await _cancellable_sleep(settings.heartbeat_interval_seconds)
    except asyncio.CancelledError:
        logger.info("Heartbeat task cancellation requested; exiting background loop.")
        raise
