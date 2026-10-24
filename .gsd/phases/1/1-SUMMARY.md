---
phase: 1
plan: 1
completed_at: 2026-10-25
---

# Summary: Job Domain & Persistence

## Results
- 3 tasks completed
- All verifications passed (15 repository tests, real SQLite DB)

## Tasks Completed
| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | Dependencies, EXCHANGE_* settings, job domain layer | phase commit (pending) | ✅ |
| 2 | `excel_jobs` model, mapper, repository (atomic `claim_next`) | phase commit (pending) | ✅ |
| 3 | pytest harness on a temporary SQLite DB + repository tests | phase commit (pending) | ✅ |

## Deviations Applied
- [Codebase convention] No `__init__.py` in `domain/` / `infrastructure/` sub-folders — existing modules (e.g. `masters/units`) use namespace sub-packages; only `app/modules/dataexchange/__init__.py` was added.
- [Design] `mark_running` from the plan's interface list is not needed: `claim_next` sets RUNNING, `worker_pid`, `started_at` and `heartbeat_at` atomically.
- [Missing critical] `ExcelStorageFullException` (507) added now (planned for 1.3) so all domain exceptions live together; `ExcelJobCapacityException` is 429 with `retry_after` (DECISION-011).
- [Test harness] `pytest.ini` sets `asyncio_default_fixture_loop_scope` / `asyncio_default_test_loop_scope = session` so the session-scoped database engine and tests share one loop; conftest refuses to run against a non-SQLite URL and points `EXCHANGE_PATH` at the temp folder.

## Files Changed
- `requirements.txt` — openpyxl 3.1.5, defusedxml 0.7.1
- `requirements-dev.txt` — new: pytest 9.1.1, pytest-asyncio 1.4.0
- `app/config/settings.py` — 16 `EXCHANGE_*` settings
- `app/modules/dataexchange/__init__.py` — new module package
- `app/modules/dataexchange/domain/{enums,entities,exceptions,irepository}.py` — new
- `app/modules/dataexchange/infrastructure/{models,mapper,repository}.py` — new
- `pytest.ini`, `tests/conftest.py`, `tests/dataexchange/__init__.py`, `tests/dataexchange/test_job_repository.py` — new

## Verification
- `import openpyxl, pytest` + `ExcelJobKind.FARMER_IMPORT.is_import` → `3.1.5 True`; `openpyxl.xml.DEFUSEDXML` → `True`: ✅
- No `fastapi|starlette|sqlalchemy` import under `domain/`: ✅
- `excel_jobs` registered with indexes `ix_excel_jobs_user_kind_status`, `ix_excel_jobs_status_created`, `ix_excel_jobs_finished_at`, `ix_excel_jobs_created_by`: ✅
- `pytest tests/dataexchange/test_job_repository.py` → 15 passed, no warnings, temp DB removed: ✅ (includes claim race with two concurrent sessions → exactly one winner; cross-user negative case)
- Real `storage/database/realtime_transfer.db` untouched (0 test users, no `excel_jobs` table yet): ✅
- `import app.main` OK; no `datetime.now(` / `utcnow(` in the module: ✅

## Notes for Later Plans
- `claim_next` uses `UPDATE … RETURNING` (SQLite ≥ 3.35; `.venv` has 3.50.4). Confirm the server's SQLite version during Phase 5.
- The `excel_jobs` table is created on the real DB the first time the app starts after Plan 1.5 wires the repository into the configurator.
