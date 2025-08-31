import json
import logging
import uuid

import pika
from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from messaging.models import (
    Message,
    MessageStatus,
    MessageAttemptLog,
    AttemptStatus,
)
from providers.models import SmsProvider
from providers.adapters import get_provider_adapter

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def process_outbound_sms(self, envelope: dict):
    """Process a single outbound SMS message envelope."""
    tracking_id = envelope.get("tracking_id")
    if not tracking_id:
        logger.warning("Envelope missing tracking_id: %s", envelope)
        return

    if Message.objects.filter(tracking_id=tracking_id).exists():
        logger.warning("Message with tracking_id %s already processed", tracking_id)
        return

    try:
        user = User.objects.get(pk=envelope.get("user_id"))
    except User.DoesNotExist:
        logger.error("User %s not found", envelope.get("user_id"))
        return

    message = Message.objects.create(
        user=user,
        tracking_id=uuid.UUID(tracking_id),
        recipient=envelope.get("to"),
        text=envelope.get("text"),
        status=MessageStatus.PROCESSING,
    )

    provider_name = None
    providers_list = envelope.get("providers_effective") or []
    if providers_list:
        provider_name = providers_list[0]

    if not provider_name:
        message.status = MessageStatus.FAILED
        message.error_message = "No provider specified"
        message.save(update_fields=["status", "error_message"])
        logger.error("No provider specified for message %s", message.tracking_id)
        return

    provider = SmsProvider.objects.filter(slug__iexact=provider_name).first()
    if not provider:
        provider = SmsProvider.objects.filter(name__iexact=provider_name).first()

    if not provider:
        message.status = MessageStatus.FAILED
        message.error_message = f"Provider {provider_name} not found"
        message.save(update_fields=["status", "error_message"])
        logger.error("Provider %s not found for message %s", provider_name, message.tracking_id)
        return

    message.provider = provider
    message.send_attempts = message.send_attempts + 1
    message.save(update_fields=["provider", "send_attempts"])

    adapter = get_provider_adapter(provider)
    result = adapter.send_sms(message.recipient, message.text)

    if result.get("error"):
        message.status = MessageStatus.FAILED
        message.error_message = result.get("error")
    else:
        message.status = MessageStatus.SENT_TO_PROVIDER
        message.provider_message_id = result.get("message_id")
        message.provider_response = result
        message.sent_at = timezone.now()
    message.save()


@shared_task
def dispatch_pending_messages(batch_size: int = 50):
    """Periodically dispatch pending messages for sending."""
    message_ids = []
    with transaction.atomic():
        pending = (
            Message.objects.select_for_update(skip_locked=True)
            .filter(status=MessageStatus.PENDING)[:batch_size]
        )
        ids = [m.id for m in pending]
        if ids:
            Message.objects.filter(id__in=ids).update(status=MessageStatus.PROCESSING)
            message_ids = ids

    for mid in message_ids:
        send_sms_with_failover.delay(mid)


@shared_task(bind=True, max_retries=5)
def send_sms_with_failover(self, message_id: int):
    """Send an SMS using available providers with retry and failover."""
    message = Message.objects.get(pk=message_id)
    message.status = MessageStatus.PROCESSING
    message.send_attempts = message.send_attempts + 1
    message.save(update_fields=["status", "send_attempts"])

    providers = list(
        SmsProvider.objects.filter(is_active=True).order_by("-priority")
    )

    last_error_message = "No active providers available"
    for provider in providers:
        adapter = get_provider_adapter(provider)
        try:
            result = adapter.send_sms(message.recipient, message.text)
            status = (
                AttemptStatus.FAILURE
                if result.get("error")
                else AttemptStatus.SUCCESS
            )
        except Exception as exc:  # pragma: no cover - defensive
            result = {"error": str(exc)}
            status = AttemptStatus.FAILURE

        MessageAttemptLog.objects.create(
            message=message,
            provider=provider,
            status=status,
            provider_response=result,
        )

        if status == AttemptStatus.FAILURE:
            last_error_message = result.get("error")
            continue

        message.status = MessageStatus.SENT_TO_PROVIDER
        message.provider = provider
        message.provider_message_id = result.get("message_id")
        message.provider_response = result
        message.sent_at = timezone.now()
        message.error_message = ""
        message.save()
        return

    # All providers failed
    message.error_message = last_error_message
    if self.request.retries < self.max_retries:
        message.status = MessageStatus.AWAITING_RETRY
        message.save(update_fields=["status", "error_message"])
        delay = 60 * (2 ** self.request.retries)
        raise self.retry(countdown=delay)

    message.status = MessageStatus.FAILED
    message.save(update_fields=["status", "error_message"])
    publish_to_dlq(message)


def publish_to_dlq(message: Message) -> None:
    """Publish message details to a Dead Letter Queue for inspection."""
    try:
        credentials = pika.PlainCredentials(
            settings.RABBITMQ_USER, settings.RABBITMQ_PASS
        )
        params = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST, credentials=credentials
        )
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue="sms_outbound_dlq", durable=True)
        body = json.dumps(
            {
                "id": message.id,
                "tracking_id": str(message.tracking_id),
                "error": message.error_message,
            }
        )
        channel.basic_publish(
            exchange="", routing_key="sms_outbound_dlq", body=body
        )
        connection.close()
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to publish message %s to DLQ", message.id)
