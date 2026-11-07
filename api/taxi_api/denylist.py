
import hashlib
import time

from authx import TokenPayload
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials
from redis.asyncio import Redis

from deps import security, get_cache
from redis_cache import RedisCachedBackend

DENYLIST_PREFIX = "auth:denylist:"


def _denylist_key(token: str, payload: TokenPayload) -> str:
    jti = payload.jti or hashlib.sha256(token.encode()).hexdigest()
    return f"{DENYLIST_PREFIX}{jti}"


class Denylist:
    async def revoke_token(self, redis: Redis, token: str, payload: TokenPayload):
        """Добавить токен в denylist на остаток его жизни."""
        remaining = int(payload.exp.timestamp() - time.time())
        if remaining <= 0:
            return
        await redis.set(_denylist_key(token, payload), "revoked", ex=remaining)


async def ensure_not_revoked(
        request: Request,
        payload: TokenPayload = Security(security.access_token_required),
        cache: RedisCachedBackend = Depends(get_cache)):
    """Зависимость для защищённых ручек: токен валиден И не отозван."""
    request_token = await security.get_token_from_request(request)
    if request_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен не найден",
        )
    token = request_token.token
    if await cache.redis.exists(_denylist_key(token, payload)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен отозван",
        )
    return payload
