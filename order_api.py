from datetime import datetime, timezone
from typing import Callable
from functools import wraps
from fastapi import FastAPI, HTTPException, Request, Header
from time import perf_counter
from http import HTTPStatus
import logging
from fastapi.responses import JSONResponse
from pydantic import BaseModel

TIME = 5

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log',
    encoding='utf-8',
    filemode='a',
)

logger = logging.getLogger('api')

counter = 1


class OrderCreate(BaseModel):
    address: str


db: list[dict] = []


class OrderError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=HTTPStatus.CONFLICT,
            detail='Заказ с таким адресом существует'
            )


@app.exception_handler(OrderError)
async def order_error(request: Request, exc: OrderError):
    return JSONResponse(
        status_code=HTTPStatus.CONFLICT,
        content={
            "error": True,
            "type": "OrderError",
            'detail': exc.detail
        })


class SearchError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Данного заказа не существует'
            )


@app.exception_handler(SearchError)
async def search_error(request: Request, exc: SearchError):
    return JSONResponse(
        status_code=HTTPStatus.NOT_FOUND,
        content={
            "error": True,
            "type": "SearchError",
            'detail': exc.detail
        })


def log(func: Callable):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            start_time = perf_counter()
            result = await func(*args, **kwargs)
            finish = perf_counter() - start_time
            logger.info(f'Выполнилось успешно функция {func.__name__} за время {finish}')
            return result
        except HTTPException as e:
            logger.exception(f'HTTP ошибка в {func.__name__}: {e.status_code}')
            raise
        except Exception as error:
            logger.exception(f'Появилась ошибка {error}')
            raise
    return wrapper


@app.get('/taxi', status_code=HTTPStatus.OK)
@log
async def list_of_orders():
    '''Список всех заказов'''
    return db


@app.post('/taxi', status_code=HTTPStatus.CREATED)
@log
async def ordering_a_taxi(
    orders: OrderCreate,
    request: Request,
    idempotency_key: str = Header(None, alias="idempotency_key")):
    '''Создаем заказ'''

    global counter
    address = orders.address

    if not idempotency_key:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Поле 'idempotency_Key' обязательно"
        )

    current_time = datetime.now(timezone.utc).timestamp()
    for order in db:
        if order.get('Idempotency-Key') == idempotency_key:
            logger.info(f"Повторный запрос с ключом {idempotency_key}")
            return JSONResponse(
                status_code=HTTPStatus.CREATED,
                content=order,
                headers={"Location": f"/taxi/{order['id']}"}
            )

    for order in db:
        if order.get('Location') == address:
            created_at = order.get('CreatedAt', 0)
            time_diff = current_time - created_at
            if time_diff < TIME:
                logger.warning(
                    f'Попытка создать дубликат заказа для {address} (прошло {time_diff:.1f} с)'
                    )
                raise OrderError()
            else:
                logger.info('Можно сделать новый заказ')

    order = {
        "id": counter,
        "idempotency_key": idempotency_key,
        "address": address,
        "CreatedAt": current_time
    }
    db.append(order)
    logger.info(f'Новый закащ сделан с ID {order.get("id")}')

    counter += 1

    return JSONResponse(
        status_code=HTTPStatus.CREATED,
        content=order,
        headers={"Location": f"/taxi/{order['id']}"}
    )


@app.get('/taxi/{order_id}', status_code=HTTPStatus.OK)
@log
async def order_search(order_id: int):
    '''Поиск конкретного заказа'''
    for order in db:
        if order.get('id') == order_id:
            return order
    logger.warning(f'Попытка найти несуществующий заказ {order_id}')
    raise SearchError()


@app.delete('/taxi/{order_id}', status_code=HTTPStatus.NO_CONTENT)
@log
async def order_delete(order_id: int):
    '''Удаление заказа'''
    for order in db:
        if order.get('id') == order_id:
            db.remove(order)
            return

    logger.warning(f'Попытка удалить несуществующий заказ {order_id}')
    raise SearchError()
