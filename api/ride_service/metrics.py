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
)
