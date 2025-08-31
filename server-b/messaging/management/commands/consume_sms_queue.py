import json
import logging
import uuid
import pika

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from messaging.models import Message, MessageStatus

logger = logging.getLogger(__name__)

QUEUE_NAME = "sms_outbound_queue"


class Command(BaseCommand):
    """Consume RabbitMQ queue and persist messages reliably to the database."""

    def handle(self, *args, **options):  # pragma: no cover - mostly I/O
        credentials = pika.PlainCredentials(
            settings.RABBITMQ_USER, settings.RABBITMQ_PASS
        )
        params = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST, credentials=credentials
        )
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        channel.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            try:
                envelope = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                logger.warning("Invalid JSON message discarded: %r", body)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            try:
                with transaction.atomic():
                    tracking_id = uuid.UUID(envelope["tracking_id"])
                    if Message.objects.filter(tracking_id=tracking_id).exists():
                        logger.info("Duplicate message %s ignored", tracking_id)
                    else:
                        user = User.objects.get(pk=envelope["user_id"])
                        Message.objects.create(
                            user=user,
                            tracking_id=tracking_id,
                            recipient=envelope.get("to"),
                            text=envelope.get("text"),
                            status=MessageStatus.PENDING,
                            initial_envelope=envelope,
                        )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                logger.exception("Failed to persist message; re-queueing")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback, auto_ack=False)
        self.stdout.write("Listening on sms_outbound_queue. Press CTRL+C to exit.")
        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            channel.stop_consuming()
        finally:
            connection.close()
