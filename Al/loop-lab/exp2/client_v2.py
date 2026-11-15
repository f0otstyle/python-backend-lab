"""Клиент-экспериментатор для server_v2: идемпотентность заказов.

1. Запусти сервер (из папки exp2):
       python -m uvicorn server_v2:app --port 8001
2. Запусти клиент:  python client_v2.py
3. Смотри ОДНОВРЕМЕННО в консоль сервера: там видно, какой запрос создал
   заказ, какой вернул снимок (повтор), а какой словил 409.

Четыре сценария:
- ретраи подряд: тот же ключ + то же тело -> снимок (200 ПОВТОР),
  тот же ключ + другое тело -> 409;
- удалить запись и повторить POST с тем же ключом -> придёт снимок
  уже удалённого заказа (каверза: у снимков нет TTL, как и в жизни);
- гонка: 5 одинаковых POST с одним ключом одновременно -> один заказ,
  остальные ответы - повторы;
- разные ключи параллельно -> не ждут друг друга (3 заказа за ~1 c, не за 3).

Ключи генерируются заново на каждый запуск, поэтому клиент можно
перезапускать сколько угодно: старые снимки не помешают.

Адрес сервера можно переопределить переменной окружения LAB_URL:
LAB_URL=http://localhost:8012 python client_v2.py
"""
import asyncio
import os
import time
import uuid

import aiohttp

BASE_URL = os.environ.get('LAB_URL', 'http://localhost:8000')
COUNT = 5          # сколько одинаковых POST в сценарии гонки
PARALLEL_KEYS = 3  # сколько разных ключей одновременно в сценарии 4
TIMEOUT = 60
CUSTOMER = 'Аня'
AMOUNT = 1500.0

# свежие ключи на каждый запуск: ретраи внутри запуска имеют один ключ,
# а разные запуски клиента не мешают друг другу
KEY_MAIN = f'idem-v2-{uuid.uuid4().hex[:6]}'
KEY_RACE = f'idem-v2-race-{uuid.uuid4().hex[:6]}'
KEY_ZOMBIE = f'idem-v2-zombie-{uuid.uuid4().hex[:6]}'  # умышленно: ключ для сценария 2


async def post_order(session, key: str, payload: dict, num: int = 0) -> dict:
    """Один POST /orders: печатает статус, id и признак повтора."""
    started = time.perf_counter()
    async with session.post(
            f'{BASE_URL}/orders', json=payload,
            headers={'Idempotency-Key': key}) as response:
        body = await response.json(content_type=None)
        elapsed = time.perf_counter() - started
        replayed = response.headers.get('Idempotency-Replayed') == 'true'
        marker = 'ПОВТОР' if replayed else 'новый'
        print(f'  POST №{num} ключ "{key[:20]}" -> {response.status} за {elapsed:.2f} c, '
              f'заказ {body.get("order_id")} [{marker}]'
              if isinstance(body, dict) else
              f'  POST №{num} ключ "{key[:20]}" -> {response.status}: {body}')
        return {'status': response.status, 'body': body, 'replayed': replayed}


async def get_order(session, order_id: str) -> int:
    """GET /orders/{id}: возвращает статус."""
    async with session.get(f'{BASE_URL}/orders/{order_id}') as response:
        print(f'  GET    {order_id} -> {response.status}')
        return response.status


async def delete_order(session, order_id: str) -> int:
    """DELETE /orders/{id}: возвращает статус."""
    async with session.delete(f'{BASE_URL}/orders/{order_id}') as response:
        print(f'  DELETE {order_id} -> {response.status}')
        return response.status


async def scenario_retries(session) -> bool:
    """Ретраи подряд: снимок на то же тело, 409 на другое."""
    print(f'\n=== Сценарий 1. Ретраи подряд с ключом "{KEY_MAIN}" ===')
    print('Ожидание: первый POST -> 201, повтор -> 200 ПОВТОР с тем же id, '
          'а POST с тем же ключом, но другой суммой -> 409.')
    payload = {'customer': CUSTOMER, 'amount': AMOUNT}
    first = await post_order(session, KEY_MAIN, payload, 1)
    replay = await post_order(session, KEY_MAIN, payload, 2)
    conflict = await post_order(
        session, KEY_MAIN, {'customer': CUSTOMER, 'amount': 9999.0}, 3)
    same_id = replay['body'].get('order_id') == first['body'].get('order_id')
    ok = (first['status'] == 201 and not first['replayed']
          and replay['status'] == 200 and replay['replayed'] and same_id
          and conflict['status'] == 409)
    print(f'Проверка: {first["status"]} -> {replay["status"]} (id совпал: {same_id}), '
          f'другое тело -> {conflict["status"]} (ожидалось 201 -> 200 -> 409)')
    return ok


