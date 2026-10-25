# Plan 5.2: Chaos, Reliability & Hostile File Rejection Tests

## Goal
Empirically validate system resilience against process crashes, hostile files, uncommitted rollbacks, and storage pressure (NFR-03, NFR-07, NFR-09, NFR-11).

## Scope & Test Cases

1. **Worker Crash & Transaction Rollback (NFR-03, NFR-07):**
   - Test worker termination mid-import.
   - Verify uncommitted batch is aborted cleanly.
   - Verify zero orphaned records (no `User` without `Farmer` or `Farmer` without `User`).
   - Verify job status transition and heartbeat stale detection.

2. **Hostile File Rejection (NFR-09):**
   - Non-xlsx file disguised with `.xlsx` extension -> rejects before parsing.
   - Zip bomb / XML entity expansion (XXE) -> rejected safely by file guard.
   - Excessive empty rows -> reader terminates after blank limit.

3. **Storage & Disk Guard (NFR-11, NFR-05):**
   - Free disk space below threshold (`EXCHANGE_MIN_FREE_BYTES`) -> returns HTTP 507 Insufficient Storage.
   - Upload cancellation -> cleans up temporary chunk files.

## Target Test Suite
- `tests/dataexchange/test_chaos.py`
