from contextlib import contextmanager
from time import perf_counter, sleep
import tracemalloc
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger('generators')

# № 1 Генератор читает файл кусками, не загружая целиком и сравни память с наивным `f.read()`
def read_large_file(path, chunk_size):
    with open(path, "rb") as f:
        while True:
            file = f.read(chunk_size)
            if not file:
                break
            yield file


def read_file(path):
    with open(path, "rb") as f:
        data = f.read()

    return data


with open("test.txt", "wb") as f:
    f.write(b"0" * (50 * 1024 * 1024))


# № 2 - создаем кастомный класс контекстного менеджера
class Timer:
    def __init__(self):
        self.start = None
        self.end_start = None

    def __enter__(self):
        self.start = perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.end_start = perf_counter() - self.start
        logger.info(f'Время выполнения функции равна {self.end_start:.2f} с')


def func_sleep_1():
    timer = Timer()
    with timer:
        sleep(2)


# № 2 - создаем контекстный менеджера на основе декоратора
@contextmanager
def timer():
    start = perf_counter()
    try:
        yield
    finally:
        end_start = perf_counter() - start
        logger.info(f'Время выполнения функции равна {end_start:.2f} с')


def func_sleep_2():
    with timer():
        sleep(2)


# № 3 - отдаёт элементы пачками по n
def batched(iterable, n):
    arr = []
    for iter in iterable:
        arr.append(iter)
        if len(arr) == n:
            yield arr
            arr = []
    if arr:
        yield arr

# --------------------------
# Проверка вложенных функций
# --------------------------


def make_counter_1():
    count = 0

    def outer():
        count += 1
        return count

    return outer


def make_counter_2():
    count = 0

    def outer():
        nonlocal count
        count += 1
        return count

    return outer

# ===================================
# Контекстный менеджер
# ===================================
def mycontextmanager_1():
    f = open('test.txt', 'w')
    try:
        f.write('Hello')
        raise ValueError("Ошибка!")
    finally:
        f.close()


def mycontextmanager_2():
    try:
        with open('test.txt', 'w') as f:
            f.write('Hello')
            raise ValueError("Ошибка!")
    except ValueError as e:
        print(f"Поймали исключение: {e}")


if __name__ == '__main__':
    tracemalloc.start()
    start = perf_counter()
    data = read_file("test.txt")
    logger.info(f"Целиком: {perf_counter() - start:.4f} с, память: {tracemalloc.get_traced_memory()[1] / 1024 / 1024:.2f} МБ")
    tracemalloc.stop()

    tracemalloc.start()
    start = perf_counter()
    total = 0
    for chunk in read_large_file("test.txt", 4096):
        total += len(chunk)
    logger.info(f"По частям: {perf_counter() - start:.4f} с, память: {tracemalloc.get_traced_memory()[1] / 1024 / 1024:.2f} МБ")
    tracemalloc.stop()

    func_sleep_1()
    func_sleep_2()

    iterable = [i for i in range(11)]
    for i in batched(iterable, 3):
        print(i)

        counter_1 = make_counter_1()
    try:
        print(counter_1())
    except UnboundLocalError:
        print('Ошибка: UnboundLocalError')

    counter_2 = make_counter_2()
    print(counter_2())
    print(counter_2())
    print(mycontextmanager_2())
    print(mycontextmanager_1())
