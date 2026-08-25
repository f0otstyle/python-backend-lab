from fastapi.testclient import TestClient
from taxi_api import app
import pytest


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def test_user(test_client: TestClient):
    user = {'username': 'Саша',
            'password': '1234'}

    registrate_response = test_client.post('/registrate', json=user)
    assert registrate_response.status_code == 201
    user_id = 1
    return user_id


def test_list_of_orders(test_client: TestClient):
    result = test_client.get('/taxi')

    assert result.status_code == 200


def test_taxi_drivers(test_client: TestClient):
    request_data = {
            "name": "Саша",
            "car": "BMW"
        }
    result = test_client.post(
            '/drivers',
            json=request_data,
        )
    body = result.json()

    assert result.status_code == 201
    assert isinstance(body["name"], str)
    assert isinstance(body["car"], str)
    assert body["name"] == "Саша"
    assert body["car"] == "BMW"


def test_top_up_your_card(test_client: TestClient, test_user):
    request_data = {
        'money': 200.0
    }

    user_id = test_user
    result = test_client.post(f'/pay/{user_id}', json=request_data)
    assert result.status_code == 200


def test_ordering_a_taxi(test_client: TestClient, test_user):
    request_data = {
            'from_address': 'Маркса 6/1',
            'to_address': 'Ватутино',
            'price': 10
    }
    headers = {
            "Idempotency-Key": "123"
        }
    result = test_client.post(
            '/taxi',
            json=request_data,
            headers=headers
        )
    body = result.json()
    assert result.status_code == 201
