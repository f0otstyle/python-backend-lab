import json
import os

from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractQueue,
    AbstractConnection
    )
import aio_pika

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_URL = f"amqp://guest:guest@{RABBITMQ_HOST}:5672/"

EXCHANGE_NAME = "taxi_events"
QUEUE_NAME = "drivers_queue"
ROUTING_KEY = "order.create"

DLX_EXCHANGE = "taxi_driver.dlx"

RETRY_QUEUE = "taxi_driver_retry_queue"
RETRY_ROUTING_KEY = "driver.retry"
RETRY_TTL_MS = 5000
MAX_RETRIES = 3


async def connect_rabbitmq():
    return await aio_pika.connect_robust(RABBITMQ_URL)


async def setup_channel(connect: AbstractConnection):
    channel = await connect.channel(publisher_confirms=True)
    exchange = await channel.declare_exchange(EXCHANGE_NAME, durable=True)
    await channel.set_qos(prefetch_count=1)

    return channel, exchange


async def declare_dlx_exchange(channel: AbstractChannel):
    return await channel.declare_exchange(DLX_EXCHANGE, durable=True)


# Очереди
async def declare_queue(
        channel: AbstractChannel,
        exchange: AbstractExchange
         ):
    queue: AbstractQueue = await channel.declare_queue(
        name=QUEUE_NAME,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": RETRY_ROUTING_KEY,
            "x-message-ttl": 60000,
            "x-max-length": 1000,
            "x-consumer-timeout": 3000,
        },
        )
    await queue.bind(exchange=exchange, routing_key=ROUTING_KEY)
    return queue


async def declare_retry_queue(
        channel: AbstractChannel,
        exchange: AbstractExchange
         ):
    queue = await channel.declare_queue(
        RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": RETRY_TTL_MS,
            "x-dead-letter-exchange": EXCHANGE_NAME,
            "x-dead-letter-routing-key": ROUTING_KEY,
        },
    )
    await queue.bind(exchange=exchange, routing_key=RETRY_ROUTING_KEY)
    return queue


async def event_publish_json(
        exchange: AbstractExchange,
        routing_key: str,
        event_id: str,
        data: dict,
        ):
    message = aio_pika.Message(
        json.dumps(data).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        headers={'event_id': event_id}
        )
    await exchange.publish(
        message,
        routing_key=routing_key,
        )
