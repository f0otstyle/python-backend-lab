from datetime import datetime, timezone
from typing import Callable
from functools import wraps
from fastapi import FastAPI, HTTPException, Request
from time import perf_counter
from http import HTTPStatus
import logging
from fastapi.params import Header
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


class OrderCreate(BaseModel):
    Location: str


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
            'detail': "Заказ с таким адресом существует"
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
            'detail': "Данного заказа не существует"
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
            logger.error(f'HTTP ошибка в {func.__name__}: {e.status_code}')
            raise
        except Exception as error:
            logger.error(f'Появилась ошибка {error}')
            raise
    return wrapper


@app.get('/taxi', status_code=HTTPStatus.OK)
@log
async def list_of_orders():
    '''Список всех заказов'''
    return db


@app.post('/taxi', status_code=HTTPStatus.CREATED)
@log
async def ordering_a_taxi(orders: OrderCreate, request: Request, idempotency_key: str = Header(None, alias="Idempotency-Key")):
    '''Создаем заказ'''
    location = orders.Location
    idempotency_Key = request.headers.get('Idempotency-Key')

    if not location:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Поле 'Location' обязательно"
        )

    if not idempotency_Key:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Поле 'idempotency_Key' обязательно"
        )

    current_time = datetime.now(timezone.utc).timestamp()
    for order in db:
        if order.get('Idempotency-Key') == idempotency_Key:
            logger.info(f"Повторный запрос с ключом {idempotency_Key}")
            return JSONResponse(
                status_code=HTTPStatus.CREATED,
                content=order,
                headers={"Location": f"/taxi/{order['id']}"}
            )

        if order.get('Location') == location:
            created_at = order.get('CreatedAt', 0)
            time_diff = current_time - created_at
            if time_diff < TIME:
                logger.warning(f'Попытка создать дубликат заказа для {location} (прошло {time_diff:.1f} с)')
                raise OrderError()
            else:
                logger.info('Можно сделать новый заказ')

    order = {
        "id": len(db) + 1,
        "Idempotency-Key": idempotency_Key,
        "Location": location,
        "CreatedAt": current_time
    }
    db.append(order)
    logger.info(f'Новый закащ сделан с ID {order.get("id")}')

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
    raise SearchError()


@app.delete('/taxi/{order_id}', status_code=HTTPStatus.NO_CONTENT)
@log
async def order_delete(order_id: int):
    '''Удаление заказа'''
    for order in db:
        if order.get('id') == order_id:
            db.remove(order)
            return
    raise SearchError()
