from functools import wraps
import time


def timers(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        time_start = time.perf_counter()
        await func(*args, **kwargs)
        time_result = time.perf_counter() - time_start
        print(f"Задача обработалась за {time_result*1000:.2f} мс")
        return time_result

    return wrapper
