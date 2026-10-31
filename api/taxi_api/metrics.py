from prometheus_client import Counter, Histogram


ORDER_CREATE_TOTAL = Counter(
    'http_request_order_created_total',
    'Количество созданных поездок'
)

ORDER_FAILED_TOTAL = Counter(
    'http_request_order_failde_total',
    'Количество неуспешных поездок',
)

ORDER_DURATION = Histogram(
    'order_duration_seconds',
    'Время создания заказа',
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2.5, 5],
)
