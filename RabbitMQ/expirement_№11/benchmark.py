import httpx
import time
import asyncio


URL = "http://localhost:8080/taxi"
LOGIN_URL = "http://localhost:8080/login"
REGISTR_URL = "http://localhost:8080/registrate"
USERNAME = 'test_bench_user'
PASSWORD = "12344"


async def get_token(client: httpx.AsyncClient):
    try:
        await client.post(REGISTR_URL, json={"username": USERNAME, "password": PASSWORD})
    except Exception:
        pass

    response = await client.post(LOGIN_URL, json={
        "username": USERNAME,
        "password": PASSWORD
    })
    if response.status_code != 200:
        raise Exception(f"Не удалось получить токен: {response.text}")
    response = await client.post(LOGIN_URL, json={
            "username": USERNAME,
            "password": PASSWORD
        })

    token = response.cookies.get("my_cookie")
    return token


async def make_request(
        client: httpx.AsyncClient,
        i: int,
        semaphore: asyncio.Semaphore,
        token: str
        ):
    async with semaphore:
        headers = {
                    "Content-Type": "application/json",
                    "Cookie": f"my_cookie={token}",
                    "Idempotency-Key": f"bench-{i}-{time.time_ns()}"
                }
        payload = {
                    "from_address": f"ул. Ленина {i}",
                    "to_address": f"ул. Пушкина {i}",
                    "price": 100
                }
        start = time.perf_counter()
        try:
            response = await client.post(URL, json=payload, headers=headers)
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed, response.status_code
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed, 0


async def main():
    semaphore = asyncio.Semaphore(10)
    async with httpx.AsyncClient() as client:
        token = await get_token(client)
        start_total = time.perf_counter()
        tasks = [make_request(client, i, semaphore, token) for i in range(100)]
        results = await asyncio.gather(*tasks)
        total_time = (time.perf_counter() - start_total) * 1000

    success_times = sorted(result[0] for result in results if result[1] == 201)
    failed_count = sum(1 for result in results if result[1] != 201)
    p50 = success_times[int(len(success_times) * 0.5)]
    p95 = success_times[int(len(success_times) * 0.95)]
    p99 = success_times[int(len(success_times) * 0.99)]
    max_time = max(success_times)
    min_time = min(success_times)
    print("\n" + "=" * 50)
    print(f"РЕЗУЛЬТАТЫ ({len(success_times)} успешных, {failed_count} ошибок)")
    print("=" * 50)
    print(f"  Min:        {min_time:.2f} мс")
    print(f"  P50:        {p50:.2f} мс")
    print(f"  P95:        {p95:.2f} мс")
    print(f"  P99:        {p99:.2f} мс")
    print(f"  Max:        {max_time:.2f} мс")
    print(f"  Total time: {total_time:.0f} мс")
    print("=" * 50)


if __name__ == '__main__':
    asyncio.run(main())
