import asyncio
from rabbitmq import connect_rabbitmq


async def main():
    connection = await connect_rabbitmq()
    channel = await connection.channel()

    for durable in (True, False):
        for persistent in (True, False):
            queue_name = f"test_q_{durable}_{persistent}"
            try:
                q = await channel.declare_queue(queue_name, passive=True)
                count = q.declaration_result.message_count
                print(f"{queue_name:25} → {count} сообщений")
            except Exception as e:
                print(f"{queue_name:25} → НЕ СУЩЕСТВУЕТ ({type(e).__name__})")

    await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
