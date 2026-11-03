import os
import sys
import pytest
import asyncio
import asyncpg
from uuid import uuid4

current_test_dir = os.path.dirname(os.path.abspath(__file__))
api_root = os.path.dirname(os.path.dirname(current_test_dir))
service_dir = os.path.join(api_root, 'payment_service')
if api_root not in sys.path:
    sys.path.insert(0, api_root)
if service_dir not in sys.path:
    sys.path.insert(0, service_dir)


from payment_service.main import app, pay_to_taxi
from payment_service.blaclist import BlacklistRedis
from redis.asyncio import Redis


DB_CONFIG = {
    "host": 'localhost',
    "port": 5432,
    "user": 'pgAdmin',
    "password": 'postgres',
    "database": 'taxi_test_db'
}

REDIS_CONFIG = {
    "host": 'localhost',
    "port": 6379,
    "db": 2,
    "decode_responses": True
}


TEST_DB_DSN = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
TEST_REDIS_URL = f"redis://{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}/{REDIS_CONFIG['db']}"


@pytest.fixture(scope="function")
async def test_db_pool():
    """Фикстура: изолированный пул соединений к тестовой БД"""
    pool = await asyncpg.create_pool(TEST_DB_DSN, min_size=1, max_size=10)

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name VARCHAR UNIQUE,
        password VARCHAR
        )
        """)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
        id SERIAL PRIMARY KEY,
        name VARCHAR,
        car VARCHAR,
        money NUMERIC DEFAULT 0
        )""")
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS order_taxi (
        id SERIAL PRIMARY KEY,
        idempotency_key VARCHAR NOT NULL,
        from_address VARCHAR,
        to_address VARCHAR NOT NULL,
        price NUMERIC NOT NULL CHECK (price > 0),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        driver_id INTEGER REFERENCES drivers(id),
        user_id INTEGER REFERENCES users(id),
        UNIQUE (user_id, idempotency_key)
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS taxi_card (
        user_id INT PRIMARY KEY,
        balance NUMERIC DEFAULT 0
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL UNIQUE REFERENCES order_taxi(id),
        user_id INTEGER NOT NULL,
        amount NUMERIC NOT NULL,
        event_id VARCHAR NOT NULL,
        paid_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS processed_events (
        event_id VARCHAR PRIMARY KEY,
        processed_at timestamptz DEFAULT NOW()
        )""")

        await conn.execute("""
            TRUNCATE TABLE payments, processed_events, taxi_card, order_taxi, drivers, users
            RESTART IDENTITY CASCADE
        """)

    yield pool
    await pool.close()


@pytest.fixture(scope="function")
async def test_redis_and_blacklist():
    """Фикстура: изолированный Redis и настройка app.state.blaclist"""
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()

    app.state.blaclist = BlacklistRedis(redis=redis)

    yield app.state.blaclist

    await redis.flushdb()
    await redis.aclose()


@pytest.mark.parametrize("run_id", [1, 2, 3])
@pytest.mark.asyncio
async def test_concurrent_payment_race_condition(
    test_db_pool,
    test_redis_and_blacklist,
    run_id
    ):
    """
    Тест доказывает, что при реальной гонке двух транзакций:
    1. Только одна оплата проходит успешно.
    2. Вторая получает конфликт уникальности и откатывается.
    3. Итоговое состояние БД строго соответствует одному списанию.
    """
    base_id = run_id * 1000
    user_id = base_id + 1
    driver_id = base_id + 2
    order_id = base_id + 3

    async with test_db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("INSERT INTO users (id, name, password) VALUES ($1, 'test_user', 'hash')", user_id)
            await conn.execute("INSERT INTO drivers (id, name,  car, money) VALUES ($1, 'test_driver', 'test_car', 0)", driver_id)
            await conn.execute("INSERT INTO taxi_card (user_id, balance) VALUES ($1, 650)", user_id)
            await conn.execute("""
                INSERT INTO order_taxi (id, user_id, driver_id, price, idempotency_key, from_address, to_address) 
                VALUES ($1, $2, $3, 300, $4, $5, $6)
            """, order_id, user_id, driver_id, f'test-imp-key-{run_id}', 'Ватутино 19', 'Ленина 22')

    async with test_db_pool.acquire() as conn:
        user_balance = await conn.fetchval('''
        SELECT balance
        FROM taxi_card
        WHERE user_id = $1
        ''', user_id)
        driver_balance = await conn.fetchval('''
        SELECT money
        FROM drivers
        WHERE id = $1
        ''', driver_id)
        payment_count = await conn.fetchval('''
        SELECT count(*)
        FROM payments
        WHERE user_id = $1
        ''', user_id)

        assert user_balance == 650
        assert driver_balance == 0
        assert payment_count == 0

    event_id_1 = str(uuid4())
    event_id_2 = str(uuid4())
    barrier = asyncio.Barrier(2)

    async def payment_worker(worker_id: int, event_id: str):
        async with test_db_pool.acquire() as conn:
            try:
                async with conn.transaction():
                    existing = await conn.fetchval("SELECT 1 FROM payments WHERE order_id = $1", order_id)
                    assert existing is None

                    await barrier.wait()

                    result = await pay_to_taxi(
                        conn=conn,
                        event_id=event_id,
                        order_id=order_id
                        )
                    if not result:
                        return "CONFLICT"

                    return "SUCCESS"

            except asyncpg.exceptions.UniqueViolationError:
                return "CONFLICT"
            except Exception as exc:
                return f"ERROR: {exc}"

    results = await asyncio.gather(
        payment_worker(1, event_id_1),
        payment_worker(2, event_id_2)
    )

    assert results.count("SUCCESS") == 1
    assert results.count("CONFLICT") == 1

    async with test_db_pool.acquire() as conn:
        user_balance = await conn.fetchval('''
                SELECT balance
                FROM taxi_card
                WHERE user_id = $1
                ''', user_id)
        driver_balance = await conn.fetchval('''
                SELECT money
                FROM drivers
                WHERE id = $1
                ''', driver_id)
        payment_count = await conn.fetchval('''
                SELECT count(*)
                FROM payments
                WHERE user_id = $1
                ''', user_id)

        assert user_balance == 350
        assert driver_balance == 300
        assert payment_count == 1
