from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import requests
import time

A = [100000, 2000000, 4000000, 5000000, 6000000]

URL = ['https://httpbin.org/delay/1',
       'https://httpbin.org/delay/2',
       'https://httpbin.org/delay/3',
       'https://httpbin.org/delay/4',
       'https://httpbin.org/delay/5',
       'https://httpbin.org/delay/6',
       'https://httpbin.org/delay/7',
       'https://httpbin.org/delay/8',
       'https://httpbin.org/delay/9']


def benchmark(name, func):
    start = time.perf_counter()
    result = func()
    elapsed = time.perf_counter() - start
    print(f'{name:<20} {elapsed:.2f} с')
    return result


def benchmark_cpu(n: int):
    return sum(i * i for i in range(n))


def benchmark_i_o(url: str):
    response = requests.get(url)
    return response.status_code


if __name__ == '__main__':
    print('CPU-bound задания')
    benchmark('Однопоточность', lambda: list(map(benchmark_cpu, A)))

    with ThreadPoolExecutor(max_workers=5) as executor:
        benchmark('Многопоточность', lambda: list(executor.map(benchmark_cpu, A)))

    with ProcessPoolExecutor(max_workers=5) as executor:
        benchmark('Многопроцессорность', lambda: list(executor.map(benchmark_cpu, A)))

    print('CPU-bound задания используя больше ядер')

    with ProcessPoolExecutor(max_workers=5) as executor:
        benchmark('Многопроцессорность на 5 ядрах', lambda: list(executor.map(benchmark_cpu, A)))

    with ProcessPoolExecutor(max_workers=10) as executor:
        benchmark('Многопроцессорность на 10 ядрах', lambda: list(executor.map(benchmark_cpu, A)))

    with ProcessPoolExecutor(max_workers=40) as executor:
        benchmark('Многопроцессорность на 40 ядрах', lambda: list(executor.map(benchmark_cpu, A)))

    with ProcessPoolExecutor(max_workers=61) as executor:
        benchmark('Многопроцессорность на 80 ядрах', lambda: list(executor.map(benchmark_cpu, A)))

    print('I/O-bound задания')
    benchmark('Однопоточность', lambda: list(map(benchmark_i_o, URL)))

    with ThreadPoolExecutor(max_workers=5) as executor:
        benchmark('Многопоточность', lambda: list(executor.map(benchmark_i_o, URL)))

    with ProcessPoolExecutor(max_workers=5) as executor:
        benchmark('Многопроцессорность', lambda: list(executor.map(benchmark_i_o, URL)))
