import asyncio
from http import HTTPStatus
import json
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel
from contextlib import asynccontextmanager
from blaclist import BlacklistRedis
from redis.asyncio import Redis
from logging_log import logger, log
import asyncpg
from aio_pika.abc import AbstractIncomingMessage
from rabbitmq import (MAX_RETRIES,
                      connect_rabbitmq,
                      declare_dlx_exchange,
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

    return db_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_pool = await init_db()
    connection = await connect_rabbitmq()
    channel, exchange = await setup_channel(connection)

    app.state.redis = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    app.state.inflight = set()

    blaclist = BlacklistRedis(redis=app.state.redis)
    app.state.blaclist = blaclist

    app.state.channel = channel
    app.state.exchange = exchange
    app.state.connection = connection

    dlx_exchange = await declare_dlx_exchange(channel)
    await declare_retry_queue(channel, dlx_exchange)
    queue = await declare_queue(channel, exchange)

    app.state.exchange = exchange
    app.state.connection = connection
    app.state.db = db_pool

    consumer_tag = await queue.consume(handler_payment)
    app.state.consumer_tag = consumer_tag

    yield

    await queue.cancel(consumer_tag)

    if app.state.inflight:
        await asyncio.gather(*app.state.inflight, return_exceptions=True)

    await app.state.redis.aclose()
    await connection.close()
    await db_pool.close()

app = FastAPI(lifespan=lifespan)


class MoneySchema(BaseModel):
    money: float


async def get_pool(request: Request):
    return request.app.state.db


async def blaclist(request: Request):
    return request.app.state.blaclist


@app.post('/pay/{user_id}',
          status_code=HTTPStatus.OK)
async def top_up_your_card(
    payload: MoneySchema,
    user_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    blacklist: BlacklistRedis = Depends(blaclist)
        ):
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                money = payload.money
                card = await conn.fetchrow('''
                    SELECT * FROM taxi_card WHERE user_id = $1
                ''', user_id)

                if card:
                    await conn.execute('''
                        UPDATE taxi_card
                        SET balance = balance + $1
                        WHERE user_id = $2
                    ''', money, user_id)
                else:
                    await conn.execute('''
                        INSERT INTO taxi_card (user_id, balance)
                        VALUES ($1, $2)
                    ''', user_id, money)

                await blacklist.delete_user_blaclist(user_id)
                logger.info(f'Баланс пользователя {user_id} пополнен на {money}')
                return {"message": f"Баланс пополнен на {money}"}

    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(status_code=500, detail="Пользователь не найден")
    except asyncpg.CheckViolationError:
        raise HTTPException(status_code=500, detail="Некорректная сумма")
    except Exception:
        logger.exception("Неожиданная ошибка")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


async def handler_payment(message: AbstractIncomingMessage):
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
                await message.ack()
                return

            death_count = len(message.headers.get("x-death", []))
            if death_count >= MAX_RETRIES:
                await message.ack()
                return

            async with db_pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute('''
                            INSERT INTO processed_events (event_id)
                            VALUES ($1)
                        ''', event_id)
                    except asyncpg.exceptions.UniqueViolationError:
                        logger.info(f'Дубликат: событие {event_id} уже обработано')
                        await message.ack()
                        return
                    payment_order = await pay_to_taxi(conn=conn, order_id=order_id)
                    if not payment_order:
                        logger.warning('Недостаточно средств на карте')
                        logger.error(f'Поездка по заказу {order_id} не оплачена')
                        await message.ack()
                        return

                    logger.info(
                                'Поездка успешна оплачена'
                                    )
            await message.ack()
        except Exception as e:
            print(f"Ошибка обработки сообщения: {e}")
            await message.nack(requeue=False)


@log
async def pay_to_taxi(
    conn,
    order_id: int,
        ):
    '''Оплата поездки'''
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
        logger.info(f"Пользователь {order['user_id']} добавлен в черный список")
        await app.state.blaclist.set_user_blaclist(order['user_id'])
        return False

    if card['balance'] < order['price']:
        logger.warning('Недостаточно средств на карте')
        logger.info(f'Пользователь {order['user_id']} добавлен в черный список')
        await app.state.blaclist.set_user_blaclist(order['user_id'])
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

    await app.state.blaclist.delete_user_blaclist(order['user_id'])
    logger.info(f'Списано {order["price"]} с карты пользователя {order["user_id"]}')
    return True
