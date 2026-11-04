from prometheus_client import Counter, Histogram


RIDE_FINISHED_TOTAL = Counter(
    'ride_finished_total',
    'Количество законченных',
)

RIDE_STARTED_TOTAL = Counter(
    'ride_started_total',
    'Количество начатых поездок',
)

RIDE_FAILED_TOTAL = Counter(
    'ride_failed_total',
    'Количество незаконченных поездок',
    ['reason']
)

RIDE_DURATION = Histogram(
    'ride_duration_seconds',
    'Время  поездки',
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2.5, 5]
)

RIDE_DLQ_TOTAL = Counter(
    'ride_dlq_total',
    'Общее количество сообщений, отправленных в DLQ'
)

OUTBOX_SUCCESS_TOTAL = Counter(
    'outbox_ride_success_total',
    'Количество передавших сообщений',
)

OUTBOX_FAILED_TOTAL = Counter(
    'outbox_ride_failed_total',
    'Количество не успешных назначенных заказов',
    ['reason']
)
