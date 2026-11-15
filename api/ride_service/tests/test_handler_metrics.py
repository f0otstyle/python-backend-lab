"""Проверка учёта метрик ride_service на учебных данных.

Postgres и RabbitMQ не нужны: соединение и сообщение подменяются фейками,
поездка живёт в памяти. Один успешно обработанный event driver.assigned
должен давать ровно +1 в ride_duration_seconds_count и +1 в
ride_finished_total.
"""
import json
import os
import sys
from contextlib import asynccontextmanager

import asyncpg
import pytest
from prometheus_client import REGISTRY

current_test_dir = os.path.dirname(os.path.abspath(__file__))
service_dir = os.path.dirname(current_test_dir)
api_root = os.path.dirname(service_dir)
if api_root not in sys.path:
    sys.path.insert(0, api_root)
if service_dir not in sys.path:
    sys.path.insert(0, service_dir)


def _drop_foreign_flat_modules():
    """Сбрасывает из sys.modules плоские модули чужих сервисов.

    Сервисы импортируют зависимости по плоским именам (from metrics import
    ...), поэтому в общем pytest-процессе имя metrics может быть уже занято
    metrics из payment_service — тогда ride_api получил бы чужой модуль и
    упал на ImportError. Оставляем модуль, только если он из ride_service.
    """
    ride_prefix = os.path.normcase(os.path.abspath(service_dir)) + os.sep
    for name in ('metrics', 'logging_log', 'rabbitmq'):
        module = sys.modules.get(name)
        module_file = getattr(module, '__file__', None)
        if module is None or module_file is None:
            continue
        if not os.path.normcase(os.path.abspath(module_file)).startswith(ride_prefix):
            del sys.modules[name]


_drop_foreign_flat_modules()

import ride_api
from ride_api import handler_order, app

# Учебные данные: один заказ в "базе"
ORDER = {'id': 42, 'user_id': 7, 'driver_id': 3, 'price': 300.0}

app.state.dlx_exchange = None  # на путях теста не используется


class FakeConn:
    """Имитация asyncpg-соединения на учебных данных в памяти."""

    def __init__(self, orders, seen_event_ids):
        self.orders = orders
        self.seen_event_ids = seen_event_ids
        self.inserted_rides = []
        self.outbox_events = []

    async def execute(self, query, *args):
        if 'INSERT INTO processed_events' in query:
            event_id = args[0]
            if event_id in self.seen_event_ids:
                raise asyncpg.exceptions.UniqueViolationError(
                    'duplicate key value violates unique constraint '
                    '"processed_events_pkey"')
            self.seen_event_ids.add(event_id)
        return 'INSERT 0 1'

    async def fetchrow(self, query, *args):
        if 'FROM order_taxi' in query:
            return self.orders.get(args[0])
        if 'INSERT INTO rides' in query:
            ride = {'id': len(self.inserted_rides) + 1,
                    'order_id': args[0],
                    'driver_id': args[1],
                    'duration': None}
            self.inserted_rides.append(ride)
            return ride
        if 'INSERT INTO outbox' in query:
            self.outbox_events.append(args)
            return None
        raise AssertionError(f'Неожиданный запрос в тесте: {query}')

    @asynccontextmanager
    async def transaction(self):
        yield


class FakePool:
    def __init__(self, conn):
        self._conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self._conn


class FakeMessage:
    """Имитация входящего сообщения driver.assigned."""

    def __init__(self, event_id, order_id):
        self.headers = {'event_id': event_id}
        self.body = json.dumps({'id': order_id}).encode()
        self.acked = False
        self.nacked = False

    @asynccontextmanager
    async def process(self, ignore_processed=False):
        yield

    async def ack(self):
        self.acked = True

    async def nack(self, requeue=False):
        self.nacked = True


def _snap():
    """Снимок показателей метрик ride_service."""
    return {
        'duration_count':
            REGISTRY.get_sample_value('ride_duration_seconds_count') or 0.0,
        'finished':
            REGISTRY.get_sample_value('ride_finished_total') or 0.0,
        'started':
            REGISTRY.get_sample_value('ride_started_total') or 0.0,
        'failed_rejection':
            REGISTRY.get_sample_value(
                'ride_failed_total', {'reason': 'business_rejection'}) or 0.0,
        'failed_duplicate':
            REGISTRY.get_sample_value(
                'ride_failed_total', {'reason': 'duplicate'}) or 0.0,
    }


def _deltas(before):
    after = _snap()
    return {key: after[key] - before[key] for key in before}


def _install_fake_db(orders, seen_event_ids):
    ride_api.db_pool = FakePool(FakeConn(orders, seen_event_ids))


@pytest.mark.asyncio
async def test_success_event_observed_once():
    """Успешный event: дельты duration_count и finished равны 1."""
    _install_fake_db(orders={ORDER['id']: ORDER}, seen_event_ids=set())
    message = FakeMessage('evt-success-1', ORDER['id'])

    before = _snap()
    await handler_order(message)
    deltas = _deltas(before)

    assert message.acked
    assert deltas['duration_count'] == 1, deltas
    assert deltas['finished'] == 1, deltas


@pytest.mark.asyncio
async def test_duplicate_event_observed_never():
    """Повторная доставка того же event_id ничего не учитывает заново."""
    _install_fake_db(
        orders={ORDER['id']: ORDER}, seen_event_ids={'evt-dup-1'})
    message = FakeMessage('evt-dup-1', ORDER['id'])

    before = _snap()
    await handler_order(message)
    deltas = _deltas(before)

    assert message.acked
    assert deltas['duration_count'] == 0, deltas
    assert deltas['finished'] == 0, deltas
    assert deltas['failed_duplicate'] == 1, deltas


@pytest.mark.asyncio
async def test_rejected_event_observed_once_as_failed():
    """Заказ не найден: одно наблюдение, finished не растёт."""
    _install_fake_db(orders={}, seen_event_ids=set())
    message = FakeMessage('evt-reject-1', ORDER['id'])

    before = _snap()
    await handler_order(message)
    deltas = _deltas(before)

    assert message.acked
    assert deltas['duration_count'] == 1, deltas
    assert deltas['finished'] == 0, deltas
    assert deltas['failed_rejection'] == 1, deltas
