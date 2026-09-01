from datetime import datetime, timezone
import random
from fastapi import FastAPI, HTTPException, Request, Header, Depends, Response
from http import HTTPStatus
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
# from models import db_pool
from error_handler import OrderError, SearchError
from logging_log import logger, log
from authx import AuthXConfig, AuthX
import asyncio
import asyncpg
import bcrypt
import os


DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_USER = os.getenv('POSTGRES_USER', 'pgAdmin')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')
DB_NAME = os.getenv('POSTGRES_DB', 'taxi_db')

TIME = 5

app = FastAPI()

db_pool = None

config = AuthXConfig(
    JWT_SECRET_KEY='SECRET-KEY',
    JWT_TOKEN_LOCATION=['cookies'],
    JWT_ACCESS_COOKIE_NAME='my_cookie',
    JWT_COOKIE_CSRF_PROTECT=False,
    )


security: AuthX = AuthX(config=config)


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
            CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            password VARCHAR NOT NULL
        )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS drivers (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            car VARCHAR NOT NULL,
            money NUMERIC NOT NULL DEFAULT 0 CHECK (money >= 0)
        )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS order_taxi (
            id SERIAL PRIMARY KEY,
            idempotency_key VARCHAR NOT NULL UNIQUE,
            from_address VARCHAR,
            to_address VARCHAR NOT NULL,
            price NUMERIC NOT NULL CHECK (price > 0),
            created_at TIMESTAMP DEFAULT NOW(),
            driver_id INTEGER REFERENCES drivers(id),
            user_id INTEGER REFERENCES users(id)
        )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rides (
            id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES order_taxi(id),
            driver_id INTEGER REFERENCES drivers(id),
            user_id INTEGER REFERENCES users(id),
            started_at TIMESTAMP DEFAULT NOW(),
            finished_at TIMESTAMP,
            duration INTEGER
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS taxi_card (
            user_id INTEGER REFERENCES users(id),
            balance NUMERIC NOT NULL CHECK (balance >= 0) DEFAULT 0
            )
        """)
    return db_pool


class OrderCreate(BaseModel):
    from_address: str
    to_address: str
    price: float


class UserRegisterSchema(BaseModel):
    username: str
    password: str


class DriverCreate(BaseModel):
    name: str
    car: str


class MoneySchema(BaseModel):
    money: float


@app.exception_handler(OrderError)
async def order_error(request: Request, exc: OrderError):
    return JSONResponse(
        status_code=HTTPStatus.CONFLICT,
        content={
            "error": True,
            "type": "OrderError",
            'detail': exc.detail
        })


@app.exception_handler(SearchError)
async def search_error(request: Request, exc: SearchError):
    return JSONResponse(
        status_code=HTTPStatus.NOT_FOUND,
        content={
            "error": True,
            "type": "SearchError",
            'detail': exc.detail
        })


async def get_pool():
    global db_pool
    db_pool = await init_db()
    if db_pool is None:
        raise RuntimeError('База данных не инициализирована')
    return db_pool


@app.post('/registrate', status_code=HTTPStatus.CREATED)
async def registrate(
    user: UserRegisterSchema,
    pool: asyncpg.Pool = Depends(get_pool)
        ):
    username = user.username
    async with pool.acquire() as conn:
        existing = await conn.fetchrow('''
            SELECT *
            FROM users
            WHERE name = $1
        ''', username)
        if existing:
            logger.error('Пользователь уже существует')
            raise HTTPException(
                status_code=400,
                detail='Пользователь уже существует'
                )
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), salt).decode('utf-8')
        logger.info('Пароль захеширован')

        new_order = await conn.fetchrow('''
            INSERT INTO users (name, password)
            VALUES ($1, $2)
            RETURNING id, name, password
            ''', username, hashed_password)
        logger.info(f'Пользователь создан {new_order}')
        return {"message": "Пользователь создан"}


@app.post('/login', status_code=HTTPStatus.OK)
async def login(
    response: Response,
    user: UserRegisterSchema,
    pool: asyncpg.Pool = Depends(get_pool)
        ):
    username = user.username
    async with pool.acquire() as conn:
        existing = await conn.fetchrow('''
            SELECT *
            FROM users
            WHERE name = $1
        ''', username)
        if not existing:
            logger.error('Пользователь не существует')
            raise HTTPException(
                status_code=401,
                detail='Пользователь не найден. Зарегистрируйтесь'
                )

        if not bcrypt.checkpw(
            user.password.encode('utf-8'),
            existing['password'].encode('utf-8')
        ):
            logger.error('Не верный пароль')
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail='Неверный пароль'
            )
        token = security.create_access_token(uid=str(existing['id']))
        logger.info('Токен выдан')
        response.set_cookie(
                key=config.JWT_ACCESS_COOKIE_NAME,
                value=token,
                # httponly=True,
                )
        logger.info('Успешный вход')
        return {"message": "Успешный вход"}


@app.get('/users/me',
         status_code=HTTPStatus.OK,
         dependencies=[Depends(security.access_token_required)]
         )
async def users_me():
    logger.info('Вы авторизованы')
    return {'data': 'Вы авторизованы'}


@app.post('/logout', status_code=HTTPStatus.OK)
async def logout(response: Response):
    response.delete_cookie("my_cookie")
    logger.info('Вы вышли из системы')
    return {"message": "Вы вышли из системы"}


@app.post('/drivers', status_code=HTTPStatus.CREATED)
@log
async def create_driver(
    driver: DriverCreate,
    pool: asyncpg.Pool = Depends(get_pool)
):
    driver_name = driver.name
    driver_car = driver.car
    '''Добавляем нового водителя'''
    async with pool.acquire() as conn:
        new_driver = await conn.fetchrow('''
            INSERT INTO drivers (name, car)
            VALUES ($1, $2)
            RETURNING id, name, car
        ''', driver_name, driver_car)

        logger.info(f'Водитель создан: {new_driver["name"]}')
        return dict(new_driver)


@app.get('/taxi', status_code=HTTPStatus.OK)
@log
async def list_of_orders(pool: asyncpg.Pool = Depends(get_pool)):
    '''Список всех заказов'''
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM order_taxi"""
            )
            if rows:
                return [dict(row) for row in rows]
            logger.error('База данных пуста')
            return []
    except asyncpg.PostgresError:
        logger.exception('Ошибка не подключения к бд')
        raise HTTPException(status_code=500, detail="Ошибка базы данных")


