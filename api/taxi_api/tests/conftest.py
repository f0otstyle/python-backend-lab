from .constants import BASE_URL, USER
import uuid
import requests
import pytest


@pytest.fixture
def test_user():

    registrate_response = requests.post(f'{BASE_URL}/registrate', json=USER)
    if registrate_response.status_code == 400:
        return 1
    elif registrate_response.status_code == 201:
        return 1


@pytest.fixture
def order_fixture(test_user):
    unique = uuid.uuid4().hex[:8]
    request_data = {
                'from_address': f'Маркса {unique}',
                'to_address': f'Ватутино {unique}',
                'price': 350
        }
    headers = {
                "Idempotency-Key": str(uuid.uuid4())
            }
    session = requests.Session()
    login_response = session.post(f'{BASE_URL}/login', json=USER)
    assert login_response.status_code == 200

    cookie = session.cookies.get("my_cookie")

    result = session.post(
            f'{BASE_URL}/taxi',
            json=request_data,
            headers=headers,
            cookies={"my_cookie": cookie}
        )

    return {
        'response': result,
        'request_data': request_data,
        'headers': headers,
        'cookies': cookie,
        'session': session
        }
