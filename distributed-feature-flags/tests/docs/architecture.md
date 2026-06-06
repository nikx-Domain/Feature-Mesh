# Testing Architecture & Strategy

Our quality engineering philosophy extends beyond happy-path validations to ensure confidence under extreme load, high concurrency, and catastrophic infrastructure failures. 

## The Testing Pyramid

1. **Unit Tests (Fast & Isolated)**
   - Target: `app.domain.*`, `app.core.*`, `sdk.*`
   - Purpose: Exhaustive edge-case testing of the Evaluation Engine, Role-Based Access Control logic, JWT Parsing, and string hashing.
   - Tools: `pytest`, `pytest-mock`
   
2. **Integration Tests (Component & Boundary)**
   - Target: `app.infrastructure.*`, `app.application.*`
   - Purpose: Verify interactions between business use cases and infrastructure layers. This includes Cache Service miss/hit behaviors and Kafka Producer semantics.
   - Tools: `pytest-asyncio`, `testcontainers` (or real services via `docker-compose.test.yml`).

3. **Contract Tests (Schema Defenses)**
   - Target: Event Schemas, SDK Snapshot format.
   - Purpose: Prevent drift between the outbox publisher and the consumers, and between the backend API and the Python SDK cache parsers.
   - Tools: `jsonschema`, Pydantic strict validations.

4. **End-to-End Tests (System Lifecycle)**
   - Target: `app.presentation.api.*`
   - Purpose: Validating entire user journeys: Organization registration -> Environment creation -> Flag toggling -> Evaluation -> Audit Retrieval.
   - Tools: `httpx`, `FastAPI TestClient`.

5. **Non-Functional Tests (Reliability & Performance)**
   - **Load Tests**: Hitting the evaluation endpoint with thousands of requests per second to measure P50/P95/P99 latencies using an asynchronous script or `locust`.
   - **Concurrency Tests**: Forcing thousands of concurrent requests utilizing `asyncio.gather` against SDK local caches and the primary backend to surface race conditions and state corruption.
   - **Failure Injection (Chaos)**: Simulating Redis crashes, Kafka timeouts, and Network partitions during executions to ensure graceful degradation (fallback to Database or fallback to default SDK values).
