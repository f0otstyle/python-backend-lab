"""Лабораторный сервер: идемпотентное создание заказов.

Запуск: python -m uvicorn server:app --port 8000

Ручки работы с записями:
- POST   /orders            - создать заказ. Идемпотентность по заголовку
                              Idempotency-Key: повтор с тем же ключом не создаёт
                              дубликат, а возвращает ответ первого запроса
                              (пометка Idempotency-Replayed: true). Без ключа
                              каждый запрос создаёт новый заказ - так видно,
                              зачем ключ нужен.
- GET    /orders            - посмотреть все заказы.
- DELETE /orders/{order_id} - удалить заказ; повторное удаление - 404.

Служебная ручка: GET /health -> {"status": "ok"}.

Хранилище в памяти: ORDERS - сами заказы, RESPONSES - сохранённые
первые ответы по ключам идемпотентности.
"""
import asyncio
import logging
import time
import uuid
from http import HTTPStatus

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

CREATE_LAG = 0.2  # имитация обработки заказа: await ниже - точка переключения цикла

# Логируем в консоль, а не в файл: для лабы так нагляднее смотреть вживую
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('loop-lab')


class OrderIn(BaseModel):
    """Тело запроса на создание заказа."""
    item: str
    qty: int = 1


ORDERS: dict[str, dict] = {}     # id заказа -> запись заказа
RESPONSES: dict[str, dict] = {}  # Idempotency-Key -> тело ответа первого запроса

# Замок делает «проверил ключ - создал заказ» атомарным. Без него два
# параллельных запроса с одним ключом оба пройдут проверку до await,
# вместе уснут в CREATE_LAG и создадут дубликаты - та же гонка, что и в exp1:
# цикл переключается только в точках await.
create_lock = asyncio.Lock()

app = FastAPI(title='Orders Idempotency Lab')


@app.get('/health', status_code=HTTPStatus.OK)
async def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.post('/orders', status_code=HTTPStatus.CREATED)
async def create_order(
    payload: OrderIn,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
) -> dict:
    """Создаёт заказ; повтор с тем же ключом возвращает первый ответ."""
    async with create_lock:
        if idempotency_key is not None and idempotency_key in RESPONSES:
            saved = RESPONSES[idempotency_key]
            response.headers['Idempotency-Replayed'] = 'true'
            logger.info(f'create: ключ "{idempotency_key}" уже был - ПОВТОР, '
                        f'отдаю заказ {saved["id"]} без создания')
            return saved
        logger.info(f'create: обрабатываю заказ "{payload.item}" x{payload.qty} '
                    f'(ключ: {idempotency_key or "нет"})')
        await asyncio.sleep(CREATE_LAG)  # здесь цикл переключается на другие запросы
        order = {
            'id': uuid.uuid4().hex[:8],
            'item': payload.item,
            'qty': payload.qty,
            'created_at': time.strftime('%H:%M:%S'),
        }
        ORDERS[order['id']] = order
        if idempotency_key is not None:
            RESPONSES[idempotency_key] = order
        logger.info(f'create: заказ {order["id"]} создан'
                    + (f', ключ "{idempotency_key}" запомнен' if idempotency_key else ''))
    return order


@app.get('/orders')
async def list_orders() -> list[dict]:
    """Посмотреть все заказы в порядке создания."""
    return list(ORDERS.values())


@app.delete('/orders/{order_id}', status_code=HTTPStatus.NO_CONTENT)
async def delete_order(order_id: str) -> None:
    """Удаляет заказ; повторное удаление того же id - 404."""
    if order_id not in ORDERS:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail='Заказ не найден')
    del ORDERS[order_id]
    # Ключи удалённого заказа забываем: иначе повтор create с тем же ключом
    # вернул бы «зомби»-ответ на несуществующий заказ вместо нового.
    for key, saved in list(RESPONSES.items()):
        if saved['id'] == order_id:
            del RESPONSES[key]
            logger.info(f'delete: ключ "{key}" забыт вместе с заказом {order_id}')
    logger.info(f'delete: заказ {order_id} удалён')
