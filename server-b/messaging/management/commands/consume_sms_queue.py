import json
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPError

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.db.utils import OperationalError

from messaging.metrics import (
    sms_bad_payload_total,
    sms_permanent_errors_total,
    sms_publisher_confirm_nacks_total,
    sms_waitqueue_publish_total,
    sms_waitqueue_retry_total,
)
from messaging.models import Message, MessageStatus

logger = logging.getLogger(__name__)

RETRY_HEADER = "x-retry-count"
ERROR_TYPE_HEADER = "error_type"
FIRST_SEEN_HEADER = "first_seen_ts"
LAST_ATTEMPT_HEADER = "last_attempt_ts"

BAD_PAYLOAD_JSON_INVALID = "JSON_INVALID"
BAD_PAYLOAD_SCHEMA_INVALID = "SCHEMA_INVALID"
ERROR_USER_NOT_FOUND = "USER_NOT_FOUND"
ERROR_MAX_RETRIES = "MAX_RETRIES_EXCEEDED"
ERROR_TRANSIENT = "TRANSIENT_ERROR"


class PublishFailure(Exception):
    """Raised when publishing to RabbitMQ fails."""


class SmsQueueConsumer:
    """Encapsulates the core queue handling logic."""

    def __init__(self, channel: BlockingChannel):
        self.channel = channel
        self.queue_name = settings.RABBITMQ_SMS_QUEUE
        self.wait_queue_name = settings.RABBITMQ_SMS_WAIT_QUEUE
        self.wait_queue_ttl = settings.RABBITMQ_SMS_WAIT_QUEUE_TTL_MS
        self.permanent_dlq_name = settings.RABBITMQ_SMS_DLQ_PERMANENT
        self.bad_payload_dlq_name = settings.RABBITMQ_SMS_DLQ_BAD_PAYLOAD
        self.max_retry_attempts = getattr(settings, "SMS_RETRY_MAX_ATTEMPTS", 5)
        self.use_dlx_for_permanent = getattr(
            settings, "FEATURE_USE_DLX_FOR_PERM_ERRORS", True
        )
        self.enable_bad_payload_dlq = getattr(
            settings, "FEATURE_BAD_PAYLOAD_DLQ", True
        )
        self.fallback_dlq_name = getattr(settings, "RABBITMQ_SMS_DLQ_FALLBACK", None)

    # ------------------------------------------------------------------
    # Queue / topology management
    # ------------------------------------------------------------------
    def setup_topology(self) -> None:
        """Declare queues with the expected durability and DLX settings."""

        # Always declare the DLQs first so bindings exist when the main queue
        # is declared with dead-letter configuration.
        self.channel.queue_declare(queue=self.permanent_dlq_name, durable=True)

        if self.enable_bad_payload_dlq:
            self.channel.queue_declare(queue=self.bad_payload_dlq_name, durable=True)

        if not self.use_dlx_for_permanent and self.fallback_dlq_name:
            self.channel.queue_declare(queue=self.fallback_dlq_name, durable=True)

        main_arguments: Dict[str, Any] = {}
        if self.use_dlx_for_permanent:
            main_arguments.update(
                {
                    "x-dead-letter-exchange": "",
                    "x-dead-letter-routing-key": self.permanent_dlq_name,
                }
            )

        self.channel.queue_declare(
            queue=self.queue_name,
            durable=True,
            arguments=main_arguments or None,
        )

        wait_arguments = {
            "x-message-ttl": self.wait_queue_ttl,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": self.queue_name,
        }
        self.channel.queue_declare(
            queue=self.wait_queue_name,
            durable=True,
            arguments=wait_arguments,
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _extract_retry_count(self, headers: Dict[str, Any]) -> int:
        raw = headers.get(RETRY_HEADER)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    def _validate_envelope(self, envelope: Dict[str, Any]) -> Optional[str]:
        if not isinstance(envelope, dict):
            return "Envelope must be a JSON object"
        required = ("tracking_id", "user_id", "to", "text")
        for field in required:
            if field not in envelope:
                return f"Missing required field: {field}"
        try:
            uuid.UUID(str(envelope["tracking_id"]))
        except (TypeError, ValueError):
            return "tracking_id is not a valid UUID"
        try:
            int(envelope["user_id"])
        except (TypeError, ValueError):
            return "user_id must be an integer"
        if not isinstance(envelope.get("to"), str) or not envelope["to"]:
            return "to must be a non-empty string"
        if not isinstance(envelope.get("text"), str) or not envelope["text"]:
            return "text must be a non-empty string"
        return None

    def _build_properties(
        self, headers: Dict[str, Any], correlation_id: Optional[str]
    ):
        return pika.BasicProperties(
            delivery_mode=2,
            headers=headers,
            correlation_id=correlation_id,
        )

    def _publish_with_confirm(
        self,
        routing_key: str,
        body: bytes,
        headers: Dict[str, Any],
        correlation_id: Optional[str],
    ) -> None:
        props = self._build_properties(headers, correlation_id)
        try:
            success = self.channel.basic_publish(
                exchange="",
                routing_key=routing_key,
                body=body,
                properties=props,
                mandatory=False,
            )
        except AMQPError as exc:  # pragma: no cover - network failure
            raise PublishFailure(str(exc)) from exc
        if not success:
            raise PublishFailure("Publisher confirm returned False")

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------
    def handle_message(self, ch, method, properties, body: bytes):
        delivery_tag = method.delivery_tag
        correlation_id = getattr(properties, "correlation_id", None)
        headers = dict(getattr(properties, "headers", {}) or {})
        now_iso = self._now_iso()
        headers.setdefault(FIRST_SEEN_HEADER, now_iso)
        headers[LAST_ATTEMPT_HEADER] = now_iso
        retry_count = self._extract_retry_count(headers)
        if retry_count > 0:
            sms_waitqueue_retry_total.inc()

        try:
            envelope = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            headers[ERROR_TYPE_HEADER] = BAD_PAYLOAD_JSON_INVALID
            logger.warning(
                "Invalid JSON payload encountered", extra={"correlation_id": correlation_id}
            )
            self._route_bad_payload(ch, delivery_tag, body, headers, correlation_id)
            return

        schema_error = self._validate_envelope(envelope)
        if schema_error:
            headers[ERROR_TYPE_HEADER] = BAD_PAYLOAD_SCHEMA_INVALID
            logger.warning(
                "Schema validation failed", extra={"error": schema_error, "correlation_id": correlation_id}
            )
            self._route_bad_payload(ch, delivery_tag, body, headers, correlation_id)
            return

        tracking_id = uuid.UUID(str(envelope["tracking_id"]))
        user_id = int(envelope["user_id"])
        headers.setdefault("tracking_id", str(tracking_id))
        correlation_id = correlation_id or str(tracking_id)
        log_context = {
            "tracking_id": str(tracking_id),
            "correlation_id": correlation_id,
            "retry_count": retry_count,
        }

        if Message.objects.filter(tracking_id=tracking_id).exists():
            logger.info("Duplicate message ignored", extra=log_context)
            ch.basic_ack(delivery_tag=delivery_tag)
            return

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.error("User not found for message", extra={**log_context, "user_id": user_id})
            self._handle_permanent_error(
                ch,
                delivery_tag,
                body,
                headers,
                correlation_id,
                ERROR_USER_NOT_FOUND,
                log_context,
            )
            return

        try:
            with transaction.atomic():
                message, created = Message.objects.get_or_create(
                    tracking_id=tracking_id,
                    defaults={
                        "user": user,
                        "recipient": envelope.get("to"),
                        "text": envelope.get("text"),
                        "status": MessageStatus.PENDING,
                        "initial_envelope": envelope,
                    },
                )
        except IntegrityError:
            logger.info(
                "IntegrityError encountered; treating as duplicate",
                extra=log_context,
            )
            ch.basic_ack(delivery_tag=delivery_tag)
            return
        except OperationalError:
            logger.exception("Operational error while persisting message", extra=log_context)
            self._handle_transient_error(
                ch,
                delivery_tag,
                body,
                headers,
                correlation_id,
                ERROR_TRANSIENT,
                retry_count,
                log_context,
            )
            return
        except Exception:  # pragma: no cover - defensive safeguard
            logger.exception("Unexpected error while persisting message", extra=log_context)
            self._handle_transient_error(
                ch,
                delivery_tag,
                body,
                headers,
                correlation_id,
                ERROR_TRANSIENT,
                retry_count,
                log_context,
            )
            return

        if not created:
            logger.info("Message already exists; acking", extra={**log_context, "message_id": message.id})
            ch.basic_ack(delivery_tag=delivery_tag)
            return

        logger.info("Message persisted", extra={**log_context, "message_id": message.id})
        ch.basic_ack(delivery_tag=delivery_tag)

    # ------------------------------------------------------------------
    # Specialized routing helpers
    # ------------------------------------------------------------------
    def _route_bad_payload(
        self,
        ch,
        delivery_tag: int,
        body: bytes,
        headers: Dict[str, Any],
        correlation_id: Optional[str],
    ) -> None:
        if not self.enable_bad_payload_dlq:
            # Backward-compatible rollback path: simply acknowledge so poison
            # messages do not endlessly cycle.
            ch.basic_ack(delivery_tag=delivery_tag)
            return

        try:
            self._publish_with_confirm(
                self.bad_payload_dlq_name,
                body,
                dict(headers),
                correlation_id,
            )
        except PublishFailure:
            sms_publisher_confirm_nacks_total.inc()
            logger.exception(
                "Failed to publish malformed payload to bad-payload DLQ",
                extra={"correlation_id": correlation_id},
            )
            ch.basic_nack(delivery_tag=delivery_tag, requeue=True)
        else:
            sms_bad_payload_total.inc()
            ch.basic_ack(delivery_tag=delivery_tag)

    def _handle_permanent_error(
        self,
        ch,
        delivery_tag: int,
        body: bytes,
        headers: Dict[str, Any],
        correlation_id: Optional[str],
        error_type: str,
        log_context: Dict[str, Any],
    ) -> None:
        sms_permanent_errors_total.inc()
        if self.use_dlx_for_permanent:
            ch.basic_reject(delivery_tag=delivery_tag, requeue=False)
            return

        target_queue = self.fallback_dlq_name or self.permanent_dlq_name
        try:
            next_headers = dict(headers)
            next_headers[ERROR_TYPE_HEADER] = error_type
            self._publish_with_confirm(target_queue, body, next_headers, correlation_id)
        except PublishFailure:
            sms_publisher_confirm_nacks_total.inc()
            logger.exception(
                "Failed to publish to fallback DLQ for permanent error",
                extra=log_context,
            )
            ch.basic_nack(delivery_tag=delivery_tag, requeue=True)
        else:
            ch.basic_ack(delivery_tag=delivery_tag)

    def _handle_transient_error(
        self,
        ch,
        delivery_tag: int,
        body: bytes,
        headers: Dict[str, Any],
        correlation_id: Optional[str],
        error_type: str,
        retry_count: int,
        log_context: Dict[str, Any],
    ) -> None:
        if retry_count >= self.max_retry_attempts:
            logger.error(
                "Max retry attempts exceeded; routing to permanent DLQ",
                extra={**log_context, "max_attempts": self.max_retry_attempts},
            )
            self._handle_permanent_error(
                ch,
                delivery_tag,
                body,
                headers,
                correlation_id,
                ERROR_MAX_RETRIES,
                log_context,
            )
            return

        next_headers = dict(headers)
        next_retry = retry_count + 1
        next_headers[ERROR_TYPE_HEADER] = error_type
        next_headers[RETRY_HEADER] = next_retry
        next_headers["retry_count"] = next_retry
        try:
            self._publish_with_confirm(
                self.wait_queue_name,
                body,
                next_headers,
                correlation_id,
            )
        except PublishFailure:
            sms_publisher_confirm_nacks_total.inc()
            logger.exception(
                "Failed to publish message to wait queue", extra=log_context
            )
            ch.basic_nack(delivery_tag=delivery_tag, requeue=True)
        else:
            sms_waitqueue_publish_total.inc()
            logger.info(
                "Message routed to wait queue for retry",
                extra={**log_context, "next_retry": next_retry},
            )
            ch.basic_ack(delivery_tag=delivery_tag)


class Command(BaseCommand):
    """Consume RabbitMQ queue and persist messages reliably to the database."""

    def handle(self, *args, **options):  # pragma: no cover - mostly I/O
        credentials = pika.PlainCredentials(
            settings.RABBITMQ_USER, settings.RABBITMQ_PASS
        )

        params = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            credentials=credentials,
            virtual_host=settings.RABBITMQ_VHOST,
        )

        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.confirm_delivery()

        consumer = SmsQueueConsumer(channel)
        consumer.setup_topology()

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue=consumer.queue_name,
            on_message_callback=consumer.handle_message,
            auto_ack=False,
        )

        self.stdout.write(
            f"Listening on queue '{consumer.queue_name}' in vhost '{settings.RABBITMQ_VHOST}'. Press CTRL+C to exit."
        )

        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            channel.stop_consuming()
        finally:
            connection.close()
