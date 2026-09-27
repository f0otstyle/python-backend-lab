from redis.asyncio import Redis
from time import time
import random

DATABASE_URL_redis = 'redis://redis:6379'


class Ratelimit:
    def __init__(self):
        self.redis = Redis.from_url(
                    DATABASE_URL_redis,
                    decode_responses=True
                )
        self.prefix = 'rate_limite'

    def _make_key(self, entity: str, identifier: str | int) -> str:
        return f'{self.prefix}:{entity}:{identifier}'

    async def is_limited(
            self,
            identifier: str | int,
            endpoint: str,
            max_request: int,
            window_seconds: int
    ):
        key = self._make_key(entity=endpoint, identifier=identifier)

        current_ms = time() * 1000
        window_start_ms = current_ms - window_seconds * 1000

        current_request = f"{time() * 1000}-{random.randint(0, 100_000)}"

        async with self.redis.pipeline() as pipe:
            await pipe.zremrangebyscore(key, 0, window_start_ms)

            await pipe.zcard(key)

            await pipe.zadd(key, {current_request: current_ms})

            await pipe.expire(key, window_seconds)

            res = await pipe.execute()

        _, current_count, _, _ = res
        if current_count >= max_request:
            return True
