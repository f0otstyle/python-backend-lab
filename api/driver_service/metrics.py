from prometheus_client import Counter, Histogram


DRIVER_ASSIGNED_TOTAL = Counter(
    'driver_assigned_total',
    'Количество успешно назначенных водителей'
)

DRIVER_FAILED_TOTAL = Counter(
    'driver_failed_total',
    'Количество не успешных назначенных водителей',
    ['reason']
)

DRIVER_DURATION = Histogram(
    'driver_duration_seconds',
    'Время назначения водителя',
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2.5, 5]
)

DRIVER_DLQ_TOTAL = Counter(
    'driver_dlq_total',
    'Количество упавших сообщений в DLQ'
)

OUTBOX_SUCCESS_TOTAL = Counter(
    'outbox_driver_success_total',
    'Количество передавших сообщений',
)

OUTBOX_FAILED_TOTAL = Counter(
    'outbox_driver_failed_total',
    'Количество не успешных назначенных водителей',
    ['reason']
)
