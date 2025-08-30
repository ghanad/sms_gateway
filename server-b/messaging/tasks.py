import logging
import uuid
from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
from messaging.models import Message, MessageStatus
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
