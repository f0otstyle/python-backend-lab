from prometheus_client import Counter, Histogram


ORDER_CREATE_TOTAL = Counter(
    'taxi_order_created_total',
    'Количество созданных поездок'
)

ORDER_FAILED_TOTAL = Counter(
    'taxi_order_failed_total',
    'Количество неуспешных поездок',
    ['reason']
)

ORDER_DURATION = Histogram(
    'order_duration_seconds',
    'Время создания заказа',
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2.5, 5],
)

OUTBOX_SUCCESS_TOTAL = Counter(
    'outbox_taxi_success_total',
    'Количество передавших сообщений',
)

OUTBOX_FAILED_TOTAL = Counter(
    'outbox_taxi_failed_total',
    'Количество не успешных назначенных заказов',
    ['reason']
)
