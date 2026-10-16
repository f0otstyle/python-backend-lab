import asyncio
import json
from aio_pika.abc import AbstractIncomingMessage
from rabbitmq import (connect_rabbitmq,
                      setup_channel,
                      declare_dlx_exchange,
                      declare_order_queue,
                      declare_dlx_queue,
                      declare_retry_queue,
                      MAX_RETRIES
                      )


async def handler_order(message: AbstractIncomingMessage):
    async with message.process(ignore_processed=True):
        try:
            event_data = json.loads(message.body.decode())
            event_id = event_data.get('event_id', 'Неизвестно')
            delivery_count = message.headers.get('x-delivery-count', 0)

            if delivery_count >= MAX_RETRIES:
                print(f'Сообщение уже пыталось обработаьть {delivery_count}')
                await message.nack(requeue=False)
                return

            print(f"Консьюмер 1 обработал задачу № {event_id}")
            raise ValueError(f"КРИТИЧЕСКИЙ СБОЙ: Невозможно обработать {event_id}")
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

    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
