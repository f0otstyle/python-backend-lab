import asyncio
from experiment_6_1 import (
    connect_rabbitmq,
    declare_order_exchange,
    declare_order_queue,
    publish_json,
)


async def run_case(durable: bool, persistent: bool):
    queue_name = f"test_q_{durable}_{persistent}"
    routing_key = f"rk_{durable}_{persistent}"

    connection = await connect_rabbitmq()
    channel = await connection.channel()
    exchange = await declare_order_exchange(channel)
    queue = await declare_order_queue(
        channel, exchange,
        queue_name=queue_name,
        durable=durable,
        routing_key=routing_key,
    )

    for i in range(100):
        await publish_json(
            exchange=exchange,
            routing_key=routing_key,
            data={"i": i},
            persistent=persistent,
        )

    print(f"[{queue_name}] опубликовано 100 сообщений "
          f"(durable={durable}, persistent={persistent})")
    await connection.close()


async def main():
    for durable in (True, False):
        for persistent in (True, False):
            await run_case(durable, persistent)


if __name__ == "__main__":
    asyncio.run(main())
