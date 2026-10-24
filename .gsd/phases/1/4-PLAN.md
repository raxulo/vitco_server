---
phase: 1
plan: 4
wave: 3
depends_on: [1, 2, 3]
files_modified:
  - app/modules/dataexchange/application/__init__.py
  - app/modules/dataexchange/application/processor.py
  - app/modules/dataexchange/application/batching.py
  - app/worker/__init__.py
  - app/worker/exchange.py
  - tests/dataexchange/test_batching.py
  - tests/dataexchange/test_worker.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "The worker runs as its own process (`python -m app.worker.exchange`), builds the same IoC container as the API, and executes jobs it claims from excel_jobs"
    - "At most EXCHANGE_MAX_CONCURRENT_JOBS jobs run at once inside the worker"
    - "Each batch is one short top-level transaction; a failure inside a batch rolls back only that batch, earlier batches stay committed"
    - "The batch size shrinks when a write transaction exceeds EXCHANGE_TX_BUDGET_MS and grows back when well under it (20 ≤ size ≤ EXCHANGE_MAX_BATCH_SIZE)"
    - "Heartbeat is written at least every 10 s while a job runs; cancel_requested stops the job at the next batch boundary with status CANCELLED"
    - "Above the soft memory limit the batch size is halved; above the hard limit the job fails with 'Worker memory limit reached' instead of the process being OOM-killed"
    - "The worker exits by itself within 5 s when its parent process disappears"
  artifacts:
    - "ExchangeProcessor protocol + JobContext; Phases 2–4 register processors per ExcelJobKind without touching the worker"
  key_links:
    - "Requirements: REQ-01, NFR-01, NFR-02, NFR-03, NFR-07, NFR-08, NFR-11; CON-01, CON-08, CON-09; DECISION-008, DECISION-010"
---

# Plan 1.4: Worker Process Engine

<objective>
Create the separate worker process that claims and executes jobs with bounded memory, short DB transactions, heartbeats and cooperative cancellation — so no job can freeze, slow down or crash the API process.

Purpose: the core of the user's rule "kitna bhi bada data ho, kabhi freeze, lag ya crash na ho" (DECISION-008).
Output: processor protocol, adaptive batcher, `app/worker/exchange.py` entry point, tests.
</objective>

