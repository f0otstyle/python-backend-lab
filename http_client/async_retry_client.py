from typing import Callable
from functools import wraps
import logging
import asyncio
import aiohttp
import time

TIMEOUT = 10
SEMAPHORE = 10

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log',
    encoding='utf-8',
    filemode='w',
)

logger = logging.getLogger('api_2')


def retry(times=3, delay=1):
    '''Декаратор для повторного выполнения функции с экспаданцеальной задержкой'''
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for i in range(times):
                try:
                    result = await func(*args, **kwargs)
                    if result == 429 or result >= 500:
                        raise aiohttp.ClientResponseError(
                            status=result,
                            message=f"HTTP Error {result}",
                        )
                    logger.info(f'Функция обработала ответ за {i} попытку')
                    return result
                except Exception as e:
                    if i == times - 1:
                        logger.error(f'Все {times} попыток провалились')
                        raise
                    wait_time = delay * (2 ** i)
                    logger.warning(f'Попытка {i + 1} для {func.__name__} упала: {e}')
                    logger.info(f'Повтор через {wait_time:.2f} секунд')
                    await asyncio.sleep(wait_time)
            return None
        return wrapper
    return decorator


@retry(times=3, delay=1)
async def get_url(session, semaphore, url: str, num: int):
    try:
        async with semaphore:
            logger.info(f'Запись запроса №: {num} началась')
            async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT)
                    ) as response:
                status = response.status
                if status == 429:
                    logger.warning(f'Запрос №{num}: 429 Too Many Requests')
                    raise Exception(f"HTTP {status}: Too Many Requests")

                if status >= 500:
                    logger.warning(f'Запрос №{num}: {status} Server Error')
                    raise Exception(f"HTTP {status}: Server Error")
                logger.info(
                    f'Запрос №: {num} выполнился со статус кодом {status}'
                    )
                return status
    except aiohttp.ClientError as error:
        logger.error(f"Error received {error}")
        raise
    except asyncio.TimeoutError:
        logger.error(f"Запрос №: {num} превышено время запроса")
        raise
    except Exception as error:
        logger.error(
            f'Получена неизвестнная ошибка {error} на запросе №: {num}'
            )
        raise


async def main():
    start = time.perf_counter()
    semaphore = asyncio.Semaphore(SEMAPHORE)
    async with aiohttp.ClientSession() as session:
        tasks = [
            get_url(
                session, semaphore,
                'http://localhost:8000/unstable', i) for i in range(50)]
        results = await asyncio.gather(*tasks)

    count = 0
    for res in results:
        if res is not None and res < 400:
            count += 1

    elapsed = time.perf_counter() - start
    print(
        f'Успешно обработано {count} асинхронных запросов - за время {elapsed:.2f}'
        )

if __name__ == '__main__':
    asyncio.run(main())
