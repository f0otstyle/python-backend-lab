"""Клиент-экспериментатор для лабораторного сервера.

1. Запусти сервер:  python -m uvicorn server:app --port 8000 --workers 1
   (--workers 1 = один процесс и один event loop: иначе блокировка
   размазалась бы по нескольким процессам и эксперимент был бы нечестным)
2. Запусти клиент:  python client_2.py
3. Смотри ОДНОВРЕМЕННО в консоль сервера: там watchdog покажет,
   когда event loop замерзал из-за синхронного кода.

Каждый ответ проверяется по двум критериям:
- HTTP-статус == 200;
- JSON-тело корректно: поле 'mode' совпадает с эндпоинтом,
  поле 'slept' совпадает с запрошенной задержкой (с допуском).
  Заодно проверка словит серверный clamp MAX_DELAY,
  если попросить задержку больше 30 c.

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
SLEPT_TOLERANCE = 0.05  # допуск при сверке slept с запрошенной задержкой

# какое значение поля 'mode' должен вернуть каждый эндпоинт
EXPECTED_MODE = {
    '/delay': 'async',
    '/blocking': 'blocking',
    '/offloaded': 'thread',
    '/def-threadpool': 'def-threadpool',
}


def expected_for(path: str) -> tuple[str, float]:
    """(ожидаемый mode, ожидаемая задержка) из пути вида '/delay/1.0'."""
    endpoint, seconds_str = path.rsplit('/', 1)
    return EXPECTED_MODE[endpoint], float(seconds_str)


async def fetch(session, semaphore, path: str, num: int) -> dict:
    """Один запрос: замер времени, проверка статуса и JSON-ответа."""
    expected_mode, expected_slept = expected_for(path)
    errors: list[str] = []
    status = None
    json_ok = False
    async with semaphore:
        started = time.perf_counter()
        try:
            async with session.get(f'{BASE_URL}{path}') as response:
                status = response.status
                if status != 200:
                    errors.append(f'статус {status} != 200')
                body = None
                try:
                    body = await response.json(content_type=None)
                except Exception:
                    errors.append('тело ответа не валидный JSON')
                if body is not None:
                    json_ok = True
                    if body.get('mode') != expected_mode:
                        json_ok = False
                        errors.append(
                            f"mode={body.get('mode')!r} вместо {expected_mode!r}")
                    slept = body.get('slept')
                    if (not isinstance(slept, (int, float))
                            or abs(slept - expected_slept) > SLEPT_TOLERANCE):
                        json_ok = False
                        errors.append(f'slept={slept!r} вместо {expected_slept}')
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            errors.append(f'сетевая ошибка: {error!r}')
        elapsed = time.perf_counter() - started

    verdict = 'OK' if not errors else 'ПРОВАЛ: ' + '; '.join(errors)
    print(f'  запрос №{num}: {path} -> {status} за {elapsed:.2f} c | {verdict}')
    return {'num': num, 'status': status, 'json_ok': json_ok,
            'elapsed': elapsed, 'errors': errors}


async def run_scenario(title: str, path: str, count: int, expected: str) -> None:
    """Запускает count одновременных запросов и печатает сводку проверок."""
    print(f'\n=== {title} ===')
    print(f'{count} одновременных запросов на {path}. Ожидание: {expected}')
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
    start = time.perf_counter()
    async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
        tasks = [fetch(session, semaphore, path, i) for i in range(count)]
        results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start
    status_ok = sum(1 for r in results if r['status'] == 200)
    json_ok = sum(1 for r in results if r['json_ok'])
    print(f'Итог: статус 200 у {status_ok}/{count}, '
          f'JSON корректен у {json_ok}/{count}, общее время {elapsed:.2f} c')


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
