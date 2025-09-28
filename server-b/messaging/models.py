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
    STATUS_PILL_CLASSES = {
        MessageStatus.PENDING: "pill--pending",
        MessageStatus.PROCESSING: "pill--processing",
        MessageStatus.AWAITING_RETRY: "pill--retry",
        MessageStatus.SENT_TO_PROVIDER: "pill--sent",
        MessageStatus.DELIVERED: "pill--delivered",
        MessageStatus.FAILED: "pill--off",
        MessageStatus.REJECTED: "pill--off",
    }

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

    # --- Original envelope ---
    initial_envelope = models.JSONField(
        null=True,
        blank=True,
        help_text="The full envelope received from the queue",
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
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
        help_text="The cost of the message as reported by the provider."
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
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the provider confirmed final delivery",
    )

    def __str__(self):
        return f"To: {self.recipient} via {self.provider.name if self.provider else 'N/A'} [{self.status}]"

    @property
    def status_pill_class(self) -> str:
        """Return the CSS class used to render the status pill in templates."""

        return self.STATUS_PILL_CLASSES.get(self.status, "pill--on")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]


class AttemptStatus(models.TextChoices):
    """Status of a single provider attempt."""

    SUCCESS = "SUCCESS", "Success"
    FAILURE = "FAILURE", "Failure"


class MessageAttemptLog(models.Model):
    """Audit log for individual provider sending attempts."""

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="attempt_logs"
    )
    provider = models.ForeignKey(
        SmsProvider,
        on_delete=models.PROTECT,
        related_name="attempt_logs",
        help_text="The provider used for this attempt",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=AttemptStatus.choices)
    provider_response = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self) -> str:  # pragma: no cover - for admin/debug only
        return f"{self.provider.name} - {self.status}"

    def get_magfa_status_summary(self):
        """Return a human-readable summary of the Magfa provider response.

        The Magfa API returns a nested JSON structure. This helper method
        interprets the structure and maps provider status codes to friendly
        messages for display in templates.

        Examples of expected provider_response structure::

            {
                "status": 0,
                "messages": [
                    {"id": 111, "status": 27, "recipient": "98912..."}
                ]
            }

        Returns:
            str: A human-friendly summary of the status or a parsing error
            message if the response doesn't match the expected structure.
        """

        resp = self.provider_response
        if not isinstance(resp, dict):
            return "Could not parse provider response."

        overall_status = resp.get("status")
        if overall_status is None:
            return "Could not parse provider response."
        if overall_status != 0:
            return f"Request Failed (Overall Status: {overall_status})"

        try:
            message_info = resp.get("messages", [])[0]
            status_code = message_info.get("status")
        except (IndexError, AttributeError):
            return "Could not parse provider response."

        if status_code is None:
            return "Could not parse provider response."

        status_map = {
            0: lambda info: f"Success (Provider ID: {info.get('id')})",
            1: lambda info: "Invalid recipient number",
            14: lambda info: "Insufficient credit",
            27: lambda info: "Recipient is blacklisted",
            33: lambda info: "Recipient has blocked messages from this sender",
        }

        if status_code in status_map:
            return status_map[status_code](message_info)

        return f"Failed with provider code: {status_code}"
