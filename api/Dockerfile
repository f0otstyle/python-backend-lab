FROM python:3.12

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt


COPY taxi_api.py .
COPY models.py .
COPY error_handler.py .
COPY logging_log.py .

CMD ["uvicorn", "taxi_api:app", "--host", "0.0.0.0", "--port", "8000"]