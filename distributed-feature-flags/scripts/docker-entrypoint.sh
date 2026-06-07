#!/usr/bin/env bash
set -e

echo "Starting deployment entrypoint..."

# Wait for the database to be ready (optional but recommended)
# We assume the docker-compose healthcheck already handles this, 
# but it's safe to run migrations directly if the DB is up.

echo "Running Alembic migrations..."
alembic upgrade head

echo "Database migrations completed. Starting application..."

# Execute the CMD passed to the container
exec "$@"
