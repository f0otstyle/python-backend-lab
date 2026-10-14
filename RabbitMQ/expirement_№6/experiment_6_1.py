import json
import aio_pika
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue

ORDER_EXCHANGE = "order"


async def connect_rabbitmq():
    return await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")


async def declare_order_exchange(channel: AbstractChannel):
    return await channel.declare_exchange(ORDER_EXCHANGE, durable=True)


async def declare_order_queue(
    channel: AbstractChannel,
    exchange: AbstractExchange,
    queue_name: str,
    durable: bool,
    routing_key: str,
) -> AbstractQueue:
    queue = await channel.declare_queue(name=queue_name, durable=durable)
    await queue.bind(exchange=exchange, routing_key=routing_key)
    return queue


async def publish_json(
    exchange: AbstractExchange,
    routing_key: str,
    data: dict,
    persistent: bool,
):
    delivery_mode = (
        aio_pika.DeliveryMode.PERSISTENT
        if persistent
        else aio_pika.DeliveryMode.NOT_PERSISTENT
    )
    message = aio_pika.Message(
        json.dumps(data).encode(),
        delivery_mode=delivery_mode,
    )
    await exchange.publish(message, routing_key=routing_key)
