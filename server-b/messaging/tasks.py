import json
import logging
import time
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
from sms_gateway_project.metrics import (
    SMS_CELERY_TASK_RETRIES_TOTAL,
    SMS_DLQ_MESSAGES_TOTAL,
    SMS_MESSAGE_FINAL_STATUS_TOTAL,
    SMS_MESSAGES_PENDING_GAUGE,
    SMS_MESSAGES_PROCESSED_TOTAL,
    SMS_PROCESSING_DURATION_SECONDS,
    SMS_PROVIDER_SEND_ATTEMPTS_TOTAL,
    SMS_PROVIDER_SEND_LATENCY_SECONDS,
)

logger = logging.getLogger(__name__)


def _provider_label(provider: SmsProvider) -> str:
    slug = getattr(provider, "slug", None)
    if slug:
        return str(slug)
    name = getattr(provider, "name", None)
    return str(name) if name else "unknown"


def _observe_provider_attempt(provider: SmsProvider, result: dict, elapsed: float) -> None:
    provider_name = _provider_label(provider)
    outcome = "success"
    if result.get("status") != "success":
        outcome_type = result.get("type")
        if outcome_type == "transient":
            outcome = "transient_failure"
        else:
            outcome = "permanent_failure"
    SMS_PROVIDER_SEND_ATTEMPTS_TOTAL.labels(provider=provider_name, outcome=outcome).inc()
    SMS_PROVIDER_SEND_LATENCY_SECONDS.labels(provider=provider_name).observe(max(elapsed, 0.0))


def _record_final_metrics(message: Message, finalized_at=None) -> None:
    final_status = getattr(message, "status", None)
    if final_status:
        SMS_MESSAGE_FINAL_STATUS_TOTAL.labels(status=final_status).inc()

    if finalized_at is None:
        finalized_at = timezone.now()

    created_at = getattr(message, "created_at", None)
    if created_at is None:
        return

    try:
        duration = (finalized_at - created_at).total_seconds()
    except Exception:  # pragma: no cover - defensive guard
        return

    if duration >= 0:
        SMS_PROCESSING_DURATION_SECONDS.observe(duration)

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
        initial_envelope=envelope,
    )

    SMS_MESSAGES_PROCESSED_TOTAL.inc()

    provider_name = None
    providers_list = envelope.get("providers_effective") or []
    if providers_list:
        provider_name = providers_list[0]

    if not provider_name:
        finalized_at = timezone.now()
        message.status = MessageStatus.FAILED
        message.error_message = "No provider specified"
        message.save(update_fields=["status", "error_message"])
        _record_final_metrics(message, finalized_at=finalized_at)
        logger.error("No provider specified for message %s", message.tracking_id)
        return

    provider = SmsProvider.objects.filter(slug__iexact=provider_name).first()
    if not provider:
        provider = SmsProvider.objects.filter(name__iexact=provider_name).first()

    if not provider:
        finalized_at = timezone.now()
        message.status = MessageStatus.FAILED
        message.error_message = f"Provider {provider_name} not found"
        message.save(update_fields=["status", "error_message"])
        _record_final_metrics(message, finalized_at=finalized_at)
        logger.error("Provider %s not found for message %s", provider_name, message.tracking_id)
        return

    message.provider = provider
    message.send_attempts = message.send_attempts + 1
    message.save(update_fields=["provider", "send_attempts"])

    adapter = get_provider_adapter(provider)
    start_time = time.perf_counter()
    result = adapter.send_sms(message.recipient, message.text)
    elapsed = time.perf_counter() - start_time
    _observe_provider_attempt(provider, result, elapsed)

    if result.get("status") == "success":
        finalized_at = timezone.now()
        message.status = MessageStatus.SENT_TO_PROVIDER
        message.provider_message_id = result.get("message_id")
        message.provider_response = result.get("raw_response")
        message.sent_at = finalized_at
        message.error_message = ""
    else:
        finalized_at = timezone.now()
        message.status = MessageStatus.FAILED
        message.error_message = result.get("reason")
        message.provider_response = result.get("raw_response")
    message.save()
    _record_final_metrics(message, finalized_at=finalized_at)


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

    pending_count = Message.objects.filter(status=MessageStatus.PENDING).count()
    SMS_MESSAGES_PENDING_GAUGE.set(pending_count)

    for mid in message_ids:
        send_sms_with_failover.delay(mid)


