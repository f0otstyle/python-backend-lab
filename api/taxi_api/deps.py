import os
from datetime import timedelta

from authx import AuthX, AuthXConfig
from fastapi import Request

from redis_cache import RedisCachedBackend


config = AuthXConfig(
    JWT_SECRET_KEY=os.getenv('JWT_SECRET_KEY', 'SECRET-KEY'),
    JWT_TOKEN_LOCATION=['cookies'],
    JWT_ACCESS_COOKIE_NAME='my_cookie',
    JWT_ACCESS_TOKEN_EXPIRES=timedelta(days=1),
    JWT_COOKIE_CSRF_PROTECT=False,
    )

security: AuthX = AuthX(config=config)


async def get_cache(request: Request) -> RedisCachedBackend:
    return request.app.state.redis_cache
