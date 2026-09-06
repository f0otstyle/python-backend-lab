import uuid
import requests
import pytest

USER = {'username': 'Саша',
        'password': '1234'}

BASE_URL = "http://localhost:8080"


@pytest.fixture
def test_user():

    registrate_response = requests.post(f'{BASE_URL}/registrate', json=USER)
    if registrate_response.status_code == 400:
        return 1
    elif registrate_response.status_code == 201:
        return 1


def test_list_of_orders():
    result = requests.get(f'{BASE_URL}/taxi')

    assert result.status_code == 200


def test_taxi_drivers():
    request_data = {
            "name": "Саша",
            "car": "BMW"
        }
    result = requests.post(
            f'{BASE_URL}/drivers',
            json=request_data,
        )
    body = result.json()

    assert result.status_code == 201
    assert isinstance(body["name"], str)
    assert isinstance(body["car"], str)
    assert body["name"] == "Саша"
    assert body["car"] == "BMW"


def test_top_up_your_card(test_user):
    request_data = {
        'money': 200.0
    }
    user_id = test_user

    with requests.Session() as session:
        login_response = session.post(f'{BASE_URL}/login', json=USER)
        assert login_response.status_code == 200
        cookie = session.cookies.get("my_cookie")

        result = session.post(f'{BASE_URL}/pay/{user_id}', json=request_data)
        assert result.status_code == 401

        result = session.post(f'{BASE_URL}/pay/{user_id}',
                              json=request_data,
                              cookies={"my_cookie": cookie})
        assert result.status_code == 200


def test_ordering_a_taxi(test_user):
    request_data = {
            'from_address': 'Маркса 6/1',
            'to_address': 'Ватутино',
            'price': 10
    }
    headers = {
            "Idempotency-Key": str(uuid.uuid4())
        }
    with requests.Session() as session:
        login_response = session.post(f'{BASE_URL}/login', json=USER)
        assert login_response.status_code == 200

        cookie = session.cookies.get("my_cookie")

        result = session.post(
                f'{BASE_URL}/taxi',
                json=request_data,
                headers=headers,
                cookies={"my_cookie": cookie}
            )
        body = result.json()
        assert result.status_code == 201
        assert isinstance(body["from_address"], str)
        assert isinstance(body["to_address"], str)
        assert body["price"] == 10
        assert body["to_address"] == 'Ватутино'
        assert body["from_address"] == 'Маркса 6/1'


def test_order_search(test_user):
    request_data = {
                'from_address': 'Маркса 6/1',
                'to_address': 'Ватутино',
                'price': 10
        }
    headers = {
            "Idempotency-Key": str(uuid.uuid4())
        }
    with requests.Session() as session:
        login_response = session.post(f'{BASE_URL}/login', json=USER)
        assert login_response.status_code == 200
        cookie = session.cookies.get("my_cookie")

        result = session.post(
                f'{BASE_URL}/taxi',
                json=request_data,
                headers=headers,
                cookies={"my_cookie": cookie}
            )
        assert result.status_code == 201

        order_id = result.json()["id"]

        result = session.get(f'{BASE_URL}/taxi/{order_id}',
                             cookies={"my_cookie": cookie}
                             )
        assert result.status_code == 200

        order_id = 100000
        result = session.get(f'{BASE_URL}/taxi/{order_id}',
                             cookies={"my_cookie": cookie}
                             )
        assert result.status_code == 404


def test_idempotency(test_user):
    request_data = {
                    'from_address': 'Маркса 6/1',
                    'to_address': 'Ватутино',
                    'price': 10
            }
    headers = {
            "Idempotency-Key": str(uuid.uuid4())
        }

    with requests.Session() as session:
        login_response = session.post(f'{BASE_URL}/login', json=USER)
        assert login_response.status_code == 200
        cookie = session.cookies.get("my_cookie")

        responce_one = session.post(
                f'{BASE_URL}/taxi',
                json=request_data,
                headers=headers,
                cookies={"my_cookie": cookie}
            )
        responce_one_id = responce_one.json()['id']
        assert responce_one.status_code == 201

        responce_two = session.post(
                    f'{BASE_URL}/taxi',
                    json=request_data,
                    headers=headers,
                    cookies={"my_cookie": cookie}
                )
        responce_two_id = responce_two.json()['id']
        assert responce_two.status_code == 201
        assert responce_one_id == responce_two_id


def test_order_delete(test_user):
    request_data = {
                'from_address': 'Маркса 6/1',
                'to_address': 'Ватутино',
                'price': 10
        }
    headers = {
            "Idempotency-Key": str(uuid.uuid4())
        }

    with requests.Session() as session:
        login_response = session.post(f'{BASE_URL}/login', json=USER)
        assert login_response.status_code == 200

        result = session.post(
                        f'{BASE_URL}/taxi',
                        json=request_data,
                        headers=headers,
                    )
        assert result.status_code == 401

        cookie = session.cookies.get("my_cookie")

        result = session.post(
                f'{BASE_URL}/taxi',
                json=request_data,
                headers=headers,
                cookies={"my_cookie": cookie}
            )
        assert result.status_code == 201

        order_id = result.json()["id"]

        result = session.delete(f'{BASE_URL}/taxi/{order_id}',
                                cookies={"my_cookie": cookie}
                                )
        assert result.status_code == 204

        result = session.get(f'{BASE_URL}/taxi/{order_id}',
                             cookies={"my_cookie": cookie}
                             )
        assert result.status_code == 404


def test_history_order_taxi(test_user):
    with requests.Session() as session:
        login_response = session.post(f'{BASE_URL}/login', json=USER)
        assert login_response.status_code == 200
        cookie = session.cookies.get("my_cookie")

        result = session.get(f'{BASE_URL}/history',
                             cookies={"my_cookie": cookie}
                             )
        assert result.status_code == 200


def test_unsupported_media_type():
    with requests.Session() as session:
        session.post(f'{BASE_URL}/registrate', json=USER)
        session.post(f'{BASE_URL}/login', json=USER)
        cookie = session.cookies.get("my_cookie")

        response = requests.post(
            f'{BASE_URL}/taxi',
            data="not json",
            headers={"Content-Type": "text/plain"},
            cookies={"my_cookie": cookie}
        )
        assert response.status_code == 422
