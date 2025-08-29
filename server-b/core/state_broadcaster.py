import json
import threading
import time
from datetime import datetime

import pika
from django.conf import settings
from django.contrib.auth.models import User

from providers.models import SmsProvider


def _get_connection():
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    return pika.BlockingConnection(
        pika.ConnectionParameters(host=settings.RABBITMQ_HOST, credentials=credentials)
    )


def _publish_full_state():
    connection = _get_connection()
    channel = connection.channel()
    channel.exchange_declare(
        exchange=settings.CONFIG_STATE_EXCHANGE,
        exchange_type="fanout",
        durable=True,
    )

    users_qs = User.objects.select_related("profile").all()
    users = [
        {
            "user_id": user.id,
            "username": user.username,
            "api_key": str(user.profile.api_key),
            "daily_quota": user.profile.daily_quota,
            "is_active": user.is_active,
        }
        for user in users_qs
    ]

    providers = []
    for provider in SmsProvider.objects.all():
        providers.append(
            {
                "name": provider.name,
                "slug": provider.slug,
                "is_active": provider.is_active,
                "is_operational": getattr(provider, "is_operational", True),
                "aliases": getattr(provider, "aliases", []),
            }
        )

    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "data": {"users": users, "providers": providers},
    }

    channel.basic_publish(
        exchange=settings.CONFIG_STATE_EXCHANGE,
        routing_key="",
        body=json.dumps(payload),
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
        ),
    )
    connection.close()


def start_periodic_broadcast(interval: int = 60) -> None:
    def _worker() -> None:
        while True:
            try:
                _publish_full_state()
            except Exception:  # pragma: no cover - log and continue
                import logging
                logging.exception("Failed to publish configuration state")
            time.sleep(interval)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
