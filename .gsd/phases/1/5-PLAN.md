---
phase: 1
plan: 5
wave: 4
depends_on: [4]
files_modified:
  - app/worker/supervisor.py
  - app/bootstrap/lifespan.py
  - app/modules/dataexchange/domain/exceptions.py
  - app/modules/dataexchange/application/command.py
  - app/modules/dataexchange/application/dto.py
  - app/modules/dataexchange/application/handler.py
  - app/modules/configurator.py
  - app/modules/dependencies.py
  - tests/dataexchange/test_supervisor_handler.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Starting the API starts exactly one exchange worker child process; stopping the API stops it"
    - "Killing the worker (kill -9 / TerminateProcess) leaves the API serving requests; the supervisor restarts the worker within 30 s; the job it was running ends FAILED (stale heartbeat) with its committed rows intact"
    - "On API startup, jobs RUNNING under a worker PID that no longer exists are failed; jobs QUEUED stay QUEUED and are picked up"
    - "Job folders and rows older than EXCHANGE_FILE_TTL_HOURS are cleaned up hourly"
    - "Submitting beyond EXCHANGE_MAX_QUEUED_JOBS, or a second active job of the same kind for the same user, returns 429 / 409 with Retry-After — the request never waits"
    - "The API process never executes a job: submit only stores the file and inserts a QUEUED row"
  artifacts:
    - "ExcelJobHandler resolvable via GetHandler.excel_handler(request)"
  key_links:
    - "Requirements: REQ-01, REQ-02, NFR-03, NFR-04, NFR-06, NFR-07, NFR-11; DECISION-008, DECISION-011"
---

# Plan 1.5: Supervisor, Handler & Backpressure

<objective>
Run and guard the worker from the API lifespan, recover from crashes and restarts, clean up old files, and expose a CQRS handler that only queues work and pushes back with clear errors when the system is busy.

Purpose: the API stays fast and alive whatever happens to a job (NFR-07, NFR-04).
Output: supervisor, lifespan wiring, handler + DI, tests that kill a real worker process.
</objective>

