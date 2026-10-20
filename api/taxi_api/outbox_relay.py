import asyncio
import asyncpg
import json
import os
import logging

from rabbitmq import (connect_rabbitmq,
                      setup_channel,
                      event_publish_json,
                      ROUTING_KEY
                      )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_USER = os.getenv('POSTGRES_USER', 'pgAdmin')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')
DB_NAME = os.getenv('POSTGRES_DB', 'taxi_db')

POLL_INTERVAL = 1.0  # Проверяем outbox каждую секунду


async def outbox_relay():
    db_pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        min_size=1,
        max_size=10
    )
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS outbox (
                id SERIAL PRIMARY KEY,
                event_id VARCHAR NOT NULL,
                event_type VARCHAR,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                published BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)

    connection = await connect_rabbitmq()
    channel, exchange = await setup_channel(connection)
    try:
        while True:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, event_id, event_type, payload
                    FROM outbox
                    WHERE published = FALSE
                    ORDER BY created_at ASC
                    LIMIT 10
                    """)

                for row in rows:
                    try:
                        payload_dict = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
                        event_id = row['event_id']
                        await event_publish_json(
                            exchange=exchange,
                            routing_key=ROUTING_KEY,
                            event_id=event_id,
                            data=payload_dict
                            )

                        logger.info('Сообщение отправленно в RabbitMQ')

                        await conn.execute("""
                            UPDATE outbox
                            SET published = TRUE
                            WHERE id = $1
                        """, row['id'])
                    except Exception as error:
                        logger.error(f'Произошла ошибка {error} у записи {row['id']}')

                await asyncio.sleep(1)
    finally:
        await db_pool.close()
        await connection.close()


if __name__ == "__main__":
    asyncio.run(outbox_relay())
