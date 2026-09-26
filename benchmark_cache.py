import asyncio
import time
import aiohttp


N = 50


async def one_request(session, semaphore):
    async with semaphore:
        start = time.perf_counter()
        async with session.get('http://127.0.0.1:8080/taxi/1') as resp:
            await resp.text()
        return (time.perf_counter() - start) * 1000


async def run(n):
    latencies = []
    semaphore = asyncio.Semaphore(50)
    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [one_request(session, semaphore) for _ in range(n)]
        latencies = await asyncio.gather(*tasks)
    return latencies


async def main():
    latencies = await run(N)
    latencies.sort()

    print(f'запросов: {len(latencies)}')
    print(f'mean:  {sum(latencies) / len(latencies):.2f} мс')
    print(f'p50:   {latencies[len(latencies) // 2]:.2f} мс')
    print(f'p95:   {latencies[int(len(latencies) * 0.95)]:.2f} мс')
    print(f'max:   {max(latencies):.2f} мс')


if __name__ == '__main__':
    asyncio.run(main())
