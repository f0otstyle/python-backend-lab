import os
import sys
import time
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

# Таймаут ожидания на барьере (сек), общий для обоих тестов: если одна
# из задач не дойдёт до барьера (упала раньше), вторая не будет ждать
# вечно — по таймауту барьер разрывается и все waiter'ы получают
# BrokenBarrierError.
BARRIER_TIMEOUT = 5.0


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


# ---------- общие помощники ----------


async def prepare_race_data(test_db_pool, run_id):
    """Создаёт пользователя, водителя, карту и заказ для гонки оплат.

    Возвращает (user_id, driver_id, order_id).
    """
    base_id = run_id * 1000
    user_id = base_id + 1
    driver_id = base_id + 2
    order_id = base_id + 3

    async with test_db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("INSERT INTO users (id, name, password) VALUES ($1, 'test_user', 'hash')", user_id)
            await conn.execute("INSERT INTO drivers (id, name, car, money) VALUES ($1, 'test_driver', 'test_car', 0)", driver_id)
            await conn.execute("INSERT INTO taxi_card (user_id, balance) VALUES ($1, 650)", user_id)
            await conn.execute("""
                INSERT INTO order_taxi (id, user_id, driver_id, price, idempotency_key, from_address, to_address)
                VALUES ($1, $2, $3, 300, $4, $5, $6)
            """, order_id, user_id, driver_id, f'test-imp-key-{run_id}', 'Ватутино 19', 'Ленина 22')

    return user_id, driver_id, order_id


async def assert_no_payments_yet(test_db_pool, user_id, driver_id):
    """Предусловие до старта гонки: балансы 650/0, оплат нет."""
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


async def assert_single_write_off(test_db_pool, user_id, driver_id):
    """Итог гонки: ровно одно списание — карта 350, водитель 300, одна запись в payments."""
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


def mark_event(timeline, worker_id, event_id, phase):
    """Фиксирует момент события задачи в общем таймлайне гонки."""
    timeline.append({
        'worker': worker_id,
        'event_id': event_id,
        'phase': phase,
        't': time.perf_counter()
    })


def print_timeline(timeline, title):
    """Печатает таймлайн обеих задач с event_id и моментами чтения/завершения."""
    if not timeline:
        return
    t0 = min(e['t'] for e in timeline)
    lines = [f'--- Таймлайн: {title} ---']
    for e in sorted(timeline, key=lambda item: item['t']):
        lines.append(
            f"+{e['t'] - t0:9.6f}s worker={e['worker']} "
            f"event_id={e['event_id'][:8]} {e['phase']}"
        )
    print('\n'.join(lines))


async def wait_at_barrier(barrier, timeout):
    """Ждёт вторую задачу на барьере, ограничивая ожидание таймаутом.

    asyncio.Barrier в этой версии Python не умеет в таймаут, поэтому
    wait() завёрнут в wait_for: если вторая задача не дойдёт до барьера
    (упала раньше), первая выходит по TimeoutError, барьер разрывается
    (abort), и ни одна из задач не остаётся ждать бесконечно.
    """
    try:
        await asyncio.wait_for(barrier.wait(), timeout=timeout)
    except BaseException:
        await barrier.abort()
        raise


@pytest.mark.parametrize("run_id", [1, 2, 3])
@pytest.mark.asyncio
async def test_concurrent_payment_race_condition(
    test_db_pool,
    test_redis_and_blacklist,
    run_id
    ):
    """
    Принудительная гонка двух транзакций: барьер стоит ВНУТРИ pay_to_taxi —
    обе задачи синхронизируются строго после реального внутреннего чтения
    отсутствующего платежа и до FOR UPDATE карты (шов on_payment_missing).

    При таком месте ожидания обе задачи гарантированно видят пустой payments
    до того, как любая из них успела вставить запись, поэтому исход
    детерминирован: ровно один SUCCESS и один CONFLICT по UNIQUE
    payments_order_id_key, с откатом второй транзакции.

    Дополнительно проверяется по таймлайну, что оба чтения платежа
    завершились раньше любого завершения оплаты/конфликта.
    """
    user_id, driver_id, order_id = await prepare_race_data(test_db_pool, run_id)
    await assert_no_payments_yet(test_db_pool, user_id, driver_id)

    event_id_1 = str(uuid4())
    event_id_2 = str(uuid4())
    barrier = asyncio.Barrier(2)
    timeline = []

    async def payment_worker(worker_id: int, event_id: str):
        async with test_db_pool.acquire() as conn:
            try:
                async with conn.transaction():

                    async def on_payment_missing():
                        # pay_to_taxi уже реально прочла payments — платежа нет;
                        # встречаемся с второй задачей до FOR UPDATE карты
                        mark_event(timeline, worker_id, event_id, 'payments_read_missing')
                        await wait_at_barrier(barrier, BARRIER_TIMEOUT)
                        mark_event(timeline, worker_id, event_id, 'rendezvous_passed')

                    result = await pay_to_taxi(
                        conn=conn,
                        event_id=event_id,
                        order_id=order_id,
                        on_payment_missing=on_payment_missing
                        )
                    phase = 'payment_done' if result is True else f'returned_{result}'
                    mark_event(timeline, worker_id, event_id, phase)

                mark_event(timeline, worker_id, event_id, 'tx_committed')
                if result is True:
                    return "SUCCESS"
                if result == 'ready':
                    return "ALREADY_PAID"
                return f"REFUSED: {result!r}"

            except asyncpg.exceptions.UniqueViolationError as exc:
                mark_event(timeline, worker_id, event_id, 'unique_violation')
                if 'payments_order_id_key' in str(exc):
                    return "CONFLICT"
                return f"WRONG_CONSTRAINT: {str(exc)}"
            except Exception as exc:
                mark_event(timeline, worker_id, event_id, 'error')
                return f"ERROR: {exc}"

    results = await asyncio.gather(
        payment_worker(1, event_id_1),
        payment_worker(2, event_id_2)
    )

    print_timeline(timeline, f'принудительная гонка run_id={run_id}')

    # Ровно один SUCCESS и один CONFLICT — гонка воспроизведена принудительно
    assert results.count("SUCCESS") == 1, f"результаты: {results}"
    assert results.count("CONFLICT") == 1, f"результаты: {results}"

    # Пересечение видно по логам: оба чтения отсутствующего платежа
    # завершились раньше, чем любая задача завершила оплату или конфликт
    read_times = [e['t'] for e in timeline if e['phase'] == 'payments_read_missing']
    done_times = [e['t'] for e in timeline if e['phase'] in ('payment_done', 'unique_violation')]
    assert len(read_times) == 2, f"чтений платежа в таймлайне: {len(read_times)}"
    assert len(done_times) == 2, f"завершений оплаты в таймлайне: {len(done_times)}"
    assert max(read_times) < min(done_times), (
        'чтение отсутствующего платежа одной задачи случилось после '
        'завершения оплаты другой — барьер не сработал в нужной точке'
    )

    # Итоговое состояние БД строго соответствует одному списанию
    await assert_single_write_off(test_db_pool, user_id, driver_id)


