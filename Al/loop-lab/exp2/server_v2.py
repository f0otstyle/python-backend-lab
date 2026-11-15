"""Лабораторный сервер v2: идемпотентное создание заказов.

Запуск (из папки exp2): python -m uvicorn server_v2:app --port 8001
(8001, чтобы не пересекаться с server.py из v1 на 8000)

Три ручки для работы с записями:
- POST   /orders            - создать заказ (идемпотентно, через Idempotency-Key)
- GET    /orders/{order_id} - посмотреть конкретную запись
- DELETE /orders/{order_id} - удалить запись
(плюс /health - служебная ручка, как в exp1)

Контракт идемпотентности (как у платёжных API, например Stripe):
- клиент сам генерирует ключ и кладёт его в заголовок Idempotency-Key;
  без ключа сервер отвечает 422 - в v2 «слепых» запросов не бывает;
- первый POST занимает ключ, имитирует работу PROCESSING_DELAY секунд,
  создаёт заказ и запоминает снимок ответа -> 201;
- повтор с тем же ключом и тем же телом НЕ создаёт второй заказ:
  возвращается сохранённый снимок -> 200 + заголовок Idempotency-Replayed: true;
- повтор с тем же ключом, но другим телом -> 409 Conflict (ключ занят);
- одновременные POST с одним ключом выстраиваются в per-key очередь
  (asyncio.Lock на каждый ключ), разные ключи друг друга не ждут.

Всё состояние в памяти процесса: рестарт сервера стирает и заказы, и ключи.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from http import HTTPStatus

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field

PROCESSING_DELAY = 1.0  # имитация «тяжёлого» создания: запись в БД, поход в платёжку

# Логируем в консоль, а не в файл: для лабы так нагляднее смотреть вживую
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('loop-lab')

app = FastAPI(title='Idempotency Lab v2')

# --- состояние в памяти процесса ---------------------------------------
orders: dict[str, dict] = {}       # order_id -> запись заказа
idempotency: dict[str, dict] = {}  # ключ -> {'fingerprint': str, 'response': dict}
_key_locks: dict[str, asyncio.Lock] = {}  # лок на каждый ключ: гонка дубликатов


class OrderIn(BaseModel):
    """Тело заказа: покупатель и сумма."""
    customer: str
    amount: float = Field(gt=0, description='сумма заказа, строго больше нуля')


def _lock_for(key: str) -> asyncio.Lock:
    """Лок на конкретный ключ: дубликаты ждут друг друга, остальные - нет."""
    if key not in _key_locks:
        _key_locks[key] = asyncio.Lock()
    return _key_locks[key]


def _fingerprint(payload: OrderIn) -> str:
    """Каноническое представление тела: одинаковые тела дают одинаковую строку."""
    return json.dumps(payload.model_dump(), sort_keys=True, ensure_ascii=False)


@app.get('/health', status_code=HTTPStatus.OK)
async def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.post('/orders', status_code=HTTPStatus.CREATED)
async def create_order(
        payload: OrderIn,
        response: Response,
        idempotency_key: str = Header(..., alias='Idempotency-Key', min_length=1),
) -> dict:
    """Ручка 1. Идемпотентное создание заказа.

    Проверка-then-действие спрятана под лок КЛЮЧА: два одинаковых POST,
    пришедшие одновременно, не создадут дубль - второй дождётся первого
    и вернёт его снимок. Лок именно пер-ключевый, а не глобальный:
    разные заказы создаются параллельно.
    """
    fingerprint = _fingerprint(payload)
    async with _lock_for(idempotency_key):
        record = idempotency.get(idempotency_key)
        if record is not None:
            if record['fingerprint'] != fingerprint:
                logger.warning(f'POST ключ={idempotency_key!r}: тело отличается - 409')
                raise HTTPException(
                    status_code=HTTPStatus.CONFLICT,
                    detail='Ключ идемпотентности уже использован с другим телом запроса',
                )
            # повтор: снимок уже есть, второй заказ не создаём
            saved_id = record['response']['order_id']
            logger.info(f'POST ключ={idempotency_key!r}: повтор - верну снимок заказа {saved_id}')
            response.headers['Idempotency-Replayed'] = 'true'
            response.status_code = HTTPStatus.OK
            return record['response']

        # первый запрос с этим ключом: имитируем работу и создаём запись
        logger.info(
            f'POST ключ={idempotency_key!r}: создаю заказ '
            f'(имитация работы {PROCESSING_DELAY} c)')
        await asyncio.sleep(PROCESSING_DELAY)  # окно, в которое прилетают дубликаты
        order = {
            'order_id': f'ord-{uuid.uuid4().hex[:8]}',
            'customer': payload.customer,
            'amount': payload.amount,
            'status': 'created',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'idempotency_key': idempotency_key,
        }
        orders[order['order_id']] = order
        idempotency[idempotency_key] = {
            'fingerprint': fingerprint,
            'response': dict(order),  # снимок ответа: ретраи получат ровно его
        }
        logger.info(f'POST ключ={idempotency_key!r}: заказ {order["order_id"]} создан')
        return order


@app.get('/orders/{order_id}')
async def get_order(order_id: str) -> dict:
    """Ручка 2. Посмотреть запись по её id."""
    order = orders.get(order_id)
    if order is None:
        logger.warning(f'GET {order_id}: записи нет - 404')
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Заказ не найден')
    logger.info(f'GET {order_id}: отдаю запись')
    return order


@app.delete('/orders/{order_id}')
async def delete_order(order_id: str) -> dict:
    """Ручка 3. Удалить запись.

    Снимок идемпотентности при удалении НЕ стираем: ретрай старого POST
    даже после удаления вернёт старый снимок. В реальных системах у ключей
    есть TTL/окно жизни - здесь оставлено намеренно, client_v2 показывает
    эту каверзу отдельным сценарием.
    """
    order = orders.pop(order_id, None)
    if order is None:
        logger.warning(f'DELETE {order_id}: записи нет - 404')
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Заказ не найден')
    logger.info(f'DELETE {order_id}: запись удалена')
    return {'status': 'deleted', 'order': order}
