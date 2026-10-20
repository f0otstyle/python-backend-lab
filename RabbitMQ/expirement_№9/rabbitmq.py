import json

import aio_pika
from aio_pika.abc import (AbstractChannel,
                          AbstractConnection,
                          AbstractExchange,
                          AbstractQueue
                          )


EXCHANGE_NAME = "order_exchange"
QUEUE_NAME = "order_queue"
ROUTING_KEY = "order.create"

DLX_EXCHANGE = "order.dlx"
DLQ_QUEUE = "order_dlq"
DLQ_ROUTING_KEY = "order.dead_letter"

RETRY_QUEUE = "order_retry_queue"
RETRY_ROUTING_KEY = "order.retry"
RETRY_TTL_MS = 5000
MAX_RETRIES = 3


async def connect_rabbitmq():
    return await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")


async def setup_channel(connect: AbstractConnection):
    channel = await connect.channel(publisher_confirms=True)
    exchange = await channel.declare_exchange(EXCHANGE_NAME, durable=True)
    await channel.set_qos(prefetch_count=50)

    return channel, exchange


async def declare_dlx_exchange(channel: AbstractChannel):
    return await channel.declare_exchange(DLX_EXCHANGE, durable=True)


async def declare_order_queue(
        channel: AbstractChannel,
        exchange: AbstractExchange
         ):
    queue: AbstractQueue = await channel.declare_queue(
        name=QUEUE_NAME,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-consumer-timeout": 3000
            }
        )
    await queue.bind(exchange=exchange, routing_key=ROUTING_KEY)
    return queue


async def declare_dlx_queue(
        channel: AbstractChannel,
        exchange: AbstractExchange
         ):
    queue_dlx: AbstractQueue = await channel.declare_queue(
        name=DLQ_QUEUE,
        durable=True
    )
    await queue_dlx.bind(exchange=exchange, routing_key=DLQ_ROUTING_KEY)
    return queue_dlx


async def declare_retry_queue(
        channel: AbstractChannel,
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
    return queue


async def event_publish_json(
        exchange: AbstractExchange,
        routing_key: str,
        data: dict,
        ):
    message = aio_pika.Message(
        json.dumps(data).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
    await exchange.publish(
        message,
        routing_key=routing_key,
        )
