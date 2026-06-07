# Database Hardening & Schema Review

This document serves as an audit and review of the PostgreSQL schema design utilized by the Distributed Feature Flag Platform. The review ensures that the database is resilient, performant, and maintains strong data integrity.

## Schema Overview
The database relies on SQLAlchemy ORM for schema definition, utilizing `Uuid` types for primary keys across all domain entities (Users, Organizations, Projects, Feature Flags, etc.).

## 1. Foreign Key Constraints & Cascades
All relational edges are secured by Foreign Key constraints.

- **ON DELETE CASCADE**: Applied heavily across hierarchical ownership. 
  - Deleting an `Organization` cascades down to delete associated `Projects`.
  - Deleting a `Project` cascades to `Environments` and `Feature Flags`.
  - Deleting a `Feature Flag` cascades to `FlagVariations` and `FeatureFlagEnvironments`.
  - *Why this is good*: It prevents orphaned records and maintains absolute referential integrity without requiring the application layer to issue dozens of separate DELETE statements, improving performance and reliability.
- **ON DELETE SET NULL**: Used judiciously for audit logs (`AuditEvent.user_id`) and default variations. If a user is deleted, their past audit logs remain intact, but the user reference is nullified.

## 2. Indexes and Uniqueness
Indexes have been explicitly defined for fields frequently used in WHERE clauses and JOINs.

- **Primary Keys**: All tables have UUID primary keys, natively indexed by PostgreSQL.
- **Unique Constraints**: 
  - `User.email`
  - `Role.name`
  - `Permission.action`
- **Composite Unique Indexes with Partial Filtering**:
  - `idx_project_name_org_active`: Ensures Project names are unique within an Organization, but **only** for active records (`deleted_at IS NULL`). This enables soft-deletes while preserving naming uniqueness constraints.
  - `idx_ff_key_project_active`: Ensures Feature Flag keys are unique within a Project for active flags.
- **Lookup Indexes**:
  - `User.email` is indexed to speed up login flows.
  - `OutboxEvent.status` and `OutboxEvent.aggregate_id` are indexed, ensuring that the background `OutboxPublisher` can query `status='pending'` efficiently without table scans.

## 3. Data Types & Resilience
- **JSON Fields**: `FlagVariation.value` and `TargetingRule.value` utilize PostgreSQL's `JSON` type. *Recommendation*: In high-scale environments, migrating this to `JSONB` could improve read and indexing performance if we ever need to query inside the JSON payload. Currently, we only fetch the payload wholesale, so `JSON` is acceptable.
- **Timestamps**: All timestamps use `DateTime(timezone=True)` defaulting to UTC, which avoids timezone drift and localization bugs across distributed nodes.

## 4. Recommendations for High Scale (Future Work)
While the current schema is robust for general production workloads, the following improvements are recommended before hitting hyper-scale:
1. **JSONB Migration**: Convert `JSON` columns to `JSONB` to allow GIN indexing if we intend to filter users based on targeting rule payloads.
2. **Partitioning**: The `audit_events` and `processed_kafka_events` tables are append-only time-series data. Partitioning these tables by month/week will improve query performance for recent logs and make data archiving (vacuuming) significantly cheaper.
3. **Connection Pooling**: We currently rely on SQLAlchemy's internal pool (`pool_size=20`, `max_overflow=10`). In a Kubernetes environment with dozens of API pods, this will quickly exhaust PostgreSQL connections. Introducing **PgBouncer** is highly recommended.
