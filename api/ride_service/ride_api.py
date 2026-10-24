import asyncio
from datetime import datetime, timezone
import json
from uuid import uuid4
from redis.asyncio import Redis
from fastapi import FastAPI
from pydantic import BaseModel
from contextlib import asynccontextmanager
from logging_log import logger, log
import asyncpg
from aio_pika.abc import AbstractIncomingMessage
from rabbitmq import (MAX_RETRIES,
                      connect_rabbitmq,
                      declare_dlx_exchange,
                      declare_dlx_queue,
                      setup_channel,
                      declare_queue,
                      declare_retry_queue
                      )
import os


DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_USER = os.getenv('POSTGRES_USER', 'pgAdmin')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')
DB_NAME = os.getenv('POSTGRES_DB', 'taxi_db')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

TIME = 5

db_pool = None


async def init_db():
    global db_pool
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
            CREATE TABLE IF NOT EXISTS rides (
                id SERIAL PRIMARY KEY,
                order_id INTEGER,
                driver_id INTEGER,
                user_id INTEGER,
                started_at TIMESTAMPTZ DEFAULT NOW(),
                finished_at TIMESTAMPTZ,
                duration INTEGER
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS taxi_card (
            user_id INTEGER PRIMARY KEY,
            balance NUMERIC NOT NULL CHECK (balance >= 0) DEFAULT 0
            )
        """)
    return db_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_pool = await init_db()
    redis = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    connection = await connect_rabbitmq()
    channel, exchange = await setup_channel(connection)

    app.state.inflight = set()

    app.state.redis = redis
    app.state.channel = channel
    app.state.exchange = exchange
    app.state.connection = connection

    await declare_dlx_exchange(channel)
    await declare_dlx_queue(channel, exchange)
    await declare_retry_queue(channel)
    queue = await declare_queue(channel, exchange)

    app.state.exchange = exchange
    app.state.connection = connection
    app.state.db = db_pool

    consumer_tag = await queue.consume(handler_order)
    app.state.consumer_tag = consumer_tag

    yield

    await queue.cancel(consumer_tag)

    if app.state.inflight:
        await asyncio.gather(*app.state.inflight, return_exceptions=True)

    await connection.close()
    await db_pool.close()
    await redis.aclose()

app = FastAPI(lifespan=lifespan)


class MoneySchema(BaseModel):
    money: float


async def handler_order(message: AbstractIncomingMessage):
    async with message.process(ignore_processed=True):
        try:
            body_str = message.body.decode()
            event_data = json.loads(body_str)

            if isinstance(event_data, str):
                event_data = json.loads(event_data)
            logger.info(f"Заголовки: {message.headers}")

            order_id = event_data.get('id')
            event_id = message.headers.get('event_id') or event_data.get('event_id')

            logger.info(f"event_id: {event_id}, order_id: {order_id}")

            if not event_id or not order_id:
                logger.error("В сообщении нет event_id или id заказа")
                await message.nack(requeue=False)
                return

            death_count = len(message.headers.get("x-death", []))
            if death_count >= MAX_RETRIES:
                logger.warning(f"Заказ {order_id} отправлен в DLQ после {death_count} попыток.")
                await message.nack(requeue=False)
                return

            async with db_pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                            INSERT INTO processed_events (event_id)
                            VALUES ($1)
                            ON CONFLICT DO NOTHING
                        ''', event_id)
                    except asyncpg.exceptions.UniqueViolationError:
                        logger.info(f'Дубликат: событие {event_id} уже обработано')
                        await message.ack()
                        return

                drive = await taxi_ride(order_id=order_id)
                if not drive:
                    logger.warning(
                        'Заказ не закончен'
                        )
                    await message.nack(requeue=True)
                    return

            logger.info(f'Заказ закончен для ID {order_id}')
        except Exception as e:
            print(f"Ошибка обработки сообщения: {e}")
            await message.nack(requeue=True)

@log
async def taxi_ride(
    order_id: int,
        ):
    '''Симуляция поездки'''
    async with db_pool.acquire() as conn:
        order = await conn.fetchrow('''
            SELECT * FROM order_taxi WHERE id=$1
        ''', order_id)
        if not order:
            logger.warning(f'Заказ {order_id} не найден или нет водителя')
            return None

    logger.info(f'Поездка по заказу {order_id} началась')

    start_time = datetime.now(timezone.utc)
    duration = 1
    await asyncio.sleep(duration)
    end_time = datetime.now(timezone.utc)

    async with db_pool.acquire() as conn:
        ride = await conn.fetchrow('''
            INSERT INTO rides (order_id, driver_id, user_id, started_at, finished_at)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, order_id, driver_id, duration
        ''', order_id, order['driver_id'], order['user_id'], start_time, end_time)

        logger.info(f'Поездка по заказу {order_id} завершена за {duration} сек')

        payload_json = json.dumps({
            'id': order['id'],
            'user_id': order['user_id'],
            'price': float(order['price']),
            'driver_id': order['driver_id']
        })

        event_id = str(uuid4())

        await conn.fetchrow('''
            INSERT INTO outbox (
            event_id, event_type, payload, published)
            VALUES ($1, $2, $3, $4)
        ''', event_id, 'ride.finished', payload_json, False)

        return dict(ride)
