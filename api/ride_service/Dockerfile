FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY ride_api.py .
COPY rabbitmq.py .
COPY error_handler.py .
COPY logging_log.py .
COPY outbox_relay.py .


CMD ["uvicorn", "ride_api:app", "--host", "0.0.0.0", "--port", "8000"]