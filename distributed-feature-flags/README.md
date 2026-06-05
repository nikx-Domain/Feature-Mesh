# Distributed Feature Flag Platform

A production-grade, high-performance, multi-tenant Feature Flag Platform inspired by LaunchDarkly, Unleash, and Flagsmith.

## Technology Stack
- **Framework**: FastAPI (Python 3.12)
- **Database**: PostgreSQL (SQLAlchemy 2.x, Alembic)
- **Caching**: Redis
- **Event Streaming**: Kafka

## Folder Layout
- `app/core/`: Configuration, logging, database connections, and dependency setups.
- `app/domain/`: Pure business entities and schemas.
- `app/application/`: Application logic, interfaces, and rule evaluations.
- `app/infrastructure/`: Redis wrappers, Kafka events, and ORM schemas.
- `app/presentation/`: Router handles, middlewares, and SSE controls.

## Development Setup

1. **Prerequisites**:
   - Python 3.12+
   - Poetry (dependency manager)
   - Docker & Docker Compose

2. **Initialize Database**:
   ```bash
   docker compose up -d
   ```

3. **Install Dependencies**:
   ```bash
   poetry install
   ```

4. **Install Pre-Commit Hooks**:
   ```bash
   poetry run pre-commit install
   ```

5. **Run Database Migrations**:
   ```bash
   poetry run alembic upgrade head
   ```

6. **Run Dev API Server**:
   ```bash
   poetry run uvicorn app.main:app --reload
   ```