@app.post('/taxi',
          status_code=HTTPStatus.CREATED,
          dependencies=[Depends(security.access_token_required)])
@log
async def ordering_a_taxi(
    orders: OrderCreate,
    request: Request,
    pool: asyncpg.Pool = Depends(get_pool),
    idempotency_key: str = Header(None, alias="Idempotency-Key")
        ):
    '''Создаем заказ'''
    from_address = orders.from_address
    to_address = orders.to_address
    price = orders.price

    if not idempotency_key:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Поле 'idempotency_key' обязательно"
        )
    current_time = datetime.now(timezone.utc).timestamp()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow('''
            SELECT * FROM order_taxi WHERE idempotency_key=$1
        ''', idempotency_key)

        if existing:
            logger.info(f"Повторный запрос с ключом {idempotency_key}")
            return JSONResponse(
                status_code=HTTPStatus.CREATED,
                content=jsonable_encoder(dict(existing)),
                headers={"Location": f"/taxi/{existing['id']}"}
            )

        duplicate = await conn.fetchrow('''
            SELECT * FROM order_taxi WHERE to_address=$1
        ''', to_address)

        if duplicate:
            created_at = duplicate['created_at'].timestamp()
            time_diff = current_time - created_at
            if time_diff < TIME:
                logger.warning(
                    f'Попытка создать дубликат заказа для {to_address} (прошло {time_diff:.1f} с)'
                    )
                raise OrderError()
            else:
                logger.info('Можно сделать новый заказ')

        new_order = await conn.fetchrow('''
            INSERT INTO order_taxi (
            idempotency_key, from_address, to_address, price
            )
            VALUES ($1, $2, $3, $4)
            RETURNING id, idempotency_key, from_address, to_address, price,
            created_at''', idempotency_key, from_address, to_address, price)

        appoint = await taxi_to_appoint(new_order['id'], pool)

        if appoint:
            logger.info(f'Водитель назначен на заказ {new_order["id"]}')
            drive = await taxi_ride(new_order['id'], pool)
            if drive:
                pay = await pay_to_taxi(new_order['id'], pool)
                logger.info(
                    f'Заказ {new_order["id"]} закончен, оплата'
                    )
                if pay:
                    logger.info(f'Заказ {new_order["id"]}, успешно оплачен')
                else:
                    logger.info(
                        f'Заказ {new_order["id"]}, оплата не прошла'
                        )
            else:
                logger.info(f'Поездка не закончена по заказ {new_order["id"]}')
        else:
            logger.warning(f'Заказ {new_order["id"]} создан без водителя')

        logger.info(f'Новый заказ сделан с ID {new_order["id"]}')
        return JSONResponse(
                status_code=HTTPStatus.CREATED,
                content=jsonable_encoder(dict(new_order)),
                headers={"Location": f"/taxi/{new_order['id']}"}
            )


