---
phase: 1
plan: 5
completed_at: 2026-10-25
---

# Summary: Supervisor, Handler & Backpressure

## Results
- 3 tasks completed
- All verifications passed: 13 supervisor / handler tests with a real worker process (163 in the module suite) + a live uvicorn check

## Tasks Completed
| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | `WorkerSupervisor` (spawn, restart back-off, watchdog, cleanup, recovery) + lifespan wiring | phase commit (pending) | ✅ |
| 2 | Commands, `ExcelJobDto`, `ExcelJobHandler` (queue only, 429 / 409, ownership 404), DI + `GetHandler.excel_handler` | phase commit (pending) | ✅ |
| 3 | Kill / restart / recovery / cleanup / backpressure tests against a real child process | phase commit (pending) | ✅ |

## Deviations Applied
- [Rule 1 - Bug risk] The worker is started with `subprocess.Popen` and polled, not `asyncio.create_subprocess_exec`: Windows selector event loops (used by uvicorn in some modes) cannot run asyncio subprocesses.
- [Rule 1 - Bug, Windows] `.venv\Scripts\python.exe` is a launcher that runs the real interpreter as its child, so the supervisor's PID can differ from the worker PID recorded on jobs. Recovery and parent checks use the recorded `worker_pid`. Tests prove that stopping or killing the launcher leaves no orphan worker.
- [Design] Startup recovery fails only RUNNING jobs whose `worker_pid` is dead; QUEUED jobs stay queued and run after a restart. Added `IExcelJobRepository.list_running()` for this.
- [Rule 2 - Missing critical] Cancelling a QUEUED job finishes it at once (CANCELLED), so it never starts; cancelling a finished job raises new `ExcelJobFinishedException` (409).
- [Design] Worker stdout → DEVNULL and stderr → `logs/exchange_worker.stderr.log` (append, reset above 5 MB, start markers), so native crash traces survive restarts and no unread pipe can block the child.
- [Test design] Supervisor tests run `tests/dataexchange/worker_fixture.py`, i.e. the production `build_worker()` plus test processors, so `app.worker.exchange` contains no test-only code. conftest now also points `LOG_PATH` at the temp folder.
- [Known limitation] On Windows, `terminate()` is `TerminateProcess` (no graceful interruption); the job is failed by the watchdog / recovery instead. On Linux the worker gets SIGTERM and interrupts jobs at their next checkpoint.
- [Known limitation] `_ensure_capacity` checks and the insert are not one atomic step; two simultaneous requests from the same user could both queue. Harmless (both run), noted for Phase 5 hardening.

## Files Changed
- `app/worker/supervisor.py` — new
- `app/bootstrap/lifespan.py` — recover + start the supervisor after seeding; stop it before the DB shuts down; failures are logged, never block the API
- `app/modules/dataexchange/application/{command,dto,handler}.py` — new
- `app/modules/dataexchange/domain/exceptions.py` — `ExcelJobFinishedException`
- `app/modules/dataexchange/domain/irepository.py`, `infrastructure/repository.py` — `list_running()`
- `app/modules/configurator.py` — `_dataexchange` registers `ExcelJobHandler` and `WorkerSupervisor`
- `app/modules/dependencies.py` — `GetHandler.excel_handler`
- `tests/conftest.py` — `LOG_PATH` to the temp folder
- `tests/dataexchange/worker_fixture.py`, `tests/dataexchange/test_supervisor_handler.py` — new; `test_job_repository.py` covers `list_running`

## Verification
- Real child worker completes a job; its PID is not the API's; after `stop()` no worker process remains: ✅ (NFR-07)
- Hard-killed worker mid-import: the handler still answers in < 1 s; the supervisor restarts it with a new PID; the job ends FAILED "Worker stopped responding"; committed rows are whole batches (multiple of 5) and ≥ processed_rows: ✅ (NFR-03, NFR-07)
- Worker with an ended parent exits with code 0 within 15 s: ✅
- Recovery fails only the RUNNING job of a dead PID; RUNNING with a live PID and QUEUED untouched: ✅
- Cleanup removes the 25 h-old job folder + row and keeps the 1 h-old one: ✅ (NFR-06)
- Submit only queues (no worker PID); same user + kind → 409 with retry_after 30; queue full → 429 with retry_after 30; other user → 404, Super Admin sees it; cancel queued → CANCELLED, again → 409; file only for finished jobs with a file; valid import moved into the job folder; hostile file rejected with no row and no folder left: ✅ (NFR-04)
- **Live uvicorn on a temp DB:** worker started; worker hard-killed → `/healthz` 200 immediately, new worker in ~1 s; API hard-killed → worker logged "parent process … gone" and exited, no orphan: ✅
- After the whole suite: 0 leftover worker processes; `import app.main` OK: ✅
