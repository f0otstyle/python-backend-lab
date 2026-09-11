from .constants import BASE_URL, USER
import pytest
import requests


@pytest.mark.smoke
@pytest.mark.parametrize("name, car", [
            ("Саша", "BMW"),
            ("Мария", "Toyota"),
        ])
def test_taxi_drivers(name, car):
    request_data = {
            "name": name,
            "car": car
        }
    result = requests.post(
            f'{BASE_URL}/drivers',
            json=request_data,
        )
    body = result.json()

    assert result.status_code == 201
    assert isinstance(body["name"], str)
    assert isinstance(body["car"], str)
    assert body["name"] == name
    assert body["car"] == car


@pytest.mark.smoke
@pytest.mark.parametrize("money", [
            200.0, 12.3
        ])
def test_top_up_your_card(money, test_user):
    request_data = {
        'money': money
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


def test_ordering_a_taxi(order_fixture):
    response = order_fixture['response']
    request_data = order_fixture['request_data']

    body = response.json()
    assert response.status_code == 201
    assert isinstance(body["from_address"], str)
    assert isinstance(body["to_address"], str)
    assert body["price"] == request_data['price']
    assert body["to_address"] == request_data['to_address']
    assert body["from_address"] == request_data['from_address']


def test_order_search(order_fixture):
    response = order_fixture['response']
    cookie = order_fixture['cookies']
    session = order_fixture['session']

    order_id = response.json()["id"]

    result = session.get(f'{BASE_URL}/taxi/{order_id}',
                         cookies={"my_cookie": cookie}
                         )
    assert result.status_code == 200

    order_id = 100000
    result = session.get(f'{BASE_URL}/taxi/{order_id}',
                         cookies={"my_cookie": cookie}
                         )
    assert result.status_code == 404


def test_idempotency(order_fixture):
    headers = order_fixture['headers']
    request_data = order_fixture['request_data']
    cookie = order_fixture['cookies']
    session = order_fixture['session']

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


def test_order_delete(order_fixture):
    response = order_fixture['response']
    cookie = order_fixture['cookies']
    session = order_fixture['session']

    order_id = response.json()["id"]

    result = session.delete(f'{BASE_URL}/taxi/{order_id}',
                            cookies={"my_cookie": cookie}
                            )
    assert result.status_code == 204

    result = session.get(f'{BASE_URL}/taxi/{order_id}',
                         cookies={"my_cookie": cookie}
                         )
    assert result.status_code == 404
