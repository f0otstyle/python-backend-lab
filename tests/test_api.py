from fastapi.testclient import TestClient
from order_api import app
import pytest


@pytest.fixture
def test_client():
    return TestClient(app)


def test_list_of_orders(test_client: TestClient):
    result = test_client.get('/taxi')

    assert result.status_code == 200


def test_ordering_a_taxi(test_client: TestClient):
    request_data = {
        "Location": "Карла Маркса 6/1"
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
    assert body["id"] >= 1
    assert body["Location"] == 'Карла Маркса 6/1'
    assert isinstance(body["Location"], str)
    assert isinstance(body["Idempotency-Key"], str)
    assert isinstance(body["CreatedAt"], (int, float))

    order_id = body["id"]

    search_response = test_client.get(f'/taxi/{order_id}')

    order = search_response.json()

    assert order["id"] == order_id
    assert order["Location"] == "Карла Маркса 6/1"
    assert order["Idempotency-Key"] == "123"


def test_order_search_not_found(test_client: TestClient):
    result = test_client.get('/taxi/999')

    assert result.status_code in [400, 404]


def test_order_search_invalid_id(test_client: TestClient):
    result = test_client.get('/taxi/a')

    assert result.status_code == 422


def test_delete_order(test_client: TestClient):
    request_data = {
            "Location": "Карла Маркса 6/1"
        }

    headers = {
            "Idempotency-Key": "123"
        }
    result = test_client.post(
            '/taxi',
            json=request_data,
            headers=headers
        )

    assert result.status_code == 201
    body = result.json()

    order_id = body['id']

    delete_result = test_client.delete(f'/taxi/{order_id}')
    assert delete_result.status_code == 204

    get_result = test_client.get(f'/taxi/{order_id}')
    assert get_result.status_code == 404
