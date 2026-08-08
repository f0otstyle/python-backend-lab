from server import app
from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def test_client():
    return TestClient(app)


def test_registrate_and_login_and_get_login(test_client: TestClient):
    user = {'username': 'Саша',
            'password': '1234'}

    # 1.Проверка регистрации
    register_response = test_client.post('/registerate', json=user)
    assert register_response.status_code == 201
    register_body = register_response.json()
    assert register_body == {"message": "Пользователь создан"}

    # 2.Процерка аунтификации
    login_response = test_client.post('/login', json=user)
    assert login_response.status_code == 200
    login_body = login_response.json()
    assert login_body == {"message": "Успешный вход"}

    # 3.Проверка авторизации
    get_login_response = test_client.get('/get_login')
    assert get_login_response.status_code == 200
    get_login_body = get_login_response.json()
    assert get_login_body == {'data': 'Вы авторизованы'}
