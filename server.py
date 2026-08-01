import asyncio
from http import HTTPStatus
import time

from fastapi import FastAPI

app = FastAPI(title="Concurrency Lab Server")

MAX_DELAY = 30


@app.get("/health", status_code=HTTPStatus.OK)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get('/status-200', status_code=HTTPStatus.OK)
async def status_200():
    return {}


@app.post('/status-201', status_code=HTTPStatus.CREATED)
async def stasus_201():
    return {'messenge': 'Created', 'detail': 'Запись успешно создана'}


@app.delete('/status-204', status_code=HTTPStatus.NO_CONTENT)
async def stasus_204():
    return None


@app.get('/status-400', status_code=HTTPStatus.BAD_REQUEST)
async def stasus_400():
    return {'messenge': 'Bad Request'}


@app.post('/status-409', status_code=HTTPStatus.CONFLICT)
async def stasus_409():
    return {'messenge': 'Conflict'}


@app.post('/status-429', status_code=HTTPStatus.TOO_MANY_REQUESTS)
async def stasus_429():
    return {'messenge': 'TOO_MANY_REQUESTS'}


@app.get("/delay/{seconds}")
async def delay(seconds: float) -> dict[str, float | str]:
    """Неблокирующая задержка: корутина отдаёт управление event loop."""
    seconds = min(seconds, MAX_DELAY)
    await asyncio.sleep(seconds)
    return {"slept": seconds, "mode": "async"}


@app.get("/blocking/{seconds}")
async def blocking(seconds: float) -> dict[str, float | str]:
    """Блокирующая задержка: поток встаёт, event loop не крутит другие задачи."""
    seconds = min(seconds, MAX_DELAY)
    time.sleep(seconds)
    return {"slept": seconds, "mode": "blocking"}