<context>
Load for context:
- .gsd/REQUIREMENTS.md (NFR-01..03, NFR-07, NFR-08, CON-01, CON-08, CON-09)
- .gsd/DECISIONS.md (DECISION-008, DECISION-010, DECISION-011)
- .gsd/phases/1/RESEARCH.md
- app/main.py and app/bootstrap/ (how the ServiceContainer and DatabaseManager are built — the worker must reuse it, not re-wire by hand)
- app/modules/configurator.py
- app/core/database/transaction.py, manager.py
- app/core/logging/ (logger setup to reuse in the worker)
- app/middleware/authentication.py (CurrentUser)
- app/modules/dataexchange/domain/*, infrastructure/* (Plans 1.1–1.3)
</context>

<tasks>

<task type="auto">
  <name>Processor protocol, job context and adaptive batcher</name>
  <files>
    app/modules/dataexchange/application/__init__.py
    app/modules/dataexchange/application/processor.py
    app/modules/dataexchange/application/batching.py
    tests/dataexchange/test_batching.py
  </files>
  <action>
    1. processor.py:
       - `JobContext` (`__slots__`): `job`, `owner: CurrentUser` (rebuilt from created_by / owner_role / owner_own_id), `storage`, `batcher`, `memory_guard`; `async report(*, processed, total, inserted, updated, discarded)` → `save_progress` + heartbeat in its own short transaction, throttled to once per second; `async checkpoint()` called by processors between batches: reports, checks `is_cancel_requested` (raise `JobCancelled`), checks memory (`memory_guard.check()`), checks disk every 10,000 rows (`storage.ensure_free_space(0)`), then `await asyncio.sleep(EXCHANGE_BATCH_PAUSE_MS / 1000)` to hand the SQLite write lock to API writers.
       - `async run_batch(ctx, fn)`: runs `fn` inside `async with database.transaction()` and measures its duration with `time.perf_counter()`, feeding it to the batcher.
       - `ExchangeProcessor(Protocol)`: `kind: ExcelJobKind`; `async run(ctx) -> ProcessorResult` (result_file / report_file + final counters).
    2. batching.py: `AdaptiveBatcher(*, budget_ms, start=200, minimum=20, maximum)` with `__slots__`: `size` property; `record(duration_ms)`: > budget → halve (≥ minimum); < 40% of budget → ×1.25 (≤ maximum). `MemoryGuard(*, soft_mb, hard_mb)`: reads RSS (Linux `/proc/self/statm`; Windows `ctypes` `GetProcessMemoryInfo`; unknown → 0), `check()` → halve the batcher above soft (= 80% of hard), raise `WorkerMemoryLimitError` above hard.
    3. test_batching.py: budget exceeded → halves down to the minimum and not below; fast transactions → grows up to the maximum and not above; MemoryGuard with a fake RSS reader: soft → batch halves, hard → raises.
    AVOID: one transaction for many batches, because the SQLite write lock would block API writes past `busy_timeout=5000` (CON-09).
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_batching.py -q → green</verify>
  <done>Batch size adaptation and memory guard behave exactly as specified, including both bounds.</done>
</task>

<task type="auto">
  <name>Worker process entry point</name>
  <files>
    app/worker/__init__.py
    app/worker/exchange.py
  </files>
  <action>
    `ExchangeWorker` (`__slots__`) + `main()` for `python -m app.worker.exchange --parent-pid <pid>`:
    1. Startup: configure logging (same logger, `worker` name), on Linux `resource.setrlimit(RLIMIT_AS, EXCHANGE_WORKER_MAX_MEMORY_MB)` (catch failure), build the ServiceContainer exactly as the API does (reuse the bootstrap function — no duplicated wiring), `database.startup()`, register processors (empty registry in this phase; Phases 2–4 add theirs through one `register_processors(container, worker)` function).
    2. Loop until stopped: if running < max_concurrent, `claim_next(os.getpid(), now)` in a short transaction; for a claimed job start `asyncio.create_task(self._execute(job), context=contextvars.Context())`; sleep `EXCHANGE_POLL_INTERVAL_MS` when idle.
    3. `_execute`: heartbeat task every 10 s; run the processor with a `JobContext`; COMPLETED / CANCELLED / FAILED (`str(exc)[:500]`, `logger.exception`) — each status write is its own transaction; unknown kind → FAILED "No processor for <kind>"; always cancel the heartbeat task.
    4. Parent watch: every 2 s check the parent PID is alive (`os.kill(pid, 0)` on POSIX, `OpenProcess` via ctypes on Windows); if gone, request cancel for own running jobs, wait ≤ 3 s, `database.shutdown()`, exit 0. Handle SIGTERM / SIGINT the same way.
    AVOID: importing FastAPI app objects or starting Uvicorn in the worker, because the worker must not serve HTTP or run the API lifespan (seeding, etc.).
    AVOID: `create_task` without `context=contextvars.Context()` (CON-01).
  </action>
  <verify>.venv\Scripts\python.exe -m app.worker.exchange --help → prints usage
    Start it with `--parent-pid <a short-lived PID>` → the log shows startup, then "parent gone, exiting" within 5 s after that PID ends</verify>
  <done>The worker starts, idles cheaply, claims jobs, and exits on its own when the parent dies.</done>
</task>

<task type="auto">
  <name>Worker behaviour tests on a real database</name>
  <files>
    tests/dataexchange/test_worker.py
  </files>
  <action>
    Drive `ExchangeWorker` in-process (call its loop / `_execute` with a test registry) on the real test SQLite DB; processors are small test classes implementing the protocol that write real rows through `run_batch` (no mocks):
    - happy path: QUEUED → RUNNING → COMPLETED, counters and result file saved;
    - concurrency: max_concurrent=2 with three slow jobs → never more than 2 RUNNING (observe via DB);
    - batch atomicity: processor fails in batch 3 → rows of batches 1–2 exist, none of batch 3; job FAILED with the message and processed_rows = rows of batches 1–2;
    - cancel: `request_cancel` mid-run → CANCELLED at the next checkpoint, processed < total;
    - heartbeat: `heartbeat_at` advances while a job runs;
    - unknown kind → FAILED "No processor for …";
    - memory hard limit (fake RSS reader) → FAILED "Worker memory limit reached", worker loop keeps running and completes the next job.
    AVOID: sleeps longer than ~2 s; use events and short poll intervals in tests.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_worker.py -q → green</verify>
  <done>All seven worker behaviours pass against the real database.</done>
</task>

</tasks>

<verification>
After all tasks, verify:
- [ ] `.venv\Scripts\python.exe -m pytest tests/dataexchange -q` is green
- [ ] No module under app/worker or app/modules/dataexchange imports `app.main` or FastAPI app objects
- [ ] Every `create_task` passes `context=contextvars.Context()`
- [ ] `__slots__` on worker, batcher, memory guard, context
</verification>

<success_criteria>
- [ ] All tasks verified
- [ ] Must-haves confirmed
</success_criteria>
