import asyncio
from rabbitmq import connect_rabbitmq, setup_channel, publish_json, ROUTING_KEY


async def main():
    print("Подключение к RabbitMQ...")
    connection = await connect_rabbitmq()

    async with connection:
        channel, exchange = await setup_channel(connection)

        for i in range(1, 1001):
            await asyncio.sleep(0.1)
            data = {
                "task_id": i,
                "message": f"Это тестовое сообщение номер {i}"
            }
            print(f"{data["task_id"]}")
            await publish_json(
                exchange=exchange,
                routing_key=ROUTING_KEY,
                data=data
            )


if __name__ == "__main__":
    asyncio.run(main())
