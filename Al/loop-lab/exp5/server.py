"""Стенд «нестабильного сервиса» для эксперимента exp5 (retry и backoff).

Запуск: python -m uvicorn server:app --port 8000

Эндпоинты:
- /flaky  - имитация нестабильности: первые FAILS_N запросов после старта
            отвечают 503 (тело-словарь с пояснением), затем всегда 200
- /health - проверка живости: {"status": "ok"} (как в exp1)

Счётчик запросов /flaky живёт в памяти конкретного экземпляра приложения:
фабрика create_app() собирает стенд с чистым счётчиком, поэтому в тестах
достаточно свежего TestClient(create_app()) - и ни сокетов, ни реального
HTTP не нужно. Watchdog'а здесь нет: стенд минимальный, лабе важен только
ответ сервиса.
"""
import logging
from http import HTTPStatus

from fastapi import FastAPI, HTTPException

FAILS_N = 3

# Логируем в консоль, а не в файл: для лабы так нагляднее смотреть вживую
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('loop-lab')


def create_app() -> FastAPI:
    """Собирает экземпляр стенда с чистым счётчиком отказов.

    Счётчик замыкается на конкретное приложение, поэтому каждый вызов
    create_app() даёт «свежий» сервис: и тесты, и перезапуск стенда
    всегда начинают с FAILS_N отказов /flaky.
    """
    app = FastAPI(title='Flaky Service Lab (exp5)')
    fails_left = FAILS_N  # сколько запросов /flaky ещё «прогревается»

    @app.get('/health', status_code=HTTPStatus.OK)
    async def health() -> dict[str, str]:
        """/health живёт всегда, даже пока /flaky ещё отказывает."""
        return {'status': 'ok'}

    @app.get('/flaky')
    async def flaky() -> dict[str, str]:
        """Нестабильный эндпоинт: FAILS_N раз даёт 503, затем стабилен.

        Клиент exp5 будет добиваться этого 200 через retry с backoff -
        стенд лишь честно «ломается» первые FAILS_N запросов после старта.
        """
        nonlocal fails_left
        if fails_left > 0:
            fails_left -= 1
            logger.warning(f'flaky: 503, ещё {fails_left} отказов до стабилизации')
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                detail=f'Сервис «прогревается»: ещё {fails_left} отказов до 200',
            )
        logger.info('flaky: 200, сервис стабилен')
        return {'status': 'ok', 'mode': 'stable'}

    return app


# Экземпляр для живого запуска: python -m uvicorn server:app --port 8000
app = create_app()
