from time import perf_counter
import requests


URL = 'http://127.0.0.1:8000/health'


def log(func):
    def wrapper(*args, **kwargs):
        start = perf_counter()
        res = func(*args, **kwargs)
        end_start = perf_counter() - start
        print(f'Время выполнения {func.__name__}: {end_start:.4f}')
        return res

    return wrapper


@log
def test_requests():
    for i in range(20):
        start = perf_counter()
        response = requests.get(URL)
        end_start = perf_counter() - start
        print(f'Запрос №{i} выполнился за время {end_start:.4f} со статусом {response.status_code}')


@log
def test_session():
    with requests.session() as session:
        for i in range(20):
            start = perf_counter()
            response = session.get(URL)
            end_start = perf_counter() - start
            print(f'Запрос №{i} выполнился за время {end_start:.4f} со статусом {response.status_code}')


if __name__ == '__main__':
    print('Первый запуск с использованием requests')
    test_requests()
    print('Второй запуск с использованием session')
    test_session()
