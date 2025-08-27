import json
import asyncio
import aio_pika
from app.config import get_settings
from app.cache import CLIENT_CONFIG_CACHE, ClientConfig

async def consume_config_events():
    settings = get_settings()
    connection = await aio_pika.connect_robust(
        f"amqp://{settings.rabbit_user}:{settings.rabbit_pass}@{settings.rabbit_host}/"
    )

    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            'config_events_exchange', aio_pika.ExchangeType.FANOUT, durable=True
        )
        queue = await channel.declare_queue(exclusive=True)
        await queue.bind(exchange)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    event_type = message.type
                    body = message.body.decode()
                    data = json.loads(body)

                    if event_type == 'user.updated':
                        api_key = data.pop('api_key')
                        CLIENT_CONFIG_CACHE[api_key] = ClientConfig(**data)
                    elif event_type == 'user.deleted':
                        api_key = data['api_key']
                        if api_key in CLIENT_CONFIG_CACHE:
                            del CLIENT_CONFIG_CACHE[api_key]
