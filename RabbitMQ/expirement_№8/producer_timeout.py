import asyncio
from rabbitmq import connect_rabbitmq, setup_channel, publish_json, ROUTING_KEY


async def main():
    print("Подключение к RabbitMQ...")
    connection = await connect_rabbitmq()

    async with connection:
        channel, exchange = await setup_channel(connection)

        data = {
            "task_id": 1,
            "message": "Это тестовое сообщение номер 1"
        }
        print(f"{data["task_id"]}")
        await publish_json(
            exchange=exchange,
            routing_key=ROUTING_KEY,
            data=data
        )


if __name__ == "__main__":
    asyncio.run(main())