@log
async def taxi_to_appoint(
    order_id: int,
    pool: asyncpg.Pool,
        ):
    '''Назначаем водителя для поездки'''
    async with pool.acquire() as conn:
        count = await conn.fetchrow('SELECT COUNT(*) FROM drivers')
        count_row = count['count']
        id_drive = random.randint(1, count_row)
        driver = await conn.fetchrow('''
            SELECT id
            FROM drivers
            WHERE id = $1
        ''', id_drive)
        if not driver:
            driver = await conn.fetchrow('''
                SELECT id FROM drivers LIMIT 1
            ''')

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
    pool: asyncpg.Pool,
        ):
    '''Симуляция поездки'''
    async with pool.acquire() as conn:
        order = await conn.fetchrow('''
            SELECT * FROM order_taxi WHERE id=$1
        ''', order_id)

        if not order:
            logger.warning(f'Заказ {order_id} не найден или нет водителя')
            return None

        logger.info(f'Поездка по заказу {order_id} началась')

        duration = random.randint(2, 5)
        await asyncio.sleep(duration)

        ride = await conn.fetchrow('''
            INSERT INTO rides (order_id, driver_id, user_id, duration, finished_at)
            VALUES ($1, $2, $3, $4, NOW())
            RETURNING id, order_id, driver_id, duration
        ''', order_id, order['driver_id'], order['user_id'], duration)

        logger.info(f'Поездка по заказу {order_id} завершена за {duration} сек')

        return dict(ride)


@log
async def pay_to_taxi(
    order_id: int,
    pool: asyncpg.Pool,
        ):
    '''Оплата поездки'''
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow('''
                SELECT * FROM order_taxi WHERE id=$1
            ''', order_id)
            if not order:
                logger.warning(f'Заказ {order_id} не найден или нет водителя')
                return None

            card = await conn.fetchrow('''
                SELECT balance FROM taxi_card WHERE user_id = $1
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


@app.post('/pay/{user_id}', status_code=HTTPStatus.OK)
async def top_up_your_card(
    payload: MoneySchema,
    user_id: int,
    pool: asyncpg.Pool = Depends(get_pool)
        ):
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

            logger.info(f'Баланс пользователя {user_id} пополнен на {money}')
            return {"message": f"Баланс пополнен на {money}"}


@app.get('/taxi/{order_id}',
         status_code=HTTPStatus.OK
         )
@log
async def order_search(
    order_id: int,
    pool: asyncpg.Pool = Depends(get_pool)
        ):
    '''Поиск конкретного заказа'''
    async with pool.acquire() as conn:
        existing = await conn.fetchrow('''
            SELECT * FROM order_taxi WHERE id=$1
        ''', order_id)
        if existing:
            logger.info(f'Заказ по {existing.get(id)} найден')
            return JSONResponse(
                        status_code=HTTPStatus.OK,
                        content=jsonable_encoder(dict(existing)),
                        headers={"Location": f"/taxi/{existing['id']}"}
                    )
    logger.warning(f'Попытка найти несуществующий заказ {order_id}')
    raise SearchError()


@app.delete('/taxi/{order_id}',
            status_code=HTTPStatus.NO_CONTENT)
@log
async def order_delete(
    order_id: int,
    pool: asyncpg.Pool = Depends(get_pool)
        ):
    '''Удаление заказа'''
    async with pool.acquire() as conn:
        existing = await conn.fetchrow('''
            DELETE FROM order_taxi WHERE id=$1
            RETURNING id, idempotency_key, to_address, created_at
        ''', order_id)
        if existing:
            logger.info(f'Заказ по номеру {existing["id"]} удален')
            return

    logger.warning(f'Попытка удалить несуществующий заказ {order_id}')
    raise SearchError()


@app.get('/history/',
         status_code=HTTPStatus.OK,
         dependencies=[Depends(security.access_token_required)])
@log
async def history_order_taxi(
    pool: asyncpg.Pool = Depends(get_pool)
        ):
    async with pool.acquire() as conn:
        histoty = await conn.fetch('''
            SELECT *
            FROM order_taxi
            ORDER BY created_at DESC
            ''')
        return [dict(row) for row in histoty]
