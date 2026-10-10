import json
import logging
import aio_pika
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue, ExchangeType

EXCHANGE_NAME = "taxi.events"
EXCHANGE_TYPE = ExchangeType.TOPIC

ROUTING_KEYS = {
    "ORDER_CREATED": "order.created",
    "ORDER_ASSIGNED": "order.assigned",
    "RIDE_FINISHED": "ride.finished",
    "PAYMENT_COMPLETED": "payment.completed"
}

QUEUE_ORDER_PROCESSING = "queue.order.processing"
QUEUE_ANALYTICS = "queue.analytics.all_orders"

logger = logging.getLogger("rabbitmq")


async def get_connection():
    return await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")


async def setup_infrastructure(channel: AbstractChannel):
    """Объявляем обмен и очереди"""
    exchange = await channel.declare_exchange(
        EXCHANGE_NAME,
        ExchangeType.TOPIC,
        durable=True
    )

    queue_processing = await channel.declare_queue(
        QUEUE_ORDER_PROCESSING,
        durable=True)
    await queue_processing.bind(
        exchange,
        routing_key=ROUTING_KEYS["ORDER_CREATED"]
        )

    queue_analytics = await channel.declare_queue(
        QUEUE_ANALYTICS,
        durable=True
        )
    await queue_analytics.bind(exchange, routing_key="order.*")

    return exchange


async def publish_event(
    channel: AbstractChannel,
    exchange_name: str,
    routing_key: str,
    data: dict,
    mandatory: bool = False
):
    """Публикация сообщения"""
    exchange = await channel.get_exchange(exchange_name)

    message = aio_pika.Message(
        body=json.dumps(data).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        content_type="application/json"
    )

    try:
        await exchange.publish(
            message,
            routing_key=routing_key,
            mandatory=mandatory
        )
        logger.info(f"✅ Сообщение отправлено: {routing_key}")
    except aio_pika.exceptions.DeliveryError as e:

        logger.error(f"❌ Сообщение возвращено (нет очередей): {e}")
        raise
