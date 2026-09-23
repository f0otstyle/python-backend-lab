import asyncio
from cache.redis import RedisCachedBackend


ORDER = {
    "username": "Саша",
    "from_address": "Ватутино",
    "to_address": "Немировича",
    "driver_name": "Виталий",
    "driver_car": "KIA K5",
    "price": 123,
}

N = 100_000


async def measure(cache, label, write_fn):
    await cache.flushall()
    await asyncio.sleep(1)
    before = await cache.info_memory()

    for i in range(N):
        await write_fn(i)

    await asyncio.sleep(1)
    after = await cache.info_memory()
    print(f"{label}: before={before}, after={after}, delta={after - before}")


async def main():
    cache = RedisCachedBackend(cache_ttl_seconds=3600)

    await measure(cache, "JSON",
        lambda i: cache.set_json(f"json:order:{i}", f"ORD-{i:06d}", ORDER))

    await measure(cache, "HASH",
        lambda i: cache.set_hash(f"hash:order:{i}", f"ORD-{i:06d}", ORDER))

    await measure(cache, "SEPARATE",
        lambda i: cache.set_separate(f"sep:order:{i}", f"ORD-{i:06d}", ORDER))


if __name__ == "__main__":
    asyncio.run(main())
