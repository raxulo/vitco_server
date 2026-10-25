# Plan 5.3: Load Testing & Flat Memory Benchmark (NFR-01, NFR-02, NFR-08)

## Goal
Prove that the background worker and database engine maintain flat memory (< 50MB RSS growth), sub-250ms write locks, and sub-300ms p95 API response times while processing high row volumes (NFR-01, NFR-02, NFR-08).

## Implementation
1. **Benchmark Tool (`scripts/loadtest_excel.py`):**
   - Synthesizes 100k+ farmer records into a valid `.xlsx` workbook.
   - Measures:
     - Worker peak RSS before and after import/export.
     - Execution elapsed time and rows/second throughput.
     - Background concurrent traffic generator simulating 500+ status poll requests and health check requests.
     - Latency statistics (p50, p95, p99).
     - SQLite lock contention monitoring: confirms 0 `database is locked` exceptions.
2. Run automated verification in tests (`tests/dataexchange/test_load_concurrency.py`).
