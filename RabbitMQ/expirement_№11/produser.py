from uuid import uuid4

from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

from pydantic import BaseModel
from rabbitmq import (connect_rabbitmq,
                      setup_channel,
                      declare_dlx_exchange,
                      declare_order_queue,
                      declare_dlx_queue,
                      declare_retry_queue,
                      event_publish_json,
                      ROUTING_KEY
                      )

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
    connect = await connect_rabbitmq()
    channel, exchange = await setup_channel(connect)

    exchange_dlx = await declare_dlx_exchange(channel)

    app.state.exchange = exchange
    app.state.connection = connect

    await declare_order_queue(channel, exchange)
    await declare_dlx_queue(channel, exchange_dlx)
    await declare_retry_queue(channel)

    yield


app = FastAPI(lifespan=lifespan)


@app.post("/taxi")
async def create_order_taxi(payload: Ride, request: Request, indenpotent_key: str):
    global count

    ride = {
        "ride_id": count,
        "ride_indenpotent_key": indenpotent_key,
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
        "event_id": ride["ride_indenpotent_key"],
        "event": "order.created",
        "ride": ride
    }
    await event_publish_json(
        exchange=request.app.state.exchange,
        routing_key=ROUTING_KEY,
        data=event_data
        )
    return {"status": "ok", "message": "Успешно"}
