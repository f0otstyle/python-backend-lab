
import hashlib
import time

from authx import TokenPayload
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials
from redis.asyncio import Redis

from deps import security, get_cache

DENYLIST_PREFIX = "auth:denylist:"


def _denylist_key(token: str, payload: TokenPayload) -> str:
    jti = payload.jti or hashlib.sha256(token.encode()).hexdigest()
    return f"{DENYLIST_PREFIX}{jti}"


class Denylist:
    async def revoke_token(self, redis: Redis, token: str):
        """Добавить токен в denylist на остаток его жизни."""
        payload: TokenPayload = security.verify_token(token)
        remaining = int(payload.exp - time.time())
        if remaining <= 0:
            return
        await redis.set(_denylist_key(token, payload), "revoked", ex=remaining)


async def ensure_not_revoked(
        credentials: HTTPAuthorizationCredentials = Security(security.access_token_required),
        redis: Redis = Depends(get_cache)):
    """Зависимость для защищённых ручек: токен валиден И не отозван."""
    token = credentials.credentials
    payload: TokenPayload = security.verify_token(token)
    if await redis.exists(_denylist_key(token, payload)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен отозван",
        )
    return payload
