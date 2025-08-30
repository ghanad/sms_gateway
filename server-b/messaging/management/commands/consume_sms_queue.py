import json
import logging
import pika
from django.conf import settings
from django.core.management.base import BaseCommand
from messaging.tasks import process_outbound_sms

logger = logging.getLogger(__name__)

QUEUE_NAME = "sms_outbound_queue"

class Command(BaseCommand):
    help = "Consume RabbitMQ queue and dispatch SMS processing tasks"

    def handle(self, *args, **options):
        credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
        params = pika.ConnectionParameters(host=settings.RABBITMQ_HOST, credentials=credentials)
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
                process_outbound_sms.delay(envelope)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                logger.exception("Failed to dispatch process_outbound_sms task")
                ch.basic_ack(delivery_tag=method.delivery_tag)

        channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
        self.stdout.write("Listening on sms_outbound_queue. Press CTRL+C to exit.")
        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            channel.stop_consuming()
        finally:
            connection.close()
