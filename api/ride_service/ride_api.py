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
from rabbitmq import (MAX_RETRIES, connect_rabbitmq, declare_dlx_exchange,
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
REDIS_PORT = os.getenv('REDIS_PORT', 6379)

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

    await queue.consume(handler_order)

    yield

    await db_pool.close()
    await connection.close()

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

            dedep_key = f"dedep:order:{event_id}"
            ock_acquired = await app.state.redis.set(
                dedep_key, "1",
                nx=True,
                ex=3600
                )
            if not ock_acquired:
                logger.info('Дубликат')
                return
            death_count = len(message.headers.get("x-death", []))
            if death_count >= MAX_RETRIES:
                logger.warning(f"Заказ {order_id} отправлен в DLQ после {death_count} попыток.")
                await message.nack(requeue=False)
                return
            appoint = await taxi_to_appoint(order_id=order_id)
            if not appoint:
                logger.info(
                    f'Поездка не закончена по заказ {order_id}'
                )
                return
            drive = await taxi_ride(order_id)
            if not drive:
                logger.warning(
                    f'Заказ {order_id} создан без водителя'
                    )
                return
            pay = await pay_to_taxi(order_id)
            if not pay:
                logger.info(
                    f'Заказ {order_id}, оплата не прошла'
                    )
                return
            logger.info(
                f'Заказ {order_id}, успешно оплачен'
                )
            logger.info(f'Новый заказ сделан с ID {order_id}')
        except Exception as e:
            print(f"Ошибка обработки сообщения: {e}")
            await message.nack(requeue=True)


@log
async def taxi_to_appoint(
    order_id: int
        ):
    '''Назначаем водителя для поездки'''
    async with db_pool.acquire() as conn:
        driver = await conn.fetchrow('SELECT id FROM drivers ORDER BY random() LIMIT 1 FOR UPDATE SKIP LOCKED')
        if not driver:
            return None

    async with db_pool.acquire() as conn:
        result = await conn.fetchrow('''
            UPDATE order_taxi
            SET driver_id = $1
            WHERE id = $2 AND driver_id IS NULL
            RETURNING id, from_address, to_address, driver_id
        ''', driver["id"], order_id)

        if not result:
            return None

        return dict(result) if result else None


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

        return dict(ride)


@log
async def pay_to_taxi(
    order_id: int,
        ):
    '''Оплата поездки'''
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow('''
                SELECT * FROM order_taxi WHERE id=$1
            ''', order_id)
            if not order:
                logger.warning(f'Заказ {order_id} не найден или нет водителя')
                return None

            card = await conn.fetchrow('''
                SELECT balance FROM taxi_card WHERE user_id = $1 FOR UPDATE
            ''', order['user_id'])

            if not card:
                logger.warning(f'У пользователя {order["user_id"]} нет карты')
                return False

            if card['balance'] < order['price']:
                logger.warning('Недостаточно средств на карте')
                return False

            await conn.execute('''
                UPDATE taxi_card
                SET balance = balance - $1
                WHERE user_id = $2
            ''', order['price'], order['user_id'])

            await conn.execute('''
                UPDATE drivers
                SET money = money + $1
                WHERE id = $2
                ''', order['price'], order['driver_id'])

            logger.info(f'Списано {order["price"]} с карты пользователя {order["user_id"]}')
        return True
