# Interview Preparation Guide

This guide is designed to help you prepare for technical interviews by detailing the architectural decisions, tradeoffs, and challenges encountered while building the Distributed Feature Flag Platform.

## 1. Architecture & Design Decisions

### Why Clean Architecture & DDD?
**Decision:** Separated the application into Domain, Application, Infrastructure, and Presentation layers.
**Reasoning:** Feature flag evaluation logic is highly critical business logic. By isolating the `domain` (Entities, rules) from `infrastructure` (PostgreSQL, Kafka), we ensured the core logic could be unit-tested without databases, and that we could swap out infrastructure (e.g., swapping RabbitMQ for Kafka) without rewriting use cases.

### Why the Transactional Outbox Pattern?
**Decision:** Used an `outbox_events` table within the same PostgreSQL transaction as feature flag updates.
**Reasoning:** "Dual writes" (writing to DB and then publishing to Kafka) are notoriously flaky. If the app crashes after the DB write but before the Kafka publish, downstream systems (like caches) become permanently out of sync. The Outbox pattern guarantees *at-least-once* delivery by tying the event creation to the DB transaction.

### Why Redis + PostgreSQL?
**Decision:** Postgres for persistent truth, Redis for fast reads.
**Reasoning:** Feature flag evaluation requires sub-millisecond latency. Hitting Postgres for every evaluation would choke the DB under high load. Redis provides O(1) lookups in memory.

## 2. Tradeoffs Made

### At-Least-Once Delivery vs. Exactly-Once
**Tradeoff:** The outbox publisher and Kafka consumers guarantee *at-least-once* delivery. This means consumers might process the same event twice.
**Mitigation:** We designed the Cache Invalidation and Audit Logging consumers to be **idempotent**. Setting a cache key or appending an audit log is safe to do multiple times. Exactly-once delivery is computationally expensive and was deemed unnecessary for this use case.

### Polling the Outbox vs. Change Data Capture (CDC)
**Tradeoff:** We use an async Python background task to poll the `outbox_events` table every 2 seconds, rather than using Debezium (CDC) to tail the Postgres WAL.
**Reasoning:** CDC introduces significant infrastructural complexity (Kafka Connect, Debezium containers). Polling is simpler to deploy and manage for a V1, though it introduces a maximum 2-second delay in event propagation.

## 3. Challenges & Failures Encountered

### Challenge: SQLAlchemy Async Sessions
**Issue:** Handling async database sessions in FastAPI dependencies often lead to `DetachedInstanceError` when accessing relationships after the session closed.
**Solution:** Implemented a robust `SQLAlchemyUnitOfWork`. By wrapping operations in an `async with uow:` block, we forced explicit relationship loading (e.g., `selectinload`) within the transaction boundary, preventing lazy-loading failures.

### Challenge: Dependency Injection Complexity
**Issue:** As the application grew, passing repositories into use cases manually became bloated.
**Solution:** Used the Unit of Work as a central registry for repositories, injecting only the UoW into the Application Use Cases.

## 4. Common Interview Questions & Answers

**Q: "How does your system handle a Redis failure?"**
A: "We implemented Circuit Breakers using `pybreaker`. If Redis fails 3 consecutive times, the circuit opens. During this time, the `CacheService` degrades gracefully, returning a 'cache miss' instead of throwing an exception. The Evaluation API then falls back to PostgreSQL to serve the flag, ensuring availability at the cost of slightly higher latency."

**Q: "How did you secure your APIs?"**
A: "The API uses stateless JWTs signed with RS256 asymmetric keys. To prevent replay attacks and token theft, I implemented Refresh Token Rotation—storing refresh token hashes in Postgres. If a refresh token is used twice, the system detects the anomaly and revokes all active sessions for that user. We also use `slowapi` for IP rate-limiting."

**Q: "How would you scale this to 100x traffic?"**
A: 
1. **API Layer**: The FastAPI instances are completely stateless and can be horizontally scaled behind a load balancer (e.g., Kubernetes HPA).
2. **Database Layer**: Add connection pooling (PgBouncer) to prevent connection exhaustion. Implement Read Replicas for the evaluation endpoints if Redis misses become too frequent.
3. **Data Pruning**: Implement table partitioning on `audit_events` to keep the primary table size manageable.

## 5. Security & Reliability Highlights
- **DLQ (Dead Letter Queue)**: If a Kafka consumer fails to process a message 3 times, it sends the message to a `dead_letter_events` topic to prevent blocking the partition while avoiding data loss.
- **Middleware**: Built custom middleware to inject security headers (CSP, X-Frame-Options) and extract tenant/user context from JWTs securely.
