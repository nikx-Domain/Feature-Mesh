from prometheus_client import Counter

sdk_snapshot_refresh_total = Counter(
    "sdk_snapshot_refresh_total",
    "Total number of SDK snapshot refreshes",
    ["status"] # success, error
)

sdk_snapshot_refresh_failures_total = Counter(
    "sdk_snapshot_refresh_failures_total",
    "Total number of SDK snapshot refresh failures"
)

sdk_cache_replacements_total = Counter(
    "sdk_cache_replacements_total",
    "Total number of times the SDK cache was completely replaced"
)

sdk_evaluations_total = Counter(
    "sdk_evaluations_total",
    "Total number of local SDK evaluations",
    ["flag_key"]
)
