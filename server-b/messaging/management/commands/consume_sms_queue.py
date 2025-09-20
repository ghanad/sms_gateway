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


class Command(BaseCommand):
    """Consume RabbitMQ queue and persist messages reliably to the database."""

    def handle(self, *args, **options):  # pragma: no cover - mostly I/O
        credentials = pika.PlainCredentials(
            settings.RABBITMQ_USER, settings.RABBITMQ_PASS
        )
        
        params = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST, 
            credentials=credentials,
            virtual_host=settings.RABBITMQ_VHOST 
        )
        
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        
        queue_name = settings.RABBITMQ_SMS_QUEUE
        dlq_name = settings.RABBITMQ_SMS_DLQ_USER_NOT_FOUND
        wait_queue_name = settings.RABBITMQ_SMS_RETRY_WAIT_QUEUE
        wait_queue_ttl = settings.RABBITMQ_SMS_RETRY_WAIT_TTL_MS

        channel.queue_declare(queue=queue_name, durable=True)
        channel.queue_declare(queue=dlq_name, durable=True)
        channel.queue_declare(
            queue=wait_queue_name,
            durable=True,
            arguments={
                "x-message-ttl": wait_queue_ttl,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": queue_name,
            },
        )

        channel.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            try:
                envelope = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                logger.warning("Invalid JSON message discarded: %r", body)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            persistent_props = pika.BasicProperties(delivery_mode=2)

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
            except User.DoesNotExist:
                logger.error(
                    "User %s not found; routing message to DLQ",
                    envelope.get("user_id"),
                )
                try:
                    ch.basic_publish(
                        exchange="",
                        routing_key=dlq_name,
                        body=body,
                        properties=persistent_props,
                    )
                except pika.exceptions.AMQPError:
                    logger.exception(
                        "Publishing to DLQ failed; attempting wait queue for retry",
                    )
                    try:
                        ch.basic_publish(
                            exchange="",
                            routing_key=wait_queue_name,
                            body=body,
                            properties=persistent_props,
                        )
                    except pika.exceptions.AMQPError:
                        logger.exception(
                            "Publishing to wait queue also failed; message will be re-queued",
                        )
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                        return
                    else:
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        return
                else:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return
            except Exception:
                logger.exception(
                    "Failed to persist message; scheduling retry via wait queue",
                )
                try:
                    ch.basic_publish(
                        exchange="",
                        routing_key=wait_queue_name,
                        body=body,
                        properties=persistent_props,
                    )
                except pika.exceptions.AMQPError:
                    logger.exception(
                        "Publishing to wait queue failed; message will be re-queued",
                    )
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    return
                else:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return
            else:
                ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=False)
        self.stdout.write(f"Listening on queue '{queue_name}' in vhost '{settings.RABBITMQ_VHOST}'. Press CTRL+C to exit.")
        
        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            channel.stop_consuming()
        finally:
            connection.close()