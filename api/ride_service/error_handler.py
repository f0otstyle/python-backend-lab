from fastapi import HTTPException
from http import HTTPStatus


class OrderError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=HTTPStatus.CONFLICT,
            detail='Заказ с таким адресом существует'
            )


class SearchError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Данного заказа не существует'
            )
