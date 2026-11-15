"""Клиент-экспериментатор: идемпотентность создания заказов.

1. Запусти сервер:  python -m uvicorn server:app --port 8000
2. Запусти клиент:  python client_1.py
3. Смотри ОДНОВРЕМЕННО в консоль сервера: там видно, какой запрос создал
   заказ, а какой вернул сохранённый ответ по ключу.

Три сценария:
- одинаковые POST без ключа      -> плодят дубликаты;
- одинаковые POST с одним ключом -> один заказ, остальные ответы - повторы;
- удалить заказ и повторить POST с тем же ключом -> создастся новый заказ,
  а не «зомби»-повтор удалённого.

Адрес сервера можно переопределить переменной окружения LAB_URL:
LAB_URL=http://localhost:8010 python client_1.py
"""
import asyncio
import os

import aiohttp

BASE_URL = os.environ.get('LAB_URL', 'http://localhost:8000')
COUNT = 5     # сколько одинаковых запросов шлём в каждом сценарии
TIMEOUT = 60
ITEM = 'болт М8'
QTY = 10
KEY = 'order-key-1'  # один и тот же ключ для всех повторов в сценариях 2 и 3


async def create_order(session, key: str | None, num: int) -> dict:
    """Один POST /orders; возвращает статус, тело ответа и признак повтора."""
    headers = {'Idempotency-Key': key} if key else {}
    async with session.post(
            f'{BASE_URL}/orders',
            json={'item': ITEM, 'qty': QTY},
            headers=headers) as response:
        body = await response.json(content_type=None)
        replayed = response.headers.get('Idempotency-Replayed') == 'true'
        marker = 'ПОВТОР' if replayed else 'новый'
        print(f'  запрос №{num}: ключ "{key or "-"}" -> {response.status}, '
              f'заказ {body.get("id")} [{marker}]')
        return {'status': response.status, 'body': body, 'replayed': replayed}


async def list_orders(session) -> list:
    """GET /orders: посмотреть, какие записи сейчас на сервере."""
    async with session.get(f'{BASE_URL}/orders') as response:
        return await response.json(content_type=None)


async def delete_order(session, order_id: str) -> int:
    """DELETE /orders/{id}: возвращает статус удаления."""
    async with session.delete(f'{BASE_URL}/orders/{order_id}') as response:
        print(f'  удаление заказа {order_id} -> {response.status}')
        return response.status


async def scenario_without_key(session) -> bool:
    """Без ключа каждый повтор создаёт свой заказ - дубликаты неизбежны."""
    print(f'\n=== Сценарий 1. {COUNT} одинаковых POST БЕЗ ключа ===')
    print(f'Ожидание: на сервере появится {COUNT} разных заказов.')
    results = await asyncio.gather(*[
        create_order(session, None, i) for i in range(COUNT)])
    orders = await list_orders(session)
    unique_ids = {r['body'].get('id') for r in results}
    ok = len(orders) == COUNT and len(unique_ids) == COUNT
    print(f'Проверка: заказов на сервере {len(orders)} (ожидалось {COUNT}), '
          f'уникальных id в ответах {len(unique_ids)} (ожидалось {COUNT})')
    # прибираем за собой ручкой удаления, чтобы не мешать следующему сценарию
    for order in orders:
        await delete_order(session, order['id'])
    return ok


async def scenario_with_key(session) -> tuple[bool, str | None]:
    """Повторы с одним ключом должны вернуть ответ первого запроса."""
    print(f'\n=== Сценарий 2. {COUNT} одинаковых POST с ОДНИМ ключом "{KEY}" ===')
    print(f'Ожидание: один заказ, {COUNT - 1} ответов с пометкой ПОВТОР.')
    results = await asyncio.gather(*[
        create_order(session, KEY, i) for i in range(COUNT)])
    orders = await list_orders(session)
    unique_ids = {r['body'].get('id') for r in results}
    replays = sum(1 for r in results if r['replayed'])
    ok = len(orders) == 1 and len(unique_ids) == 1 and replays == COUNT - 1
    print(f'Проверка: заказов на сервере {len(orders)} (ожидалась 1), '
          f'уникальных id {len(unique_ids)} (ожидался 1), '
          f'повторов {replays} из {COUNT} (ожидалось {COUNT - 1})')
    order_id = orders[0]['id'] if orders else None
    return ok, order_id


async def scenario_after_delete(session, order_id: str) -> bool:
    """Удалённый заказ не должен «воскресать» из хранилища ключей."""
    print(f'\n=== Сценарий 3. Удалить заказ {order_id} и повторить POST с тем же ключом ===')
    print('Ожидание: удаление -> 204, повторное удаление -> 404, '
          'а POST с тем же ключом создаст НОВЫЙ заказ.')
    deleted = await delete_order(session, order_id)
    deleted_again = await delete_order(session, order_id)
    again = await create_order(session, KEY, 0)
    orders = await list_orders(session)
    new_id = again['body'].get('id')
    ok = (deleted == 204
          and deleted_again == 404
          and again['status'] == 201
          and not again['replayed']
          and new_id != order_id
          and len(orders) == 1)
    print(f'Проверка: удаление -> {deleted} (ожидалось 204), повтор -> {deleted_again} '
          f'(ожидалось 404), POST вернул заказ {new_id} вместо {order_id}, '
          f'заказов на сервере {len(orders)} (ожидался 1)')
    await delete_order(session, new_id)
    return ok


async def main() -> None:
    print(f'Сервер: {BASE_URL}')
    checks: list[bool] = []
    async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
        # чистый лист: сносим всё, что осталось от прошлых запусков
        for order in await list_orders(session):
            await delete_order(session, order['id'])

        checks.append(await scenario_without_key(session))
        with_key_ok, order_id = await scenario_with_key(session)
        checks.append(with_key_ok)
        if order_id:
            checks.append(await scenario_after_delete(session, order_id))

    passed = sum(checks)
    print(
        f'\nИтог: {passed}/{len(checks)} проверок сошлись. '
        'Без ключа повторы плодят дубликаты; с ключом сервер возвращает '
        'ответ первого запроса; после удаления ключ забывается - '
        'следующий POST с тем же ключом создаёт новый заказ.'
    )


if __name__ == '__main__':
    asyncio.run(main())
