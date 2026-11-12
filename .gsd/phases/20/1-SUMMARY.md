---
phase: 20
plan: 1
status: complete
commit: pending (one commit for the phase)
---

# Plan 20.1 Summary: Postgres Driver & Configuration

Branch `feature/postgresql-support`, from `bugfix/mcc-weight-hide-analyzer-type` (8194f01).

## Done
- `asyncpg==0.32.0` and `alembic==1.20.1` in requirements; the exe spec bundles both, plus the migration scripts as data.
- Default `DATABASE_URL` is `postgresql+asyncpg://postgres@localhost:5432/quickyee`; `.env` documents it and the SQLite URL. New `DATABASE_STATEMENT_TIMEOUT_MS` (120 s); pool 10 + 20 per process.
- Postgres driver passes asyncpg `server_settings` (`timezone=Asia/Kolkata`, statement and idle-in-transaction timeouts, `application_name`) instead of statements on every connect.
- `NaiveDateTime` type (`app/core/database/types.py`) on every timestamp column and as `Base.type_annotation_map[datetime]`. It drops tzinfo on bind, as SQLite always did, so asyncpg accepts the UTC-aware values some code still writes.

## Deviation
- No `.env.example`: `.env` is tracked and already serves as the template, so the database lines went there.

## Verification
SQLite suite: 942 passed. 1 failure, `test_owner_options_super_admin`, passes alone with and without these changes (depends on test order).