<context>
Load for context:
- .gsd/REQUIREMENTS.md (NFR-03, NFR-04, NFR-06, NFR-07, NFR-11)
- .gsd/DECISIONS.md (DECISION-008, DECISION-011)
- app/bootstrap/lifespan.py, app/modules/configurator.py (`_repo_config`, `_handler_config`, `_farmer` as a pattern), app/modules/dependencies.py
- app/worker/exchange.py (Plan 1.4), app/modules/dataexchange/infrastructure/* (Plans 1.1, 1.3)
</context>

<tasks>

<task type="auto">
  <name>Worker supervisor, watchdog and lifespan wiring</name>
  <files>
    app/worker/supervisor.py
    app/bootstrap/lifespan.py
  </files>
  <action>
    1. supervisor.py — `WorkerSupervisor` (`__slots__`):
       - `start()`: `asyncio.create_subprocess_exec(sys.executable, "-m", "app.worker.exchange", "--parent-pid", str(os.getpid()))` (stdout/stderr to the log directory file, not PIPE, so a chatty worker never blocks on a full pipe);
       - monitor task (`context=contextvars.Context()`): when the child exits, log the exit code and restart with back-off 1 s, 2 s, 4 s … max 30 s (reset after 5 min healthy);
       - watchdog every 30 s, each in its own short transaction: `fail_stale(now - EXCHANGE_HEARTBEAT_TIMEOUT_S)`; hourly cleanup of expired jobs (folder + row) and of upload folders older than the TTL;
       - `stop()`: SIGTERM (Windows: `terminate()`), wait 10 s, then kill; cancel monitor / watchdog tasks.
       - `EXCHANGE_WORKER_ENABLED` setting (default True) so tests and special deployments can run without the child.
    2. lifespan.py: after `database.startup()` and the super-admin seed — in a transaction fail RUNNING jobs whose worker PID is not alive (startup recovery), then `await supervisor.start()`; in `finally` before `database.shutdown()`: `await supervisor.stop()`.
    AVOID: `stdout=PIPE` without reading it, because the child blocks once the OS pipe buffer (≈ 64 KB) fills.
    AVOID: `multiprocessing.Process` with the default fork start method on Linux, because forking a process with a running event loop and open DB connections is unsafe; a fresh `python -m` subprocess is clean on every OS.
  </action>
  <verify>Start the dev server → the log shows "exchange worker started (pid …)"; stop it → "exchange worker stopped"; no orphan python process remains (Get-Process python)</verify>
  <done>Worker lifecycle follows the API lifecycle; restart back-off, watchdog and cleanup run.</done>
</task>

<task type="auto">
  <name>Commands, DTO, handler with backpressure, IoC registration</name>
  <files>
    app/modules/dataexchange/domain/exceptions.py
    app/modules/dataexchange/application/command.py
    app/modules/dataexchange/application/dto.py
    app/modules/dataexchange/application/handler.py
    app/modules/configurator.py
    app/modules/dependencies.py
  </files>
  <action>
    1. exceptions.py: ExcelJobCapacityException → status 429 with a `retry_after` attribute (seconds); keep ExcelJobConflictException 409 (also carries retry_after).
    2. command.py (`@dataclass(slots=True, kw_only=True)`): `SubmitExportCommand(kind, owner, target_id)`, `SubmitImportCommand(kind, owner, target_id, upload_id, mode=ImportMode.UPSERT, dry_run=False)`, `GetExcelJobQuery(id, owner)`, `ListExcelJobsQuery(owner, kind=None, status=None, limit=20, offset=0)`, `CancelExcelJobCommand(id, owner)`, `GetExcelJobFileQuery(id, owner)`.
    3. dto.py: `ExcelJobDto` (`slots=True, kw_only=True`): id, kind, status, mode, dry_run, target_id, total_rows, processed_rows, inserted, updated, discarded, progress (0–100), rows_per_second, eta_seconds, poll_after_ms (1,000 while running; 2,000 after 2 min; 5,000 after 10 min; omitted when finished), has_file, file_name, error_message, created_at, started_at, finished_at.
    4. handler.py — `ExcelJobHandler` (`__slots__ = ("_database", "_repository", "_storage", "_guard")`):
       - `submit_export` / `submit_import`: `count_queued() >= EXCHANGE_MAX_QUEUED_JOBS` → ExcelJobCapacityException(retry_after=30); `find_active(owner.id, kind)` → ExcelJobConflictException; `storage.ensure_free_space(...)`; for imports move the completed upload (Plan 1.6 service) into the job folder and run `FileGuard.inspect` in `asyncio.to_thread` before the row is created; insert the QUEUED row. The handler never runs the job.
       - `get`, `list` + `count`, `cancel` (`request_cancel`; finished job → 409), `file_path`: other users' jobs → ExcelJobNotFoundException (404) unless SUPER_ADMIN; `file_path` → ExcelJobFileNotReadyException unless the file exists.
       Entity-scope checks (VLCC / owner / chart) belong to Phases 2–4.
    5. configurator.py: register `ExcelJobRepository` in `_repo_config`; new `_dataexchange` classmethod building `ExchangeStorage`, `FileGuard`, `ExcelJobHandler` and `WorkerSupervisor`; call it from `_handler_config`.
    6. dependencies.py: `excel_handler(request)` accessor (same shape as the others).
  </action>
  <verify>.venv\Scripts\python.exe -c "import app.modules.configurator; print('ok')" → ok, and the app entry module imports</verify>
  <done>Handler queues jobs only, enforces queue / per-user limits with Retry-After, hides other users' jobs.</done>
</task>

<task type="auto">
  <name>Crash, restart and backpressure tests with a real worker process</name>
  <files>
    tests/dataexchange/test_supervisor_handler.py
  </files>
  <action>
    Real test DB; a test-only processor registered through an env flag (e.g. `EXCHANGE_TEST_PROCESSORS=1` makes `register_processors` add a slow processor that inserts real rows batch by batch).
    - supervisor starts a real worker subprocess; a queued job completes;
    - kill -9 / `TerminateProcess` the worker mid-job → supervisor restarts it (new PID) within 30 s; after the heartbeat timeout (set to 3 s in the test) the job is FAILED; the rows committed before the kill exist, and there is no half-written batch;
    - the API-side handler keeps answering `get` while the worker is dead (no hang);
    - parent gone → worker exits on its own (start the worker with a dummy parent PID that is then ended);
    - backpressure: MAX_QUEUED_JOBS=2 → third submit raises 429 with retry_after; same user + kind twice → 409;
    - ownership: user B gets 404 for user A's job;
    - cleanup: a job finished 25 h ago loses folder + row; one finished 1 h ago keeps them.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_supervisor_handler.py -q → green</verify>
  <done>Kill / restart / stale-heartbeat / backpressure / cleanup behaviours are all proven with a real subprocess.</done>
</task>

</tasks>

<verification>
After all tasks, verify:
- [ ] `.venv\Scripts\python.exe -m pytest tests/dataexchange -q` is green
- [ ] Dev server: start → worker PID logged; kill the worker PID by hand → API keeps answering, worker comes back
- [ ] Existing endpoints still respond (login + one list endpoint)
</verification>

<success_criteria>
- [ ] All tasks verified
- [ ] Must-haves confirmed
- [ ] No regressions
</success_criteria>
