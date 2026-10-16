import asyncio
import json
import os
from uuid import uuid4
from aio_pika.abc import AbstractIncomingMessage
from redis.asyncio import Redis
from rabbitmq import (connect_rabbitmq,
                      setup_channel,
                      declare_dlx_exchange,
                      declare_order_queue,
                      declare_dlx_queue,
                      declare_retry_queue,
                      MAX_RETRIES
                      )

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
redis = Redis(host=REDIS_HOST, port=6379, decode_responses=True)


async def handler_order(message: AbstractIncomingMessage):
    async with message.process(ignore_processed=True):
        try:
            event_data = json.loads(message.body.decode())
            event_id = event_data.get('event_id', 'Неизвестно')

            dedep_key = f"dedep:order:{event_id}"
            ock_acquired = await redis.set(dedep_key, "1", nx=True, ex=3600)
            if not ock_acquired:
                print("Дубликат")
                return

            print(f"ОБРАБОТКА события {event_id}")

            print(f"Консьюмер 1 обработал задачу № {event_id}")
        except Exception as e:
            print(f"Ошибка обработки сообщения: {e}")
            print("Возвращаю в очередь для повторной попытки...")
            await message.nack(requeue=True)


async def main():
    connect = await connect_rabbitmq()
    channel, exchange = await setup_channel(connect)

    await declare_dlx_exchange(channel)
    queue_order = await declare_order_queue(channel, exchange)

    await queue_order.consume(handler_order)

    try:
        await asyncio.Future()
    finally:
        await redis.aclose()
        await connect.close()

if __name__ == "__main__":
    asyncio.run(main())
