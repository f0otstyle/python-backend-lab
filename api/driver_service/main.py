import asyncio
from http import HTTPStatus
import json
from uuid import uuid4
from pydantic import BaseModel
from fastapi import Depends, FastAPI, HTTPException, Request
from contextlib import asynccontextmanager
import asyncpg
import os

from redis.asyncio import Redis
from rabbitmq import (MAX_RETRIES,
                      connect_rabbitmq,
                      declare_dlx_exchange,
                      declare_dlx_queue,
                      setup_channel,
                      declare_queue,
                      declare_retry_queue
                      )
from aio_pika.abc import AbstractIncomingMessage
from logging_log import log, logger


DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_USER = os.getenv('POSTGRES_USER', 'pgAdmin')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')
DB_NAME = os.getenv('POSTGRES_DB', 'taxi_db')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis_api')
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

    return db_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_pool = await init_db()

    connection = await connect_rabbitmq()
    channel, exchange = await setup_channel(connection)

    app.state.redis = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    app.state.inflight = set()

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

    consumer_tag = await queue.consume(handler_driver)
    app.state.consumer_tag = consumer_tag

    yield

    await queue.cancel(consumer_tag)

    if app.state.inflight:
        await asyncio.gather(*app.state.inflight, return_exceptions=True)

    await app.state.redis.aclose()
    await connection.close()
    await db_pool.close()

app = FastAPI(lifespan=lifespan)


class DriverCreate(BaseModel):
    name: str
    car: str


async def get_pool(request: Request):
    return request.app.state.db


@app.post('/drivers', status_code=HTTPStatus.CREATED)
@log
async def create_driver(
    driver: DriverCreate,
    pool: asyncpg.Pool = Depends(get_pool)
        ):
    '''Добавляем нового водителя'''
    driver_name = driver.name
    driver_car = driver.car
    try:
        async with pool.acquire() as conn:
            new_driver = await conn.fetchrow('''
                INSERT INTO drivers (name, car)
                VALUES ($1, $2)
                RETURNING id, name, car
            ''', driver_name, driver_car)

            logger.info(f'Водитель создан: {new_driver["name"]}')
            return dict(new_driver)
    except asyncpg.PostgresError:
        logger.exception('Ошибка не подключения к бд')
        raise HTTPException(status_code=500, detail="Ошибка базы данных")


async def handler_driver(message: AbstractIncomingMessage):
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

                    appoint = await taxi_to_appoint(conn=conn, order_id=order_id)
                    if not appoint:
                        logger.info(
                            f'Водитель не назначен по заказу {order_id}'
                        )
                        await message.nack(requeue=True)
                        return

                    logger.info(
                                'Водитель для поездки назначен'
                                    )
        except Exception as e:
            print(f"Ошибка обработки сообщения: {e}")
            await message.nack(requeue=True)


@log
async def taxi_to_appoint(
    conn,
    order_id: int
        ):
    '''Назначаем водителя для поездки'''
    current_order = await conn.fetchrow('''
        SELECT id, driver_id
        FROM order_taxi
        WHERE id = $1''', order_id)

    if not current_order:
        logger.warning(f" Заказ {order_id} не найден в БД!")
        return None

    logger.info(f'Заказ {order_id} успешно найден в бд')

    driver = await conn.fetchrow('''
        SELECT id
        FROM drivers
        ORDER BY random()
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    ''')
    if not driver:
        logger.info('Водителей в базе данных нету')
        return None

    result = await conn.fetchrow('''
        UPDATE order_taxi
        SET driver_id = $1
        WHERE id = $2
        RETURNING id, from_address, to_address, driver_id, user_id, price, idempotency_key
        ''', driver["id"], order_id)

    if not result:
        logger.warning(f'Не удалось обновить заказ {order_id}')
        return None

    payload_json = json.dumps({
        'id': result['id'],
        'idempotency_key': result['idempotency_key'],
        'from_address': result['from_address'],
        'to_address': result['to_address'],
        'price': float(result['price']),
        'driver_id': result['driver_id'],
        'user_id': result['user_id']
        })

    event_id = str(uuid4())

    await conn.fetchrow('''
        INSERT INTO outbox (
        event_id, event_type, payload, published)
        VALUES ($1, $2, $3, $4)
    ''', event_id, 'driver.assigned', payload_json, False)

    return dict(result) if result else None
