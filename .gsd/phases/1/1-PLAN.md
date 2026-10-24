---
phase: 1
plan: 1
wave: 1
depends_on: []
files_modified:
  - requirements.txt
  - requirements-dev.txt
  - app/config/settings.py
  - app/modules/dataexchange/__init__.py
  - app/modules/dataexchange/domain/__init__.py
  - app/modules/dataexchange/domain/enums.py
  - app/modules/dataexchange/domain/entities.py
  - app/modules/dataexchange/domain/exceptions.py
  - app/modules/dataexchange/domain/irepository.py
  - app/modules/dataexchange/infrastructure/__init__.py
  - app/modules/dataexchange/infrastructure/models.py
  - app/modules/dataexchange/infrastructure/mapper.py
  - app/modules/dataexchange/infrastructure/repository.py
  - tests/conftest.py
  - tests/dataexchange/__init__.py
  - tests/dataexchange/test_job_repository.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "An ExcelJob can be created, read back, and its progress / status updated in the excel_jobs table"
    - "Only one active (QUEUED or RUNNING) job per user per kind can be found by find_active"
    - "fail_interrupted() turns every QUEUED / RUNNING job into FAILED and keeps processed_rows"
    - "claim_next() hands a QUEUED job to exactly one caller even when two callers race; the oldest job is claimed first"
    - "fail_stale(before) fails only RUNNING jobs whose heartbeat_at is older than the cut-off"
  artifacts:
    - "app/modules/dataexchange/domain/ has zero imports from fastapi, starlette or sqlalchemy"
    - "excel_jobs table is created by Base.metadata.create_all"
  key_links:
    - "Requirements: REQ-02, NFR-03 (recovery), NFR-04 (active-job lookup), NFR-07 (claim + heartbeat); DECISION-008"
---

# Plan 1.1: Job Domain & Persistence

<objective>
Create the `dataexchange` module skeleton with the `ExcelJob` domain model and its SQLAlchemy persistence, plus the dependencies and test harness every later plan uses.

Purpose: every export / import is a persisted job (DECISION-001); the runner, API and entity adapters all build on this.
Output: domain + infrastructure layers for jobs, `openpyxl` dependency, pytest harness on a temporary SQLite DB.
</objective>

<context>
Load for context:
- .gsd/SPEC.md (Goal 6)
- .gsd/REQUIREMENTS.md (REQ-02, NFR-03, NFR-04, CON-03)
- .gsd/DECISIONS.md (DECISION-001)
- .gsd/phases/1/RESEARCH.md
- AGENTS.md, .agents/rules/code_standards.md, .gsd/STANDARDS.md
- app/modules/masters/units/ (reference module layout: domain/irepository.py, exceptions, mapper, repository)
- app/core/database/mixins.py, app/core/database/base.py
- app/core/exceptions/base.py (ApplicationException)
- app/config/settings.py (STORAGE_PATH and friends; DATABASE_URL setting name)
- app/core/database/factory.py, app/core/database/drivers/sqlite.py (create_all on connect)
</context>

<tasks>

