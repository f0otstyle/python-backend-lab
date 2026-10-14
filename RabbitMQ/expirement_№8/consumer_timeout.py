import asyncio
import json

from aio_pika.abc import AbstractIncomingMessage
from rabbitmq import setup_channel, declare_order_queue, connect_rabbitmq


async def handler_order(message: AbstractIncomingMessage):
    async with message.process():
        try:
            event_data = json.loads(message.body.decode())
            task_id = event_data.get('task_id', 'Неизвестно')
            await asyncio.sleep(10)
            print(f"Консьюмер 1 обработал задачу № {task_id}")
        except Exception as e:
            print(f"Ошибка обработки сообщения: {e}")
            await message.nack(requeue=True)


async def main():
    connection = await connect_rabbitmq()
    channel, exchange = await setup_channel(connection)
    queue = await declare_order_queue(channel, exchange)

    await queue.consume(handler_order)

    await asyncio.Future()

    await queue.close()

if __name__ == "__main__":
    asyncio.run(main())
