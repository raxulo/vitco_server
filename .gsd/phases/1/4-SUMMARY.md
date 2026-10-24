---
phase: 1
plan: 4
completed_at: 2026-10-25
---

# Summary: Worker Process Engine

## Results
- 3 tasks completed
- All verifications passed: 8 batching + 9 worker tests (150 in the module suite); parent-exit check on a real process

## Tasks Completed
| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | `ExchangeProcessor` protocol, `JobContext` (`run_batch`, `checkpoint`, `report`, `interrupt`), `AdaptiveBatcher`, `MemoryGuard` | phase commit (pending) | ✅ |
| 2 | `python -m app.worker.exchange`: container reuse, claim loop, heartbeat, parent watch, signals, own log file, address-space backstop | phase commit (pending) | ✅ |
| 3 | Worker behaviour tests on the real test DB | phase commit (pending) | ✅ |

## Deviations Applied
- [Rule 1 - Bug] Windows RSS was read as 0, so the memory guard was blind on Windows. Without `restype`, the 64-bit pseudo-handle from `GetCurrentProcess()` is truncated and `GetProcessMemoryInfo` fails silently. Fixed with explicit ctypes `restype` / `argtypes`; a test asserts a real, non-zero RSS.
- [Rule 1 - Bug] Two processes rotating the API's `RotatingFileHandler` file corrupts logs (rename fails on Windows). The worker logs to its own rotating `logs/exchange_worker.log` + console, through the project logger root (`realtimetransfer`, not `app`).
- [Rule 3 - Blocking] The worker resolves `ExcelJobRepository`, `ExchangeStorage` and `FileGuard` from the container, so their registration moved forward from Plan 1.5. This adds the `_repo_config` entry and a new `ModuleConfigurator._dataexchange_register`. Side effect: the API now creates the `excel_jobs` table on startup.
- [Rule 2 - Missing critical] Worker shutdown (parent gone / SIGTERM) interrupts running jobs at their next checkpoint (`JobInterrupted` → FAILED "Interrupted by server restart"), waits 3 s, then cancels. A user cancel ends CANCELLED "Cancelled by the user".
- [Design] RLIMIT_AS (Linux only) = 2 × `EXCHANGE_WORKER_MAX_MEMORY_MB` + 512 MB. Virtual memory includes SQLite's 256 MB mmap and thread stacks, so an RSS-sized limit would cause false MemoryErrors; the RSS `MemoryGuard` stays the primary guard.
- [Design] Cancel flag and progress are checked / written at most once per second per job (not every batch) to keep DB load from polling negligible.

## Files Changed
- `app/modules/dataexchange/application/batching.py` — new
- `app/modules/dataexchange/application/processor.py` — new
- `app/worker/__init__.py`, `app/worker/exchange.py` — new
- `app/modules/configurator.py` — registers ExcelJobRepository, ExchangeStorage, FileGuard
- `tests/dataexchange/test_batching.py`, `tests/dataexchange/test_worker.py` — new

## Verification
- Batch size halves to the minimum (200→100→50→25→20) and grows to the maximum; memory guard shrinks at soft, raises at hard; real RSS > 10 MB on Windows: ✅ (NFR-08, NFR-01)
- `python -m app.worker.exchange --help` prints usage: ✅
- Worker started with a short-lived parent PID exited **1.2 s** after the parent ended, logging "parent process … gone" (temp DB, real DB untouched): ✅ (NFR-07)
- Happy path; max 2 running of 3 (observed in DB and in-process); failure in batch 3 keeps batches 1–2 and nothing of batch 3; cancel → CANCELLED with committed rows == processed_rows; heartbeat advances during a long step; unknown kind → "No processor for VLCC_IMPORT"; memory limit → FAILED and the next job completes; stop → "Interrupted by server restart" with no half batch: ✅ (NFR-03, NFR-07)
- 4 repeated runs of the worker tests all green (no timing flakiness): ✅
- No `app.main` / FastAPI app import under `app/worker` or the module; every `create_task` uses `context=contextvars.Context()`: ✅ (CON-01)
