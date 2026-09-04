from fastapi.testclient import TestClient
from taxi_api import app
import pytest

USER = {'username': 'Саша',
        'password': '1234'}


@pytest.fixture
def test_client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def test_user(test_client: TestClient):

    registrate_response = test_client.post('/registrate', json=USER)
    if registrate_response.status_code == 400:
        return 1
    elif registrate_response.status_code == 201:
        return 1


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
    login_response = test_client.post('/login', json=USER)
    assert login_response.status_code == 200
    result = test_client.post(
            '/taxi',
            json=request_data,
            headers=headers
        )
    body = result.json()
    assert result.status_code == 201
    assert isinstance(body["from_address"], str)
    assert isinstance(body["to_address"], str)
    assert isinstance(body["price"], int)
    assert body["price"] == 10
    assert body["to_address"] == 'Ватутино'
    assert body["from_address"] == 'Маркса 6/1'


def test_order_search(test_client: TestClient, test_user):
    request_data = {
                'from_address': 'Маркса 6/1',
                'to_address': 'Ватутино',
                'price': 10
        }
    headers = {
            "Idempotency-Key": "123"
        }

    login_response = test_client.post('/login', json=USER)
    assert login_response.status_code == 200

    result = test_client.post(
            '/taxi',
            json=request_data,
            headers=headers
        )
    assert result.status_code == 201

    order_id = result.json()["id"]

    result = test_client.get(f'/taxi/{order_id}')
    assert result.status_code == 200


def test_idempotency(test_client: TestClient, test_user):
    request_data = {
                    'from_address': 'Маркса 6/1',
                    'to_address': 'Ватутино',
                    'price': 10
            }
    headers = {
            "Idempotency-Key": "123"
        }

    login_response = test_client.post('/login', json=USER)
    assert login_response.status_code == 200

    responce_one = test_client.post(
            '/taxi',
            json=request_data,
            headers=headers
        )
    responce_one_id = responce_one.json()['id']
    assert responce_one.status_code == 201

    responce_two = test_client.post(
                '/taxi',
                json=request_data,
                headers=headers
            )
    responce_two_id = responce_two.json()['id']
    assert responce_two.status_code == 201
    assert responce_one_id == responce_two_id


def test_order_delete(test_client: TestClient, test_user):
    request_data = {
                'from_address': 'Маркса 6/1',
                'to_address': 'Ватутино',
                'price': 10
        }
    headers = {
            "Idempotency-Key": "123"
        }

    login_response = test_client.post('/login', json=USER)
    assert login_response.status_code == 200

    result = test_client.post(
            '/taxi',
            json=request_data,
            headers=headers
        )
    assert result.status_code == 201

    order_id = result.json()["id"]

    result = test_client.delete(f'/taxi/{order_id}')
    assert result.status_code == 204

    result = test_client.get(f'/taxi/{order_id}')
    assert result.status_code == 404


def test_history_order_taxi(test_client: TestClient, test_user):
    login_response = test_client.post('/login', json=USER)
    assert login_response.status_code == 200

    result = test_client.get('/history/')
    assert result.status_code == 200