@shared_task(bind=True, max_retries=5)
def send_sms_with_failover(self, message_id: int):
    """Send an SMS using available providers with retry and intelligent failover."""
    message = Message.objects.get(pk=message_id)
    envelope = message.initial_envelope or {}

    # Determine provider list
    provider_names = envelope.get("providers_effective") or []
    providers: list[SmsProvider] = []
    if provider_names:
        for name in provider_names:
            provider = SmsProvider.objects.filter(slug__iexact=name).first()
            if not provider:
                provider = SmsProvider.objects.filter(name__iexact=name).first()
            if provider:
                providers.append(provider)
    else:
        providers = list(
            SmsProvider.objects.filter(is_active=True).order_by("-priority")
        )

    message.send_attempts = message.send_attempts + 1
    message.save(update_fields=["send_attempts"])

    sent_successfully = False
    all_failures_were_permanent = True
    error_logs: list[str] = []

    for provider in providers:
        adapter = get_provider_adapter(provider)
        start_time = time.perf_counter()
        try:
            result = adapter.send_sms(message.recipient, message.text)
        except Exception as exc:  # pragma: no cover - defensive
            result = {
                "status": "failure",
                "type": "transient",
                "reason": str(exc),
                "raw_response": None,
            }
        elapsed = time.perf_counter() - start_time
        _observe_provider_attempt(provider, result, elapsed)

        status = (
            AttemptStatus.SUCCESS
            if result.get("status") == "success"
            else AttemptStatus.FAILURE
        )

        MessageAttemptLog.objects.create(
            message=message,
            provider=provider,
            status=status,
            provider_response=result.get("raw_response"),
        )

        if result.get("status") == "success":
            sent_successfully = True
            finalized_at = timezone.now()
            message.status = MessageStatus.SENT_TO_PROVIDER
            message.provider = provider
            message.provider_message_id = result.get("message_id")
            message.provider_response = result.get("raw_response")
            message.sent_at = finalized_at
            message.error_message = ""
            message.save()
            _record_final_metrics(message, finalized_at=finalized_at)
            break

        # Failure case
        reason = result.get("reason") or "Unknown error"
        error_logs.append(reason)
        if result.get("type") == "transient":
            all_failures_were_permanent = False
            continue

        # Permanent failure - fail fast
        finalized_at = timezone.now()
        message.status = MessageStatus.FAILED
        message.error_message = reason
        message.save(update_fields=["status", "error_message"])
        _record_final_metrics(message, finalized_at=finalized_at)
        publish_to_dlq(message)
        return

    if sent_successfully:
        return

    if all_failures_were_permanent:
        finalized_at = timezone.now()
        message.status = MessageStatus.FAILED
        message.error_message = "; ".join(error_logs)
        message.save(update_fields=["status", "error_message"])
        _record_final_metrics(message, finalized_at=finalized_at)
        publish_to_dlq(message)
        return

    # At least one transient failure
    message.status = MessageStatus.AWAITING_RETRY
    message.error_message = error_logs[-1] if error_logs else "Transient failure"
    message.save(update_fields=["status", "error_message"])

    if self.request.retries < self.max_retries:
        delay = 60 * (2 ** self.request.retries)
        SMS_CELERY_TASK_RETRIES_TOTAL.inc()
        raise self.retry(countdown=delay)

    # Retry limit exceeded
    finalized_at = timezone.now()
    message.status = MessageStatus.FAILED
    message.error_message = "; ".join(error_logs)
    message.save(update_fields=["status", "error_message"])
    _record_final_metrics(message, finalized_at=finalized_at)
    publish_to_dlq(message)


def publish_to_dlq(message: Message) -> None:
    """Publish message details to a Dead Letter Queue for inspection."""
    try:
        credentials = pika.PlainCredentials(
            settings.RABBITMQ_USER, settings.RABBITMQ_PASS
        )
        params = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            credentials=credentials,
            virtual_host=getattr(settings, "RABBITMQ_VHOST", "/"),
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
        SMS_DLQ_MESSAGES_TOTAL.inc()
        connection.close()
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to publish message %s to DLQ", message.id)
