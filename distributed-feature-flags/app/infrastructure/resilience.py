import pybreaker
import structlog

logger = structlog.get_logger(__name__)

class CircuitBreakerListener(pybreaker.CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state):
        logger.warning(
            "circuit_breaker_state_change",
            name=cb.name,
            old_state=old_state.name,
            new_state=new_state.name
        )

# Database Circuit Breaker
# Allows 5 consecutive failures before opening. Half-open tests after 30 seconds.
db_circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    listeners=[CircuitBreakerListener()],
    name="database"
)

# Redis Circuit Breaker
# More sensitive since it's a cache. 3 failures -> open. 10s timeout.
redis_circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=10,
    listeners=[CircuitBreakerListener()],
    name="redis"
)

# Kafka Circuit Breaker
kafka_circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    listeners=[CircuitBreakerListener()],
    name="kafka"
)
