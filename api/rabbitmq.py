import json

from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractQueue,
    AbstractConnection
    )
import aio_pika

ORDER_EXCHANGE = "taxi_exchange"
ORDER_QUEUE = 'taxi_queue'
ROUTING_KEY = "taxi_create"

DLX_EXCHANGE = "taxi.dlx"
DLQ_QUEUE = "taxi_dlq"
DLQ_ROUTING_KEY = "taxi_dead.letter"

RETRY_QUEUE = "taxi_retry_queue"
RETRY_ROUTING_KEY = "taxi_retry"
RETRY_TTL_MS = 5000
MAX_RETRIES = 3


async def connect_rabbitmq():
    return await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")


# Обменники
async def declare_order_exchange(connect: AbstractConnection):
    channel = await connect.channel(publisher_confirms=True)
    exchange = await channel.declare_exchange(ORDER_EXCHANGE, durable=True)
    await channel.set_qos(prefetch_count=1)

    return channel, exchange


async def declare_dlx_exchange(channel: AbstractChannel):
    return await channel.declare_exchange(DLX_EXCHANGE, durable=True)


# Очереди
async def declare_order_queue(
        channel: AbstractChannel,
        exchange: AbstractExchange
         ):
    queue: AbstractQueue = await channel.declare_queue(
        name=ORDER_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": DLQ_ROUTING_KEY,
            "x-message-ttl": 60000,
            "x-max-length": 1000,
            "x-consumer-timeout": 3000,
        },
        )
    await queue.bind(exchange=exchange, routing_key=ROUTING_KEY)
    return queue


async def declare_dlx_order_queue(
        channel: AbstractChannel,
        exchange: AbstractExchange
         ):
    queue_dlx: AbstractQueue = await channel.declare_queue(
        name=DLQ_QUEUE,
        durable=True
    )
    await queue_dlx.bind(exchange=exchange, routing_key=DLQ_ROUTING_KEY)
    return queue_dlx


async def declare_retry_order_queue(
        channel: AbstractChannel,
         ):
    queue = await channel.declare_queue(
        RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": RETRY_TTL_MS,
            "x-dead-letter-exchange": ORDER_EXCHANGE,
            "x-dead-letter-routing-key": ROUTING_KEY,
        },
    )
    return queue


async def publish_json(
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
