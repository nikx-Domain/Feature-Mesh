from prometheus_client import Counter, Histogram

HTTP_LATENCY_BUCKETS = (0.010, 0.025, 0.050, 0.100, 0.250, 0.500, 1.0, 2.5, 5.0, float("inf"))

http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    buckets=HTTP_LATENCY_BUCKETS
)

http_errors_total = Counter(
    "http_errors_total",
    "Total number of HTTP 5xx errors",
    ["method", "endpoint"]
)
