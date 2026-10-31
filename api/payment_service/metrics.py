from prometheus_client import Counter, Histogram


PAYMENT_SUCCESS_TOTAL = Counter(
    'http_request_success_payment_total',
    'Количество успешных оплат',
)

PAYMENT_FAILED_TOTAL = Counter(
    'http_request_failed_payment_total',
    'Количество упавших оплат',
    ['reason']
)

PAYMENT_DURATION = Histogram(
    'payment_duration_seconds',
    'Время обработки оплаты',
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2.5, 5],
)
