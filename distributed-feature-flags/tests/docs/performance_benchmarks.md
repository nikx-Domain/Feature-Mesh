# Performance Benchmarks Methodology

This document establishes the benchmarking methodology used to validate the latency, throughput, and memory footprint of the Feature Flag Platform.

## 1. Benchmarked Layers

We evaluate performance across three distinct pathways:
1. **Database Evaluation (Cold Cache)**
   - The cache pointer or payload is absent. The system falls back to PostgreSQL.
   - Evaluates worst-case performance under cache eviction.
2. **Redis Evaluation (Hot Cache)**
   - The primary operational state. Evaluates the overhead of network roundtrips to Redis.
3. **SDK Local Evaluation (Zero Network)**
   - Purely localized evaluation via the Python SDK. 

## 2. Methodology & Metrics

### Measurement Dimensions
- **Throughput (Requests/sec)**: How many evaluations can be resolved concurrently before saturating CPU/Network?
- **Latency (P50, P95, P99)**: The time taken to return a variation.
- **Memory Usage**: Profiling SDK footprint per thousands of rules stored.

### Environment Setup
- Tests run against isolated Docker containers (`docker-compose.test.yml`).
- PostgreSQL and Redis constrained to 1 CPU / 1GB RAM to simulate stress.
- SDK Client loaded with 500 flags and 10,000 targeting rules.

## 3. Baselines & Targets

| Scenario | Target Throughput | Target Latency (P95) | Target Latency (P99) |
| :--- | :--- | :--- | :--- |
| **SDK Local Eval** | > 10,000 req/sec | < 1 ms | < 2 ms |
| **Redis Evaluation** | > 3,000 req/sec | < 15 ms | < 30 ms |
| **Database Eval** | > 500 req/sec | < 80 ms | < 150 ms |

## 4. Execution Tools
We use the asynchronous load testing script located at `tests/performance/load_test.py` to assert these benchmarks. Using an asynchronous load generator removes client-side blocking, ensuring we truly measure server capacity.
