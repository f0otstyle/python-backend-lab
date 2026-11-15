"""Лабораторный сервер для экспериментов с event loop.

Запуск: python -m uvicorn server:app --port 8000

Эндпоинты задержки:
- /delay/{seconds}          - асинхронная задержка (await asyncio.sleep)
- /blocking/{seconds}       - синхронная задержка внутри async-обработчика (time.sleep)
- /offloaded/{seconds}      - тот же time.sleep, но унесённый в отдельный поток
- /def-threadpool/{seconds} - синхронный обработчик на обычном def (FastAPI сам уносит его в threadpool)

Пока сервер работает, watchdog измеряет лаг event loop:
как только в цикл попадает синхронная задача, в консоли появляется WARNING.
"""
import asyncio
import time
import logging
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI

MAX_DELAY = 30

# Логируем в консоль, а не в файл: для лабы так нагляднее смотреть вживую
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('loop-lab')


async def watchdog(interval: float = 0.5) -> None:
    """Фоновая задача: просыпается каждые `interval` секунд и меряет опоздание.

    Пока в цикле крутится только асинхронный код, опоздание ~0-5 мс.
    Если кто-то заморозил цикл синхронным кодом (например, time.sleep),
    опоздание равно времени заморозки - это самый честный ответ на вопрос,
    что происходит с event loop, когда в него попадает синхронная задача.
    """
    loop = asyncio.get_running_loop()
    while True:
        started = loop.time()
        await asyncio.sleep(interval)
        lag = loop.time() - started - interval
        if lag > 0.2:
            logger.warning(
                f'WATCHDOG: event loop не отвечал {lag:.2f} c - '
                f'в него попал синхронный код!'
            )
        else:
            logger.info(f'WATCHDOG: heartbeat, лаг {lag * 1000:.0f} мс')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Стартует watchdog при запуске сервера и гасит его при остановке."""
    logger.info('Сервер запущен, watchdog следит за event loop')
    watcher = asyncio.create_task(watchdog())
    yield
    watcher.cancel()
    logger.info('Сервер остановлен')


app = FastAPI(title='Event Loop Lab', lifespan=lifespan)


@app.get('/health', status_code=HTTPStatus.OK)
async def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/delay/{seconds}')
async def delay(seconds: float) -> dict[str, float | str]:
    """Асинхронная задержка: корутина засыпает и отдаёт управление event loop."""
    seconds = min(seconds, MAX_DELAY)
    logger.info(f'delay({seconds}): старт')
    await asyncio.sleep(seconds)  # точка переключения: loop обслуживает другие запросы
    logger.info(f'delay({seconds}): закончился')
    return {'slept': seconds, 'mode': 'async'}


@app.get('/blocking/{seconds}')
async def blocking(seconds: float) -> dict[str, float | str]:
    """Синхронная задержка внутри async-обработчика: event loop заморожен.

    time.sleep() не содержит ни одного await, поэтому циклу некуда
    переключаться: /delay, /health и watchdog простаивают, пока он спит.
    """
    seconds = min(seconds, MAX_DELAY)
    logger.info(f'blocking({seconds}): старт, замораживаю event loop')
    time.sleep(seconds)  # <-- синхронная задача внутри event loop
    logger.info(f'blocking({seconds}): event loop снова крутится')
    return {'slept': seconds, 'mode': 'blocking'}


@app.get('/offloaded/{seconds}')
async def offloaded(seconds: float) -> dict[str, float | str]:
    """Правильный способ запускать синхронный код из async-обработчика.

    asyncio.to_thread() уносит time.sleep() в отдельный поток,
    поэтому event loop продолжает крутиться.
    """
    seconds = min(seconds, MAX_DELAY)
    logger.info(f'offloaded({seconds}): старт, уношу sleep в поток')
    await asyncio.to_thread(time.sleep, seconds)
    logger.info(f'offloaded({seconds}): поток закончил, loop не пострадал')
    return {'slept': seconds, 'mode': 'thread'}


@app.get('/def-threadpool/{seconds}')
def def_threadpool(seconds: float) -> dict[str, float | str]:
    """Синхронный обработчик на обычном def (не async def).

    FastAPI сам запускает такие функции в threadpool,
    поэтому time.sleep() здесь не трогает event loop.
    """
    seconds = min(seconds, MAX_DELAY)
    logger.info(f'def-threadpool({seconds}): старт в отдельном потоке')
    time.sleep(seconds)
    logger.info(f'def-threadpool({seconds}): закончился')
    return {'slept': seconds, 'mode': 'def-threadpool'}
