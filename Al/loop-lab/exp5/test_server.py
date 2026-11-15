"""Тесты стенда «нестабильного сервиса» (exp5).

Реального HTTP нет: fastapi.testclient.TestClient вызывает ASGI-приложение
в памяти - ни сокетов, ни живого сервера. Чистое состояние для каждого теста
даёт фабрика create_app(): у каждого экземпляра приложения свой счётчик
отказов /flaky, поэтому тесты не влияют друг на друга.
"""
import sys
from pathlib import Path

# pytest берёт pythonpath=["."] из pyproject.toml в корне песочницы и
# подсовывает чужой server.py, лежащий выше по дереву. Ставим папку этого
# теста в начало sys.path, чтобы `import server` взял именно наш стенд.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from server import FAILS_N, create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """Свежий стенд с чистым счётчиком /flaky на каждый тест."""
    return TestClient(create_app())


def test_fails_n_is_three():
    """По SPEC стенд должен «отказывать» ровно первые 3 запроса."""
    assert FAILS_N == 3


def test_flaky_503_exact_fails_n_then_200(client: TestClient):
    """Первые FAILS_N запросов - 503 (тело-словарь с пояснением), затем 200.

    После стабилизации сервис продолжает отвечать 200 на все следующие
    запросы - «ровно N отказов», не больше и не меньше.
    """
    # фаза отказов: /flaky ещё «греется»
    for request_no in range(1, FAILS_N + 1):
        resp = client.get('/flaky')
        assert resp.status_code == 503, (
            f'запрос {request_no}/{FAILS_N}: ожидал 503, пришёл {resp.status_code}'
        )
        body = resp.json()
        assert isinstance(body, dict), 'тело 503 должно быть словарём'
        assert body.get('detail'), 'в теле 503 нужно пояснение (ключ detail)'

    # фаза стабильности: 200 и продолжает 200
    for request_no in range(1, 4):
        resp = client.get('/flaky')
        assert resp.status_code == 200, (
            f'запрос {request_no} после стабилизации: ожидал 200, '
            f'пришёл {resp.status_code}'
        )
        assert isinstance(resp.json(), dict)


def test_health_is_ok(client: TestClient):
    """/health как в exp1: 200 и {"status": "ok"}."""
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.json() == {'status': 'ok'}


def test_health_works_while_flaky_is_failing(client: TestClient):
    """/health живёт всегда - даже пока /flaky ещё отдаёт 503."""
    assert client.get('/flaky').status_code == 503
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.json() == {'status': 'ok'}


def test_fresh_app_resets_fails_counter():
    """Фабрика create_app() даёт чистый счётчик: новый стенд снова отказывает.

    Старый экземпляр уже стабилен, но у нового приложения счётчик свой -
    именно поэтому каждый тест получает стенда в исходном состоянии.
    """
    warmed_up = TestClient(create_app())
    for _ in range(FAILS_N):
        warmed_up.get('/flaky')
    assert warmed_up.get('/flaky').status_code == 200  # старый стенд стабилен

    fresh = TestClient(create_app())
    assert fresh.get('/flaky').status_code == 503, (
        'новый экземпляр приложения должен начинать с чистого счётчика'
    )
