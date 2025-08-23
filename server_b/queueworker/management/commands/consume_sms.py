import json
import os
import signal
import pika
from django.core.management.base import BaseCommand
from messaging.models import Message
from providers.models import Provider
from providers import registry

class Command(BaseCommand):
    help = 'Consume SMS from RabbitMQ'

    def add_arguments(self, parser):
        parser.add_argument('--queue', default='sms.outbound')

    def handle(self, *args, **opts):
        queue = opts['queue']
        url = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
        params = pika.URLParameters(url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=queue, durable=True)
        channel.basic_qos(prefetch_count=1)

        def on_message(ch, method, properties, body):
            try:
                payload = json.loads(body)
                provider = Provider.objects.get(id=payload['policy']['provider_id'])
                ProviderCls = registry.get(provider.type)
                prov = ProviderCls()
                result = prov.send(payload, provider.__dict__)
                Message.objects.update_or_create(
                    tracking_id=payload['tracking_id'],
                    defaults={'customer_id': payload['customer_id'], 'provider': provider, 'status': 'sent' if result.ok else 'failed', 'provider_message_id': result.provider_message_id, 'last_error': result.error}
                )
                ch.basic_ack(method.delivery_tag)
            except Exception:
                ch.basic_ack(method.delivery_tag)

        channel.basic_consume(queue=queue, on_message_callback=on_message)

        def stop(*_):
            channel.stop_consuming()
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

        channel.start_consuming()
        connection.close()
