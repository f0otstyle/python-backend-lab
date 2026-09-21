import asyncio
import json

from aio_pika.abc import AbstractIncomingMessage
from rabbitmq import (
    connect_rabbitmq,
    declare_order_exchange,
    declare_order_queue
)


async def handler_order(message: AbstractIncomingMessage):
    async with message.process():
        try:
            event_data = json.loads(message.body.decode())
            order = event_data.get('ride', 'Данного заказа нет')
            print(f"Полученное сообщение:\n\nПользователь {order['user_name']}.\nВаш заказ принял {order['driver']} на автомобтили {order['car']}.\nЗаказ осуществляется по адресу {order['to_addres']}.\nСтоимость заказа будет {order['price']} ")
        except Exception as e:
            print(f"Ошибка обработки сообщения: {e}")
            await message.nack(requeue=True)


async def main():
    connection = await connect_rabbitmq()
    channel = await connection.channel()
    exchange = await declare_order_exchange(channel)
    queue = await declare_order_queue(channel, exchange)

    await queue.consume(handler_order)

    await asyncio.Future()

    await queue.close()

if __name__ == "__main__":
    asyncio.run(main())
