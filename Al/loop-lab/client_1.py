"""Клиент-экспериментатор для лабораторного сервера.

1. Запусти сервер:  python -m uvicorn server:app --port 8000
2. Запусти клиент:  python client.py
3. Смотри ОДНОВРЕМЕННО в консоль сервера: там watchdog покажет,
   когда event loop замерзал из-за синхронного кода.

Адрес сервера можно переопределить переменной окружения LAB_URL:
LAB_URL=http://localhost:8010 python client.py
"""
import asyncio
import os
import time

import aiohttp

BASE_URL = os.environ.get('LAB_URL', 'http://localhost:8000')
COUNT = 5            # сколько одновременных запросов в каждом сценарии
DELAY = 1.0          # сколько секунд спит каждый эндпоинт
BLOCKING_DELAY = 3.0 # длительность блокирующего запроса в сценарии «заморозка»
SEMAPHORE_LIMIT = 10 # максимум одновременных запросов (как в твоём compare.py)
TIMEOUT = 60


async def fetch(session, semaphore, path: str, num: int) -> int:
    """Один запрос с замером реального времени выполнения."""
    async with semaphore:
        started = time.perf_counter()
        async with session.get(f'{BASE_URL}{path}') as response:
            await response.read()
            elapsed = time.perf_counter() - started
            print(f'  запрос №{num}: {path} -> {response.status} за {elapsed:.2f} c')
            return response.status


async def run_scenario(title: str, path: str, count: int, expected: str) -> None:
    """Запускает count одновременных запросов и печатает общее время."""
    print(f'\n=== {title} ===')
    print(f'{count} одновременных запросов на {path}. Ожидание: {expected}')
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
    start = time.perf_counter()
    async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
        tasks = [fetch(session, semaphore, path, i) for i in range(count)]
        statuses = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start
    ok = sum(1 for status in statuses if status == 200)
    print(f'Итог: {ok}/{count} успешно за {elapsed:.2f} c')


async def run_freeze_scenario() -> None:
    """Главный эксперимент: /blocking ставит на паузу соседние /delay-запросы."""
    print('\n=== Сценарий 5. «Заморозка» event loop ===')
    print(
        f'{COUNT} запросов на /delay/{DELAY} стартуют первыми, через 0.2 c '
        f'прилетает /blocking/{BLOCKING_DELAY}. '
        f'Ожидание: delay-запросы, которые должны были занять {DELAY} c, '
        f'завершатся только после разморозки (~{0.2 + BLOCKING_DELAY:.1f} c).'
    )
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
    async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
        delay_tasks = [
            asyncio.create_task(fetch(session, semaphore, f'/delay/{DELAY}', i))
            for i in range(COUNT)
        ]
        await asyncio.sleep(0.2)  # даём delay-запросам успеть «заснуть»
        blocking_task = asyncio.create_task(
            fetch(session, semaphore, f'/blocking/{BLOCKING_DELAY}', 99)
        )
        await asyncio.gather(*delay_tasks, blocking_task)


async def main() -> None:
    print(f'Сервер: {BASE_URL}')

    await run_scenario(
        'Сценарий 1. Чистый asyncio',
        f'/delay/{DELAY}',
        COUNT,
        expected=f'~{DELAY:.0f} c - event loop обслуживает все запросы одновременно',
    )
    await run_scenario(
        'Сценарий 2. Синхронный код внутри async-обработчика',
        f'/blocking/{DELAY}',
        COUNT,
        expected=f'~{COUNT * DELAY:.0f} c - запросы выстроились в очередь, loop заморожен',
    )
    await run_scenario(
        'Сценарий 3. Синхронный код через asyncio.to_thread',
        f'/offloaded/{DELAY}',
        COUNT,
        expected=f'~{DELAY:.0f} c - sleep крутится в отдельном потоке',
    )
    await run_scenario(
        'Сценарий 4. Обработчик на обычном def',
        f'/def-threadpool/{DELAY}',
        COUNT,
        expected=f'~{DELAY:.0f} c - FastAPI сам уносит def-обработчики в threadpool',
    )
    await run_freeze_scenario()

    print(
        '\nВывод: время «съедает» только синхронный код внутри async-обработчика. '
        'Всё, что содержит await, event loop крутит параллельно.'
    )


if __name__ == '__main__':
    asyncio.run(main())
