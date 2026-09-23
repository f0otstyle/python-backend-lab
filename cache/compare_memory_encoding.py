import asyncio

from cache.redis import RedisCachedBackend


async def main():
    cache = RedisCachedBackend(cache_ttl_seconds=3600)

    order = {
        "username": "Саша",
        "from_address": "Ватутино",
        "to_address": "Немировича",
        "driver_name": "Виталий",
        "driver_car": "KIA K5",
        "price": 123
    }

    k_json = await cache.set_json("order", "ORD-001:json", order)
    k_hash = await cache.set_hash("order", "ORD-001:hash", order)
    k_sep = await cache.set_separate("order", "ORD-001:sep", order)

    report = await cache.compare([k_json, k_hash] + k_sep)
    for row in report:
        print(row)


if __name__ == '__main__':
    asyncio.run(main())
