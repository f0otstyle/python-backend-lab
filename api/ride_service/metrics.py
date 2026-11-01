from prometheus_client import Counter, Histogram


RIDE_FINISHED_TOTAL = Counter(
    'http_request_ride_finished_total',
    'Количество законченных',
)

RIDE_STARTED_TOTAL = Counter(
    'http_request_ride_started_total',
    'Количество начатых поездок',
)

RIDE_FAILED_TOTAL = Counter(
    'http_request_ride_failed_total',
    'Количество незаконченных поездок',
    ['reason']
)

RIDE_DLQ_TOTAL = Counter(
    'ride_dlq_total',
    'Общее количество сообщений, отправленных в DLQ'
)

OUTBOX_SUCCESS_TOTAL = Counter(
    'http_request_outbox_order_total',
    'Количество передавших сообщений',
)

OUTBOX_FAILED_TOTAL = Counter(
    'http_request_outbox_failed_total',
    'Количество не успешных назначенных заказов',
    ['reason']
)