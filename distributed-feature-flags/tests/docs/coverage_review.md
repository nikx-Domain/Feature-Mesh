# Unit Test Coverage Review & Targets

## Existing Coverage Analysis
Based on the current test suites, we identified the following testing gaps:

1. **Authentication & RBAC**: Currently covered at a baseline level (e.g., token generation, basic permission checks). *Gap*: Missing deep coverage on expired tokens, malformed JWTs, and multi-tenant isolation scenarios.
2. **Evaluation Engine**: Covered basic toggles. *Gap*: Targeting rules operator logic (regex, semantic versioning), Rollout hashing distribution logic, and missing attribute handling.
3. **Redis Layer**: *Gap*: Almost entirely untested in isolation. Needs simulated cache miss/hit ratios and serialization logic validation.
4. **Kafka Layer**: *Gap*: Missing Outbox retry assertions, payload validation, and producer failure behaviors.
5. **SDK**: *Gap*: Bootstrapping fallback, concurrent cache read/write, and background thread lifecycle management.
6. **Observability**: Fully tested in Phase 9, but needs integration in the overarching E2E suite.

## Coverage Targets

We enforce strict coverage constraints across core domains.

| Module | Target | Rationale |
| :--- | :--- | :--- |
| **Evaluation Engine** | >95% | Core domain logic. Absolute deterministic correctness is required. |
| **Authentication / RBAC** | >90% | Security boundaries. No unauthenticated path should exist. |
| **SDK (Client & Engine)** | >90% | Client-side evaluation must perfectly mirror server-side. |
| **Redis Layer** | >85% | Caching must degrade gracefully without taking down the API. |
| **Kafka Layer / Outbox** | >85% | Eventual consistency relies heavily on this infrastructure. |
| **Observability** | >85% | Ensures we never lose visibility due to unhandled exceptions in metrics wrappers. |
| *Overall Platform* | *>85%* | Broad confidence across all layers. |

## Strategy to Reach Targets
To reach these targets, Phase 10 will inject specific failure simulations (Chaos testing) to cover the `except` blocks that are historically hard to reach. We will also run `pytest --cov=app --cov-report=html` to generate visual heatmaps of untested code.
