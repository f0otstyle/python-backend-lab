from time import perf_counter
import logging
from typing import Callable
from fastapi import HTTPException
from functools import wraps

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='taxi.log',
    encoding='utf-8',
    filemode='a',
)

logger = logging.getLogger('api')


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
