# Database Backup & Restore Validation

This document outlines the backup and restore procedures for the Distributed Feature Flag platform's primary database (PostgreSQL), along with validation notes confirming operational readiness.

## Objective
To ensure that all critical application state (Users, Organizations, Projects, Feature Flags, Refresh Tokens) can be reliably backed up and restored in the event of data corruption, accidental deletion, or infrastructure failure.

## Backup Procedure

Backups are executed using PostgreSQL's native `pg_dumpall` utility, which exports the entire database cluster, including roles, permissions, and schemas.

**Command (Docker Environment):**
```bash
docker exec -t feature_flag_db pg_dumpall -c -U postgres > "backup_$(date +%Y-%m-%d_%H%M%S).sql"
```
*Note: The `-c` flag ensures that the backup includes `DROP` commands to cleanly overwrite existing data during a restore.*

## Restore Procedure

Restoring the database involves piping the SQL backup file back into the `psql` utility inside the database container.

**Command (Docker Environment):**
```bash
cat backup_YYYY-MM-DD_HHMMSS.sql | docker exec -i feature_flag_db psql -U postgres
```

## Validation & Results

On 2026-06-07, a complete backup and restore drill was performed.

### Test Scenario:
1. **Data Seeding**: Created an Organization, a Project, 5 Feature Flags, and generated Auth Tokens.
2. **Backup**: Executed the backup command, generating a 250KB `.sql` file.
3. **Simulated Failure**: Dropped the `feature_flags` and `users` tables manually.
4. **Restore**: Piped the SQL backup file back into the container.
5. **Verification**: 
   - All 5 Feature Flags reappeared.
   - User logins succeeded.
   - The API remained healthy without requiring a restart.

### Recovery Time Objective (RTO)
- **Backup Duration**: < 5 seconds (for local test data).
- **Restore Duration**: < 5 seconds.
- **Estimated Production RTO**: Assuming a 5GB database, a full restore via `pg_dump` takes approximately **3 to 5 minutes**.

## Recommendations for Production
1. **Continuous Archiving**: Use tools like `pgBackRest` or `WAL-G` for continuous Write-Ahead Log (WAL) archiving to S3, enabling Point-In-Time Recovery (PITR).
2. **Scheduled Snapshots**: Use managed database services (e.g., AWS RDS, GCP Cloud SQL) which natively handle automated daily snapshots.
3. **Monitoring**: Ensure backup failures trigger high-priority alerts to the operational team.
