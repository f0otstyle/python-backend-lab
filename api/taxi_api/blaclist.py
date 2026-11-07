from redis.asyncio import Redis


class BlacklistRedis:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.prefix = 'blaclist'

    async def __make_key(self, user_id: int):
        return f'taxi:{self.prefix}:{user_id}'

    async def set_user_blaclist(self, user_id: int):
        key = await self.__make_key(user_id)
        return await self.redis.set(key, user_id)

    async def get_user_blaclist(self, user_id: int):
        key = await self.__make_key(user_id)
        return await self.redis.get(key)

    async def delete_user_blaclist(self, user_id: int):
        key = await self.__make_key(user_id)
        return await self.redis.delete(key)
