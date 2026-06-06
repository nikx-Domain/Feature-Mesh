# test-integration.ps1
# Spins up the infrastructure, runs the tests, checks coverage, and tears down.

Write-Host "Starting Test Infrastructure..."
docker-compose -f docker-compose.test.yml up -d

Write-Host "Waiting for Kafka and Postgres to be ready..."
Start-Sleep -Seconds 15

try {
    Write-Host "Running Pytest..."
    # We assume 'poetry run pytest' or just 'pytest' is available depending on environment
    # In CI, we use python -m pytest
    python -m pytest --cov=app --cov=sdk --cov-report=xml
    $pytestExitCode = $LASTEXITCODE
    
    if ($pytestExitCode -eq 0) {
        Write-Host "Pytest completed successfully."
    } else {
        Write-Host "Pytest failed with exit code $pytestExitCode"
    }

    Write-Host "Checking Coverage Boundaries..."
    python tests/scripts/check_coverage.py
    $covExitCode = $LASTEXITCODE
    
    if ($pytestExitCode -ne 0 -or $covExitCode -ne 0) {
        Write-Host "CI GATE FAILED."
        exit 1
    }
} finally {
    Write-Host "Tearing down Test Infrastructure..."
    docker-compose -f docker-compose.test.yml down -v
}