@pytest.mark.parametrize("run_id", [1, 2, 3])
@pytest.mark.asyncio
async def test_concurrent_payment_joint_start(
    test_db_pool,
    test_redis_and_blacklist,
    run_id
    ):
    """
    Совместный старт: барьер стоит до входа в pay_to_taxi (прежнее место) —
    обе задачи гарантированно получили соединение и дошли до общей точки
    перед стартом оплаты. Ожидание ограничено таймаутом: если одна задача
    упала до барьера, барьер разрывается и вторая не ждёт бесконечно.

    Здесь гонка не принудительная — после отпускания барьера одна задача
    может полностью завершить оплату до внутреннего чтения платежа другой,
    поэтому корректны оба исхода: SUCCESS + CONFLICT и SUCCESS + ALREADY_PAID.

    Проверяется главный инвариант идемпотентности: ровно одно списание.
    Этот сценарий не заменяет отдельную проверку принудительной гонки выше.
    """
    user_id, driver_id, order_id = await prepare_race_data(test_db_pool, run_id)
    await assert_no_payments_yet(test_db_pool, user_id, driver_id)

    event_id_1 = str(uuid4())
    event_id_2 = str(uuid4())
    barrier = asyncio.Barrier(2)
    timeline = []

    async def payment_worker(worker_id: int, event_id: str):
        async with test_db_pool.acquire() as conn:
            try:
                async with conn.transaction():

                    async def on_payment_missing():
                        # только фиксируем момент реального чтения платежа,
                        # никого не ждём — гонка естественная, не принудительная
                        mark_event(timeline, worker_id, event_id, 'payments_read_missing')

                    # совместный старт: обе задачи получили соединение, открыли
                    # транзакцию и встречаются перед входом в pay_to_taxi
                    await wait_at_barrier(barrier, BARRIER_TIMEOUT)
                    mark_event(timeline, worker_id, event_id, 'before_pay_to_taxi')
                    result = await pay_to_taxi(
                        conn=conn,
                        event_id=event_id,
                        order_id=order_id,
                        on_payment_missing=on_payment_missing
                        )
                    phase = 'payment_done' if result is True else f'returned_{result}'
                    mark_event(timeline, worker_id, event_id, phase)

                mark_event(timeline, worker_id, event_id, 'tx_committed')
                if result is True:
                    return "SUCCESS"
                if result == 'ready':
                    return "ALREADY_PAID"
                return f"REFUSED: {result!r}"

            except asyncpg.exceptions.UniqueViolationError as exc:
                mark_event(timeline, worker_id, event_id, 'unique_violation')
                if 'payments_order_id_key' in str(exc):
                    return "CONFLICT"
                return f"WRONG_CONSTRAINT: {str(exc)}"
            except Exception as exc:
                mark_event(timeline, worker_id, event_id, 'error')
                return f"ERROR: {exc}"

    results = await asyncio.gather(
        payment_worker(1, event_id_1),
        payment_worker(2, event_id_2)
    )

    print_timeline(timeline, f'совместный старт run_id={run_id}')

    # Ровно одна оплата; вторая — либо конфликт UNIQUE, либо корректное 'ready'
    assert results.count("SUCCESS") == 1, f"результаты: {results}"
    assert results.count("CONFLICT") + results.count("ALREADY_PAID") == 1, (
        f"неожиданные результаты: {results}"
    )

    # Главное: состояние БД строго соответствует одному списанию
    await assert_single_write_off(test_db_pool, user_id, driver_id)
