FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY taxi_api.py .
COPY error_handler.py .
COPY logging_log.py .

CMD ["uvicorn", "taxi_api:app", "--host", "0.0.0.0", "--port", "8000"]