async def scenario_after_delete(session) -> bool:
    """Удалённая запись удалена, а снимок ключа - нет: ретрай вернёт «зомби»."""
    print(f'\n=== Сценарий 2. Удалить запись и повторить POST с ключом "{KEY_ZOMBIE}" ===')
    print('Ожидание: GET после удаления -> 404, но POST с тем же ключом -> '
          '200 ПОВТОР со старым id: снимок живёт дольше записи.')
    created = await post_order(
        session, KEY_ZOMBIE, {'customer': 'Боря', 'amount': 42.0}, 0)
    order_id = created['body'].get('order_id')
    deleted = await delete_order(session, order_id)
    deleted_again = await delete_order(session, order_id)
    gone = await get_order(session, order_id)
    zombie = await post_order(
        session, KEY_ZOMBIE, {'customer': 'Боря', 'amount': 42.0}, 0)
    zombie_id = zombie['body'].get('order_id')
    ok = (created['status'] == 201
          and deleted == 200 and deleted_again == 404 and gone == 404
          and zombie['status'] == 200 and zombie['replayed']
          and zombie_id == order_id)
    print(f'Проверка: удаление {deleted}, повторное {deleted_again}, GET {gone}, '
          f'а POST с тем же ключом вернул {zombie_id} (уже удалённый)')
    return ok, order_id


async def scenario_race(session) -> bool:
    """Гонка: N одинаковых POST с одним ключом создают ровно один заказ."""
    print(f'\n=== Сценарий 3. {COUNT} одинаковых POST с ОДНИМ ключом "{KEY_RACE}" ===')
    print(f'Ожидание: один заказ, {COUNT - 1} ответов ПОВТОР, id у всех одинаковый.')
    payload = {'customer': CUSTOMER, 'amount': 777.0}
    results = await asyncio.gather(*[
        post_order(session, KEY_RACE, payload, i) for i in range(COUNT)])
    unique_ids = {r['body'].get('order_id') for r in results}
    created = sum(1 for r in results if r['status'] == 201 and not r['replayed'])
    replays = sum(1 for r in results if r['replayed'])
    ok = len(unique_ids) == 1 and created == 1 and replays == COUNT - 1
    print(f'Проверка: уникальных id {len(unique_ids)} (ожидался 1), '
          f'новых {created} (ожидался 1), повторов {replays} (ожидалось {COUNT - 1})')
    return ok, unique_ids


async def scenario_parallel_keys(session) -> bool:
    """Разные ключи не стоят в очереди: per-key лок, а не глобальный."""
    keys = [f'idem-v2-par-{uuid.uuid4().hex[:6]}' for _ in range(PARALLEL_KEYS)]
    print(f'\n=== Сценарий 4. {PARALLEL_KEYS} POST с РАЗНЫМИ ключами одновременно ===')
    print(f'Ожидание: ~{1.0:.0f} c на всех (каждый заказ "работает" 1 c, но параллельно), '
          'все заказы новые и разные.')
    started = time.perf_counter()
    results = await asyncio.gather(*[
        post_order(session, key, {'customer': CUSTOMER, 'amount': 1.0}, i)
        for i, key in enumerate(keys)])
    elapsed = time.perf_counter() - started
    unique_ids = {r['body'].get('order_id') for r in results}
    all_new = all(r['status'] == 201 and not r['replayed'] for r in results)
    ok = all_new and len(unique_ids) == PARALLEL_KEYS and elapsed < 2.0
    print(f'Проверка: {elapsed:.2f} c (если бы ждали друг друга - было бы ~3 c), '
          f'уникальных id {len(unique_ids)} из {PARALLEL_KEYS}')
    return ok, unique_ids


async def main() -> None:
    print(f'Сервер: {BASE_URL}')
    checks: list[bool] = []
    created_ids: set[str] = set()
    async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
        checks.append(await scenario_retries(session))

        zombie_ok, zombie_id = await scenario_after_delete(session)
        checks.append(zombie_ok)

        race_ok, race_ids = await scenario_race(session)
        checks.append(race_ok)
        created_ids |= race_ids

        parallel_ok, parallel_ids = await scenario_parallel_keys(session)
        checks.append(parallel_ok)
        created_ids |= parallel_ids

        # прибираем живые записи (сценарий 2 уже удалил свою)
        print(f'\n--- Уборка: удаляю {len(created_ids)} оставшихся заказов ---')
        for order_id in sorted(created_ids):
            await delete_order(session, order_id)

    passed = sum(checks)
    print(
        f'\nИтог: {passed}/{len(checks)} проверок сошлись. '
        'Ретрай с тем же ключом получает снимок первого ответа, '
        'чужое тело под чужим ключом - 409, гонка дубликатов создаёт ровно '
        'один заказ, а разные ключи работают параллельно.'
    )


if __name__ == '__main__':
    asyncio.run(main())
