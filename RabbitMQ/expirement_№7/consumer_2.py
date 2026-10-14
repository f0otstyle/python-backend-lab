import asyncio
import json
import random
from aio_pika.abc import AbstractIncomingMessage
from rabbitmq import setup_channel, declare_order_queue, connect_rabbitmq
from time_time import timers


@timers
async def handler_order(message: AbstractIncomingMessage):
    async with message.process():
        try:
            event_data = json.loads(message.body.decode())
            task_id = event_data.get('task_id', 'Неизвестно')
            delay = random.uniform(0.01, 1.0)
            await asyncio.sleep(delay)
            print(f"Консьюмер 2 обработал задачу № {task_id}")

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
