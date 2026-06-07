#!/usr/bin/env bash
set -e

echo "Running Dependency Audit..."
poetry run pip-audit
echo "Dependency audit completed successfully."
