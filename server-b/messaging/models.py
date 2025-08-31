# server-b/messaging/models.py
from django.db import models
from django.contrib.auth.models import User
from providers.models import SmsProvider
import uuid

class MessageStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PROCESSING = 'PROCESSING', 'Processing'
    AWAITING_RETRY = 'AWAITING_RETRY', 'Awaiting Retry'
    SENT_TO_PROVIDER = 'SENT', 'Sent to Provider'
    DELIVERED = 'DELIVERED', 'Delivered'
    FAILED = 'FAILED', 'Failed'
    REJECTED = 'REJECTED', 'Rejected internally'

class Message(models.Model):
    # --- Core information from RabbitMQ ---
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='messages',
        help_text="The user who initiated the SMS request"
    )
    tracking_id = models.UUIDField(
        unique=True,
        db_index=True,
        help_text="The unique tracking ID from Server A for end-to-end tracing"
    )
    recipient = models.CharField(max_length=20, help_text="The phone number of the recipient")
    text = models.TextField(help_text="The content of the SMS")

    # --- Status and sending management ---
    status = models.CharField(
        max_length=20,
        choices=MessageStatus.choices,
        default=MessageStatus.PENDING,
        db_index=True
    )
    provider = models.ForeignKey(
        SmsProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
        help_text="The provider used for sending this message"
    )
    send_attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of failed attempts to send"
    )

    # --- Information from the provider's response ---
    provider_message_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Message ID from the provider's system (for webhooks)"
    )
    provider_response = models.JSONField(
        null=True,
        blank=True,
        help_text="The full API response from the provider"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="The last error message if the sending failed"
    )

    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the message was received from the queue")
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp of the last status update")
    sent_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of successful sending to the provider")

    def __str__(self):
        return f"To: {self.recipient} via {self.provider.name if self.provider else 'N/A'} [{self.status}]"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]
