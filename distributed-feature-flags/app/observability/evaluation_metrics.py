from prometheus_client import Counter, Histogram

# Custom Buckets for Evaluation Latency: 5ms to 250ms
# These buckets are designed to capture the performance disparity between 
# pure in-memory cache evaluations (< 5ms) and database fallback latency (> 50ms)
EVALUATION_LATENCY_BUCKETS = (0.005, 0.010, 0.025, 0.050, 0.100, 0.250, float("inf"))

# Labels: "flag_key" is low-cardinality since there's a finite number of flags.
# "reason" provides insight into why a flag evaluated to a certain variation 
# (e.g., TARGETING_MATCH, ROLLOUT, DISABLED, DEFAULT)
feature_flag_evaluations_total = Counter(
    "feature_flag_evaluations_total",
    "Total number of feature flag evaluations",
    ["flag_key", "reason"]
)

feature_flag_evaluation_failures_total = Counter(
    "feature_flag_evaluation_failures_total",
    "Total number of feature flag evaluation failures",
    ["flag_key"]
)

feature_flag_targeting_matches_total = Counter(
    "feature_flag_targeting_matches_total",
    "Total number of feature flag targeting rule matches",
    ["flag_key"]
)

feature_flag_rollout_matches_total = Counter(
    "feature_flag_rollout_matches_total",
    "Total number of feature flag rollout rule matches",
    ["flag_key"]
)

feature_flag_disabled_total = Counter(
    "feature_flag_disabled_total",
    "Total number of times a feature flag was evaluated while disabled",
    ["flag_key"]
)

evaluation_duration_seconds = Histogram(
    "evaluation_duration_seconds",
    "Time spent evaluating a feature flag",
    ["flag_key"],
    buckets=EVALUATION_LATENCY_BUCKETS
)
