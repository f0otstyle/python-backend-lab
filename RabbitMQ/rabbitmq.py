import json

from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue
import aio_pika

ORDER_EXCHANGE = "order"
ORDER_QUEUE = 'order_queue'
ROUTING_KEY = "order_create"


async def connect_rabbitmq():
    return await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")


async def declare_order_exchange(channel: AbstractChannel):
    return await channel.declare_exchange(ORDER_EXCHANGE, durable=True)


async def declare_order_queue(
        channel: AbstractChannel,
        exchange: AbstractExchange
         ):
    queue: AbstractQueue = await channel.declare_queue(
        name=ORDER_QUEUE,
        durable=True
        )
    await queue.bind(exchange=exchange, routing_key=ROUTING_KEY)
    return queue


async def publish_json(
        exchange: AbstractExchange,
        routing_key: str,
        data: dict
        ):
    message = aio_pika.Message(
        json.dumps(data).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
    await exchange.publish(message, routing_key=routing_key)
