import json
import logging
from datetime import datetime

import pika
from celery import shared_task
from django.conf import settings


def _get_connection():
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            credentials=credentials,
            virtual_host=getattr(settings, "RABBITMQ_VHOST", "/"),
        )
    )


logger = logging.getLogger(__name__)


@shared_task
def publish_full_state():
    if not getattr(settings, "CONFIG_STATE_SYNC_ENABLED", False):
        logger.info("Configuration state sync disabled; skipping broadcast.")
        return

    from django.contrib.auth.models import User  # Imported lazily for testability
    from providers.models import SmsProvider  # Imported lazily for testability

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
