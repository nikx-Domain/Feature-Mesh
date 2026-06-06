from prometheus_client import Counter, Gauge

redis_cache_hits_total = Counter(
    "redis_cache_hits_total",
    "Total number of Redis cache hits"
)

redis_cache_misses_total = Counter(
    "redis_cache_misses_total",
    "Total number of Redis cache misses"
)

redis_cache_rebuilds_total = Counter(
    "redis_cache_rebuilds_total",
    "Total number of Redis cache rebuilds"
)

redis_cache_errors_total = Counter(
    "redis_cache_errors_total",
    "Total number of Redis cache errors",
    ["action"]
)

redis_cache_hit_ratio = Gauge(
    "redis_cache_hit_ratio",
    "Ratio of Redis cache hits to total requests"
)
