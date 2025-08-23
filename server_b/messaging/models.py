import uuid
from django.db import models
from providers.models import Provider


class Message(models.Model):
    class Status(models.TextChoices):
        RECEIVED = 'received'
        QUEUED = 'queued'
        SENT = 'sent'
        ACCEPTED = 'accepted'
        DELIVERED = 'delivered'
        FAILED = 'failed'
        REJECTED = 'rejected'
        EXPIRED = 'expired'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tracking_id = models.CharField(max_length=64, unique=True)
    customer_id = models.CharField(max_length=64)
    provider = models.ForeignKey(Provider, on_delete=models.PROTECT)
    provider_message_id = models.JSONField(blank=True, null=True)
    policy_snapshot = models.JSONField(blank=True, null=True)
    payload_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    attempts = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('idempotency_key', 'provider')

    def __str__(self):
        return self.tracking_id


class MessageEvent(models.Model):
    message = models.ForeignKey(Message, related_name='events', on_delete=models.CASCADE)
    event_type = models.CharField(max_length=50)
    raw = models.JSONField(blank=True, null=True)
    at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.message.tracking_id}:{self.event_type}"
