from fastapi import FastAPI, Request
from pydantic import BaseModel
from contextlib import asynccontextmanager
from uuid import uuid4
from rabbitmq import (connect_rabbitmq,
                      declare_order_exchange,
                      publish_json,
                      ROUTING_KEY)

count = 1

redis: dict = {}


class Ride(BaseModel):
    user_name: str
    driver: str
    car: str
    from_addres: str
    to_addres: str
    price: int


@asynccontextmanager
async def lifespan(_: FastAPI):
    connection = await connect_rabbitmq()
    channel = await connection.channel()
    exchange = await declare_order_exchange(channel)

    app.state.exchange = exchange
    app.state.connection = connection

    yield

    await connection.close()

app = FastAPI(lifespan=lifespan)


@app.post("/taxi")
async def create_order_taxi(payload: Ride, request: Request):
    global count

    ride = {
        "ride_id": count,
        "user_name": payload.user_name,
        "driver": payload.driver,
        "car": payload.car,
        "from_addres": payload.from_addres,
        "to_addres": payload.to_addres,
        "price": payload.price
    }

    redis[count] = ride

    count += 1

    event_data = {
        "event_id": str(uuid4()),
        "event": "order.created",
        "ride": ride
    }
    await publish_json(
        exchange=request.app.state.exchange,
        routing_key=ROUTING_KEY,
        data=event_data
        )

    return 'Успешная отправка'
