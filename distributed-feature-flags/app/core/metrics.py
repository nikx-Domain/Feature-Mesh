from prometheus_client import Counter, Histogram, Gauge

# Custom Buckets for Evaluation Latency: 5ms to 250ms
EVALUATION_LATENCY_BUCKETS = (0.005, 0.010, 0.025, 0.050, 0.100, 0.250, float("inf"))
HTTP_LATENCY_BUCKETS = (0.010, 0.025, 0.050, 0.100, 0.250, 0.500, 1.0, 2.5, 5.0, float("inf"))

# --- Evaluation Metrics ---
FEATURE_FLAG_EVALUATIONS_TOTAL = Counter(
    "feature_flag_evaluations_total",
    "Total number of feature flag evaluations",
    ["flag_key", "reason"]
)

FEATURE_FLAG_EVALUATION_FAILURES_TOTAL = Counter(
    "feature_flag_evaluation_failures_total",
    "Total number of feature flag evaluation failures",
    ["flag_key"]
)

FEATURE_FLAG_TARGETING_MATCHES_TOTAL = Counter(
    "feature_flag_targeting_matches_total",
    "Total number of feature flag targeting rule matches",
    ["flag_key"]
)

FEATURE_FLAG_ROLLOUT_MATCHES_TOTAL = Counter(
    "feature_flag_rollout_matches_total",
    "Total number of feature flag rollout rule matches",
    ["flag_key"]
)

FEATURE_FLAG_DISABLED_TOTAL = Counter(
    "feature_flag_disabled_total",
    "Total number of times a feature flag was evaluated while disabled",
    ["flag_key"]
)

EVALUATION_DURATION_SECONDS = Histogram(
    "evaluation_duration_seconds",
    "Time spent evaluating a feature flag",
    ["flag_key"],
    buckets=EVALUATION_LATENCY_BUCKETS
)

# --- Redis Cache Metrics ---
REDIS_CACHE_HITS_TOTAL = Counter(
    "redis_cache_hits_total",
    "Total number of Redis cache hits"
)

REDIS_CACHE_MISSES_TOTAL = Counter(
    "redis_cache_misses_total",
    "Total number of Redis cache misses"
)

REDIS_CACHE_REBUILDS_TOTAL = Counter(
    "redis_cache_rebuilds_total",
    "Total number of Redis cache rebuilds"
)

REDIS_CACHE_ERRORS_TOTAL = Counter(
    "redis_cache_errors_total",
    "Total number of Redis cache errors",
    ["action"]
)

REDIS_CACHE_HIT_RATIO = Gauge(
    "redis_cache_hit_ratio",
    "Ratio of Redis cache hits to total requests (calculated externally via PromQL ideally, but kept as a stub or can be periodically updated)"
)

# --- Kafka / Outbox Metrics ---
KAFKA_EVENTS_PUBLISHED_TOTAL = Counter(
    "kafka_events_published_total",
    "Total number of events published to Kafka",
    ["topic"]
)

KAFKA_EVENTS_FAILED_TOTAL = Counter(
    "kafka_events_failed_total",
    "Total number of failed Kafka publishes",
    ["topic"]
)

KAFKA_CONSUMER_PROCESSED_TOTAL = Counter(
    "kafka_consumer_processed_total",
    "Total number of events processed by consumer",
    ["topic"]
)

KAFKA_CONSUMER_FAILURES_TOTAL = Counter(
    "kafka_consumer_failures_total",
    "Total number of consumer processing failures",
    ["topic"]
)

OUTBOX_EVENTS_PENDING = Gauge(
    "outbox_events_pending",
    "Current number of pending outbox events"
)

OUTBOX_EVENTS_PROCESSED_TOTAL = Counter(
    "outbox_events_processed_total",
    "Total number of outbox events successfully processed"
)

# --- API Metrics ---
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"]
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    buckets=HTTP_LATENCY_BUCKETS
)

HTTP_ERRORS_TOTAL = Counter(
    "http_errors_total",
    "Total number of HTTP 5xx errors",
    ["method", "endpoint"]
)

# --- SDK Metrics (Server Side Representation of SDK Health if needed) ---
# Note: These are defined here but typically an SDK emits its own metrics to its own registry.
SDK_SNAPSHOT_REFRESH_TOTAL = Counter(
    "sdk_snapshot_refresh_total",
    "Total number of SDK snapshot refreshes",
    ["status"] # success, error
)

SDK_EVALUATIONS_TOTAL = Counter(
    "sdk_evaluations_total",
    "Total number of local SDK evaluations",
    ["flag_key"]
)

SDK_CACHE_REPLACEMENTS_TOTAL = Counter(
    "sdk_cache_replacements_total",
    "Total number of times the SDK cache was completely replaced"
)
