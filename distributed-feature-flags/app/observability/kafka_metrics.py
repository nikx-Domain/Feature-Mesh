from prometheus_client import Counter, Gauge

kafka_events_published_total = Counter(
    "kafka_events_published_total",
    "Total number of events published to Kafka",
    ["topic"]
)

kafka_events_failed_total = Counter(
    "kafka_events_failed_total",
    "Total number of failed Kafka publishes",
    ["topic"]
)

kafka_consumer_processed_total = Counter(
    "kafka_consumer_processed_total",
    "Total number of events processed by consumer",
    ["topic"]
)

kafka_consumer_failures_total = Counter(
    "kafka_consumer_failures_total",
    "Total number of consumer processing failures",
    ["topic"]
)

outbox_events_pending = Gauge(
    "outbox_events_pending",
    "Current number of pending outbox events"
)

outbox_events_processed_total = Counter(
    "outbox_events_processed_total",
    "Total number of outbox events successfully processed"
)
