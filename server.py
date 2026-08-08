import asyncio
import time
import random
from pydantic import BaseModel
from http import HTTPStatus
from authx import AuthXConfig, AuthX
import bcrypt
from uuid import uuid4
from fastapi.middleware.cors import CORSMiddleware
import logging
from fastapi import (FastAPI,
                     HTTPException,
                     Response,
                     Depends,
                     WebSocket,
                     WebSocketDisconnect
                     )

app = FastAPI(title="Concurrency Lab Server")

MAX_DELAY = 30

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log',
    encoding='utf-8',
    filemode='a',
)

logger = logging.getLogger('api')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:3000'],
    allow_methods=['*'],
)

db: dict[str, dict] = {}

config = AuthXConfig(
    JWT_SECRET_KEY='SECRET_KEY',
    JWT_TOKEN_LOCATION=['cookies'],
    JWT_ACCESS_COOKIE_NAME='my_cookie')


security: AuthX = AuthX(config=config)


class UserRegisterSchema(BaseModel):
    username: str
    password: str


@app.post('/registerate', status_code=HTTPStatus.CREATED)
async def registrate(user: UserRegisterSchema):
    if db.get(user.username):
        logger.error('Пользователь уже существует')
        raise HTTPException(
            status_code=400,
            detail='Пользователь уже существует'
            )
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), salt)
    logger.info('Пароль захеширован')
    db[user.username] = {
        "id": str(uuid4()),
        "username": user.username,
        "hashed_password": hashed_password
    }
    logger.info('Пользователь создан')
    return {"message": "Пользователь создан"}


@app.post('/login', status_code=HTTPStatus.OK)
async def login(response: Response, user: UserRegisterSchema):
    users = db.get(user.username)
    if not users:
        logger.error('Пользователь не существует')
        raise HTTPException(
            status_code=401,
            detail='Пользователь не найден. Зарегистрируйтесь'
            )

    if not bcrypt.checkpw(
        user.password.encode('utf-8'),
        users['hashed_password']
    ):
        logger.error('Не верный пароль')
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Неверный пароль'
        )
    token = security.create_access_token(uid=users['id'])
    logger.info('Токен выдан')
    response.set_cookie(
            key=config.JWT_ACCESS_COOKIE_NAME,
            value=token,
            httponly=True,
            )
    logger.info('Успешный вход')
    return {"message": "Успешный вход"}


@app.get('/get_login',
         status_code=HTTPStatus.OK,
         dependencies=[Depends(security.access_token_required)]
         )
async def get_login():
    logger.info('Вы авторизованы')
    return {'data': 'Вы авторизованы'}


@app.post('/logout', status_code=HTTPStatus.OK)
async def logout(response: Response):
    response.delete_cookie("my_cookie")
    logger.info('Вы вышли из системы')
    return {"message": "Вы вышли из системы"}


@app.websocket('/ws/')
async def websocket_user(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket подключён")

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Получено {data}")
            await websocket.send_text(f"Эхо: {data}")
    except WebSocketDisconnect:
        logger.info("WebSocket отключён")


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


@app.get("/unstable")
async def unstable():
    """
    Нестабильный эндпоинт для тестирования retry-механизма.
    Возвращает:
    - 200 OK (60% запросов)
    - 429 Too Many Requests (15%)
    - 500 Internal Server Error (15%)
    - 503 Service Unavailable (10%)
    """
    # Случайная задержка от 0.1 до 2 секунд
    await asyncio.sleep(random.uniform(0.1, 2.0))

    rand = random.random()

    if rand < 0.60:
        return {"status": "success", "message": "OK"}
    elif rand < 0.75:
        # 429 Too Many Requests
        raise HTTPException(
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            detail="Too Many Requests"
        )
    elif rand < 0.90:
        # 500 Internal Server Error
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )
    else:
        # 503 Service Unavailable
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail="Service Unavailable"
        )
