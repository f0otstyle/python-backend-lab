from prometheus_client import Counter, Histogram


DRIVER_ASSIGNED_TOTAL = Counter(
    'http_request_driver_assigned_total',
    'Количество успешно назначенных водителей'
)

DRIVER_FAILED_TOTAL = Counter(
    'http_request_driver_failed_total',
    'Количество не успешных назначенных водителей'
)

DRIVER_DURATION = Histogram(
    'driver_duration_seconds',
    'Время назначения водителя',
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2.5, 5]
)
