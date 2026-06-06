# CI Quality Gates & Hardening Definitions

Phase 10.5 introduces strict build failure thresholds. A pull request MUST pass all of these gates to be mergeable.

## 1. Lint Gate
- **Definition**: Fails if `flake8` or `mypy` return non-zero exit codes.
- **Goal**: Prevent type inconsistencies and PEP8 violations from entering the `main` branch.

## 2. Unit Tests Gate
- **Definition**: Fails if any isolated domain test or SDK internal state test raises an `AssertionError`.
- **Execution**: Run via `pytest tests/domain sdk/tests`.

## 3. Integration & E2E Gate
- **Definition**: Fails if cross-component boundaries fail (e.g., Redis down simulation, Kafka Outbox schema mismatch) or if the E2E lifecycle test `test_full_platform_lifecycle` fails to complete the registration-to-evaluation sequence.
- **Execution**: `pytest tests/e2e tests/infrastructure`. 

## 4. Contract Tests Gate
- **Definition**: Fails if `tests/contracts/test_kafka_schemas.py` or `tests/contracts/test_schemas.py` detect a JSON Schema mismatch, preventing Producer/Consumer drift.

## 5. Load Test Smoke Gate
- **Definition**: We trigger a mini 5-second `locust` headless run.
- **Condition**: If Error Rate > 1% or P95 > 200ms during this 5-second burst, the CI build fails.

## 6. Coverage Validation Gate
- **Definition**: The script `tests/scripts/check_coverage.py` parses `coverage.xml`.
- **Fail Conditions**:
  - `app.domain.evaluation` < 90%
  - `app.infrastructure.cache` < 85%
  - `app.infrastructure.kafka` < 85%
  - `sdk` < 85%
- **Goal**: Guaranteed high confidence that resilient logic remains strictly tested.
