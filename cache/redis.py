from redis.asyncio import Redis
import json

DATABASE_URL_redis = 'redis://localhost:6379'


class RedisCachedBackend:
    def __init__(self, cache_ttl_seconds: int | None):
        self.redis = Redis.from_url(
            DATABASE_URL_redis,
            decode_responses=True
            )
        self.cache_ttl_seconds = cache_ttl_seconds
        self.prefix = 'taxi'

    def _make_key(self, entity: str, identifier: str) -> str:
        return f'{self.prefix}:{entity}:{identifier}'

    async def set_json(self,
                       entity: str,
                       identifier: str,
                       value: dict | list[dict]
                       ):
        key = self._make_key(entity=entity, identifier=identifier)
        await self.redis.set(key, json.dumps(value), ex=self.cache_ttl_seconds)
        return key

    async def get_json(self,
                       entity: str,
                       identifier: str
                       ) -> dict | list[dict] | None:
        key = self._make_key(entity, identifier)
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_hash(self,
                       entity: str,
                       identifier: str,
                       value: dict | list[dict]
                       ):
        key = self._make_key(entity, identifier)
        flat = {k: (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
                for k, v in value.items()}
        await self.redis.hset(key, mapping=flat)
        if self.cache_ttl_seconds is not None:
            await self.redis.expire(key, self.cache_ttl_seconds)
        return key

    async def get_hash(self, entity: str, identifier: str):
        key = self._make_key(entity, identifier)
        data = await self.redis.hgetall(key)
        return data or None

    async def set_separate(self, entity: str, identifier: str,
                           value: dict) -> list[str]:
        keys = []
        for field, val in value.items():
            key = self._make_key(entity, f'{identifier}:{field}')
            await self.redis.set(
                key,
                val if isinstance(val, str) else json.dumps(val, ensure_ascii=False),
                ex=self.cache_ttl_seconds,
            )
            keys.append(key)
        return keys

    async def get_separate(self, entity: str, identifier: str,
                           fields: list[str]) -> dict:
        result = {}
        for field in fields:
            key = self._make_key(entity, f'{identifier}:{field}')
            result[field] = await self.redis.get(key)
        return result

    async def compare(self, keys: list[str]) -> list[dict]:
        report = []
        for key in keys:
            if not await self.redis.exists(key):
                report.append({"key": key, "exists": False})
                continue
            report.append({
                "key": key,
                "exists": True,
                "type": await self.redis.type(key),
                "encoding": await self.redis.object("encoding", key),
                "memory_usage": await self.redis.memory_usage(key),
            })
        return report

    async def flushall(self) -> None:
        await self.redis.flushall()

    async def info_memory(self) -> int:
        info = await self.redis.info("memory")
        return info["used_memory"]
