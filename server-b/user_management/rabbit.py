import pika
import json
from django.conf import settings

def get_rabbit_connection():
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    return pika.BlockingConnection(pika.ConnectionParameters(host=settings.RABBITMQ_HOST, credentials=credentials))

def declare_config_exchange(channel):
    channel.exchange_declare(exchange=settings.CONFIG_EVENTS_EXCHANGE, exchange_type='fanout', durable=True)

def publish_user_event(user, event_type):
    connection = get_rabbit_connection()
    channel = connection.channel()
    declare_config_exchange(channel)

    if event_type == 'user.deleted':
        payload = {
            'api_key': str(user.profile.api_key),
            'user_id': user.id,
        }
    else:
        payload = {
            'api_key': str(user.profile.api_key),
            'user_id': user.id,
            'username': user.username,
            'is_active': user.is_active,
            'daily_quota': user.profile.daily_quota,
        }

    channel.basic_publish(
        exchange=settings.CONFIG_EVENTS_EXCHANGE,
        routing_key='',
        body=json.dumps(payload),
        properties=pika.BasicProperties(
            content_type='application/json',
            delivery_mode=2,  # make message persistent
            type=event_type,
        )
    )
    connection.close()
