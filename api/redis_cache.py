from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis
import json

DATABASE_URL_redis = 'redis://redis:6379'


LUA_SET_HASH = '''
    local ttl = tonumber(ARGV[#ARGV])
    for i = 1, #ARGV - 1, 2 do
        redis.call('HSET', KEYS[1], ARGV[i], ARGV[i + 1])
    end
    if ttl > 0 then
         redis.call('EXPIRE', KEYS[1], ttl)
    end
    return 'OK'
    '''


class RedisCachedBackend:
    def __init__(self, cache_ttl_seconds: int | None):
        self.redis = Redis.from_url(
            DATABASE_URL_redis,
            decode_responses=True
            )
        self.cache_ttl_seconds = cache_ttl_seconds
        self.set_hash_script = self.redis.register_script(LUA_SET_HASH)
        self.prefix = 'taxi'

    def _make_key(self, entity: str, identifier: str | int) -> str:
        return f'{self.prefix}:{entity}:{identifier}'

    async def set_json(self,
                       entity: str,
                       identifier: str | int,
                       value: dict | list[dict],
                       ex_time: int | None
                       ):
        key = self._make_key(entity=entity, identifier=identifier)
        serializable_value = jsonable_encoder(value)
        ttl_cache = ex_time if ex_time else self.cache_ttl_seconds
        await self.redis.set(key, json.dumps(serializable_value), ex=ttl_cache)
        return key

    async def get_json(self,
                       entity: str,
                       identifier: str | int
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
        flat = {k: (v if isinstance(v, str) else json.dumps(
            v,
            ensure_ascii=False
            ))
                for k, v in value.items()}

        args = []
        for field, val in flat.items():
            args.extend([field, val])
        args.append(self.cache_ttl_seconds or 0)

        await self.set_hash_script(keys=[key], args=args)
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
                val if isinstance(val, str) else json.dumps(
                    val,
                    ensure_ascii=False
                    ),
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

    async def delete_json(self,
                          entity: str,
                          identifier: str | int
                          ):
        key = self._make_key(entity, identifier)
        await self.redis.delete(key)
