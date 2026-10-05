from .constants import BASE_URL
import pytest


@pytest.mark.smoke
def test_ordering_a_taxi(order_fixture):
    response = order_fixture['response']
    cookie = order_fixture['cookies']
    session = order_fixture['session']

    order_id = response.json()["id"]

    result = session.get(f'{BASE_URL}/taxi/{order_id}',
                         cookies={"my_cookie": cookie}
                         )
    assert result.status_code == 200

    result = session.delete(f'{BASE_URL}/taxi/{order_id}',
                            cookies={"my_cookie": cookie}
                            )
    assert result.status_code == 204

    result = session.get(f'{BASE_URL}/taxi/{order_id}',
                         cookies={"my_cookie": cookie}
                         )
    assert result.status_code == 404