<task type="auto">
  <name>Add dependencies, settings and the job domain layer</name>
  <files>
    requirements.txt
    requirements-dev.txt
    app/config/settings.py
    app/modules/dataexchange/__init__.py
    app/modules/dataexchange/domain/__init__.py
    app/modules/dataexchange/domain/enums.py
    app/modules/dataexchange/domain/entities.py
    app/modules/dataexchange/domain/exceptions.py
    app/modules/dataexchange/domain/irepository.py
  </files>
  <action>
    1. requirements.txt: add `openpyxl==3.1.5` and `defusedxml==<latest on PyPI, check with pip index versions>` under a `# Excel import / export (streaming read_only / write_only; defusedxml blocks XML entity bombs)` comment. New requirements-dev.txt: `-r requirements.txt`, `pytest==9.1.1`, `pytest-asyncio==1.4.0`. Install both into `.venv`.
    2. app/config/settings.py, next to the existing storage paths (all overridable from .env, DECISION-008/010/011):
       `EXCHANGE_PATH = BASE_DIR / "storage" / "exchange"`, `EXCHANGE_MAX_CONCURRENT_JOBS = 2`, `EXCHANGE_MAX_QUEUED_JOBS = 20`, `EXCHANGE_MAX_UPLOAD_MB = 500`, `EXCHANGE_UPLOAD_CHUNK_MB = 5`, `EXCHANGE_MAX_UNCOMPRESSED_MB = 2048`, `EXCHANGE_MAX_ROWS = 5_000_000`, `EXCHANGE_MIN_FREE_DISK_MB = 1024`, `EXCHANGE_FILE_TTL_HOURS = 24`, `EXCHANGE_TX_BUDGET_MS = 250`, `EXCHANGE_BATCH_PAUSE_MS = 20`, `EXCHANGE_MAX_BATCH_SIZE = 500`, `EXCHANGE_WORKER_MAX_MEMORY_MB = 1024`, `EXCHANGE_HEARTBEAT_TIMEOUT_S = 120`, `EXCHANGE_POLL_INTERVAL_MS = 1000`.
    3. domain/enums.py (IntEnum, like the rest of the codebase):
       - `ExcelJobKind`: FARMER_EXPORT=1, FARMER_IMPORT=2, VLCC_EXPORT=3, VLCC_IMPORT=4, PRODATA_EXPORT=5, PRODATA_IMPORT=6; property `is_import`.
       - `ExcelJobStatus`: QUEUED=0, RUNNING=1, COMPLETED=2, FAILED=3, CANCELLED=4; property `is_active` (QUEUED/RUNNING), `is_finished`.
       - `ImportMode`: UPSERT=0, CREATE_ONLY=1.
    4. domain/entities.py: `ExcelJob` as `@dataclass(slots=True, kw_only=True)` with: id, kind, status, mode (ImportMode | None), dry_run, created_by (user id), owner_role (int), owner_own_id (UUID | None), target_id (UUID | None: VLCC id / owner user id / chart id), source_file, result_file, report_file (str | None — names relative to the job folder), total_rows, processed_rows, inserted, updated, discarded (int, default 0), error_message, cancel_requested (bool), worker_pid (int | None), heartbeat_at, created_at, started_at, finished_at, updated_at.
    5. domain/exceptions.py: subclasses of `ApplicationException` with class attrs `code` / `message` / `status_code`: ExcelJobNotFoundException (404), ExcelJobConflictException (409, "An export / import of this type is already running"), ExcelJobCapacityException (409, server busy), ExcelJobFileNotReadyException (409), InvalidExcelFileException (422), ExcelFileTooLargeException (413).
       AVOID: importing anything from `app.core.exceptions` beyond the base class, and any fastapi / sqlalchemy import in domain/, because the domain layer must stay framework-free (AGENTS.md §1).
    6. domain/irepository.py: `IExcelJobRepository(ABC)` with async methods: `create(job)`, `get(job_id)`, `list_for_user(user_id, *, kind, status, limit, offset)`, `count_for_user(user_id, *, kind, status)`, `save_progress(job_id, *, processed_rows, total_rows, inserted, updated, discarded)`, `mark_running(job_id, started_at)`, `mark_finished(job_id, *, status, finished_at, error_message, result_file, report_file)`, `find_active(user_id, kind)`, `count_running()`, `count_queued()`, `claim_next(worker_pid, now) -> ExcelJob | None`, `heartbeat(job_id, now)`, `request_cancel(job_id)`, `is_cancel_requested(job_id) -> bool`, `fail_stale(before, now) -> int`, `fail_interrupted(now) -> int`, `list_expired(before) -> list[ExcelJob]`, `delete(job_id)`.
  </action>
  <verify>.venv\Scripts\python.exe -c "import openpyxl, pytest; from app.modules.dataexchange.domain.enums import ExcelJobKind; print(openpyxl.__version__, ExcelJobKind.FARMER_IMPORT.is_import)"  → prints `3.1.5 True`
    Select-String -Path app/modules/dataexchange/domain/*.py -Pattern "fastapi|starlette|sqlalchemy" → no matches</verify>
  <done>openpyxl 3.1.5 and pytest import from .venv; domain package imports cleanly and contains no framework imports.</done>
</task>

<task type="auto">
  <name>Create the excel_jobs model, mapper and repository</name>
  <files>
    app/modules/dataexchange/infrastructure/__init__.py
    app/modules/dataexchange/infrastructure/models.py
    app/modules/dataexchange/infrastructure/mapper.py
    app/modules/dataexchange/infrastructure/repository.py
  </files>
  <action>
    1. models.py: `ExcelJobModel(Base, UUIDMixin, TimestampMixin)`, `__tablename__ = "excel_jobs"`; columns mirror the entity using `Mapped[...]` + `mapped_column`; enums as `Enum(ExcelJobKind)` etc. like other models; `created_by` FK `users.id` (ondelete CASCADE, indexed); composite index `ix_excel_jobs_user_kind_status (created_by, kind, status)`; index on `finished_at` for cleanup.
    2. mapper.py: `ExcelJobMapper.to_model(entity)` / `to_entity(model)` staticmethods (pattern of `app/modules/masters/units/infrastructure/mapper.py`).
    3. repository.py: `ExcelJobRepository(IExcelJobRepository)` with `__slots__ = ("_database",)` and `_session` property returning `self._database.session` (same as VlccRepository). Implement every interface method with SQLAlchemy 2.0 `select` / `update`; `save_progress` / `mark_*` are single `UPDATE ... WHERE id = :id` statements (no read-modify-write) and also set `updated_at=now_naive_ist()`; `fail_interrupted` updates all QUEUED/RUNNING rows to FAILED with `error_message="Interrupted by server restart"` and returns rowcount; `list_for_user` orders by `created_at DESC`.
       `claim_next` must be race-free on SQLite and PostgreSQL: `UPDATE excel_jobs SET status=RUNNING, worker_pid=:pid, started_at=:now, heartbeat_at=:now WHERE id = (SELECT id FROM excel_jobs WHERE status=QUEUED ORDER BY created_at LIMIT 1) AND status=QUEUED RETURNING *` — the second `status=QUEUED` guard makes a lost race return no row. `fail_stale` fails RUNNING rows with `heartbeat_at < before` ("Worker stopped responding").
       Add index `ix_excel_jobs_status_created (status, created_at)` for `claim_next`.
       AVOID: SELECT-then-UPDATE for claiming, because two workers (or a restarted worker) could both take the same job.
       AVOID: calling `commit()` inside the repository, because transactions are owned by the caller (`async with database.transaction()`), as in every other repository.
       AVOID: `datetime.now()`; use `app.core.clock.now_naive_ist()` (AGENTS.md §2).
  </action>
  <verify>.venv\Scripts\python.exe -c "from app.core.database.base import Base; import app.modules.dataexchange.infrastructure.repository; print('excel_jobs' in Base.metadata.tables)" → prints `True`</verify>
  <done>excel_jobs is registered in Base.metadata with both indexes; repository implements the full interface.</done>
</task>

<task type="auto">
  <name>Pytest harness and repository tests on a real SQLite database</name>
  <files>
    tests/conftest.py
    tests/dataexchange/__init__.py
    tests/dataexchange/test_job_repository.py
  </files>
  <action>
    1. tests/conftest.py: before importing anything from `app`, point the database setting (check the exact field name in app/config/settings.py) at `sqlite+aiosqlite:///<tmp_path_factory dir>/test.db`; session-scoped async fixture `database` that builds the DatabaseManager via `DatabaseFactory`, calls `startup()` (which runs create_all) and `shutdown()` at the end; fixture `user_factory` that inserts real `UserModel` rows (unique email + mobile) inside `database.transaction()`. Configure `asyncio_mode = "auto"` through a `[tool.pytest.ini_options]` block or `pytest.ini` — create `pytest.ini` at repo root if no pyproject exists and add it to this task's files when created.
    2. test_job_repository.py — real DB, no mocks:
       - create + get round-trip keeps every field;
       - save_progress then get returns the new counters;
       - find_active returns the QUEUED job for (user, kind) and None for another kind and another user;
       - fail_interrupted returns 2 for one QUEUED + one RUNNING job, leaves a COMPLETED job untouched, keeps processed_rows;
       - list_expired returns only jobs finished before the cut-off;
       - list_for_user / count_for_user never return another user's jobs (negative case);
       - claim_next: two concurrent `claim_next` calls (separate sessions, `asyncio.gather`) on one QUEUED job → exactly one gets it, the other gets None; with two queued jobs the older one is claimed first; no QUEUED job → None;
       - fail_stale fails a RUNNING job with an old heartbeat and leaves one with a fresh heartbeat RUNNING;
       - request_cancel → is_cancel_requested is True.
       AVOID: asserting only `is not None` — assert concrete field values (GSD test quality rules).
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_job_repository.py -q → all tests pass, 0 skipped</verify>
  <done>≥ 10 repository tests pass against a real SQLite file database, including the cross-user negative case and the claim race.</done>
</task>

</tasks>

<verification>
After all tasks, verify:
- [ ] `.venv\Scripts\python.exe -m pytest tests/dataexchange -q` is green
- [ ] No `fastapi|starlette|sqlalchemy` import under app/modules/dataexchange/domain/
- [ ] No `datetime.now(` / `utcnow(` under app/modules/dataexchange/
- [ ] Classes with state declare `__slots__`; dataclasses use `slots=True, kw_only=True`
</verification>

<success_criteria>
- [ ] All tasks verified
- [ ] Must-haves confirmed
- [ ] Existing app still starts (`.venv\Scripts\python.exe -c "import app.main"` or the project's entry module imports without error)
</success_criteria>
