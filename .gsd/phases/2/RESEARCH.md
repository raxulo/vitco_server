---
phase: 2
researched_at: 2026-10-25
discovery_level: 1
---

# Phase 2 Research — Farmer Excel Exchange

## Objective
How do we import / export the farmers of one VLCC at the highest throughput SQLite allows, without breaking the business rules the existing farmer API enforces, and without slowing the API?

## Discovery Level
**Level 1** — internal patterns plus a measured micro-benchmark (`scratchpad/bench_bulk.py`, `bench_probe.py`; temp DB, app engine settings).

## Measurements (dev machine, SQLite WAL, `synchronous=NORMAL`)

| What | Result |
|------|--------|
| Raw `sqlite3.executemany`, `users` only (5 indexes, random UUID text PK), 500 rows / commit | **9,229 rows/s** — the hardware / SQLite ceiling |
| SQLAlchemy ORM `insert(Model)`, 4 tables per farmer (user, address, bank, farmer), batch 500 | 1,750 farmers/s, p50 272 ms, p95 511 ms |
| SQLAlchemy Core `Table.insert()` executemany, same | **2,068 farmers/s**, p50 248 ms, p95 329 ms |
| 500-row pre-check `lower(email) IN (…)` + `mobile IN (…)` on 100k users, no expression index | 64 ms (full scan of `users`) |
| Same with `CREATE INDEX ix_users_email_lower ON users (lower(email))` | **17 ms**; plan `SEARCH users USING INDEX ix_users_email_lower` |

Interpretation: one farmer = 4 indexed row inserts, so ~2,300 farmers/s is the SQLite ceiling here. Core bulk SQL reaches ~90 % of it. ORM overhead is ~15 %. A 500-farmer batch is just around the 250 ms lock budget, so the adaptive batcher settles at ~400–500.

## Findings

### Existing business rules the import must keep (from the farmer API / ProfileService)
- `POST /api/v1/farmers` (`routers/farmer.py`):
  - blank email → `farmer_<code>_<hex6>@dairy.local`; blank password → `Vitco@123`;
  - `milk_type` defaults to MIXED; `assigned_chart_rank` defaults to 1;
  - the user's `is_active` follows the farmer's.
- `FarmerHandler.full_create` and `ensure_can_manage`: only owners with `FarmerRepository.can_manage_farmers` may create or modify. For a VLCC this needs `vlcc.farmer_enabled`. The farmer code must not already exist in that VLCC.
- `ProfileService.create`: mobile is mandatory and exactly 10 digits (`mobile_number`). Email and mobile must be unique across **all** users (`exists_email` is case-insensitive via `lower(email)`; `exists_mobile` is exact). Passwords are Argon2-hashed.
- Address: one row per user (`addresses.user_id` UNIQUE).
- Bank: `account_holder` NOT NULL. `sync.py` fills it with the user's name when missing.
- Farmer codes: `farmer_master (vlcc_id, farmer_code)` is UNIQUE **including soft-deleted rows**, while `exists_code_in_vlcc` ignores deleted ones. So re-using a deleted farmer's code fails at the DB, and the import must discard it explicitly (REQ-09).
- VLCC scope: `FarmerAccessScope` / `Hierarchy.vlcc_ids(owner)`. For a VLCC login, `CurrentUser.own_id` is its VLCC id (used by the farmer router).

### Performance levers
1. **Core bulk SQL**: one `INSERT … executemany` per table per batch; updates through `update(Table).where(id == bindparam)` executemany. No per-row ORM objects, no ProfileService per row (N+1 + per-row Argon2).
2. **Expression index** `ix_users_email_lower` (SQLite + PostgreSQL both support `CREATE INDEX IF NOT EXISTS … (lower(email))`): 4× faster pre-checks, and the existing `exists_email` used by every create / update API gets faster too. `create_all` does not add indexes to existing tables, so the worker runs it idempotently at startup (one-time cost off the API process).
3. **Pre-fetch per batch, 3 queries**: existing farmers of the VLCC by code (joined with user / address / bank, deleted included), users by `lower(email) IN`, users by `mobile IN`.
4. **Pipeline**: the next file batch is parsed in a thread while the current one is written; export fetches the next keyset page while the previous one is written to xlsx in a thread.
5. **Passwords**: the default hash is computed once per job. Custom passwords are hashed in a thread pool; argon2-cffi releases the GIL, so hashes run in parallel on several cores.
6. **Export query**: keyset on the UNIQUE `(vlcc_id, farmer_code)` index (`WHERE vlcc_id = ? AND (farmer_code, id) > (?, ?) ORDER BY farmer_code, id LIMIT 1000`), with joins on primary keys only.
7. **Template**: built once and cached on disk; the endpoint is a plain FileResponse.

## Patterns to Follow
- Bulk SQL lives in `app/modules/dataexchange/infrastructure/farmer_repository.py` (infrastructure may use other modules' models, like `hierarchy.py` does). Rules are re-stated, not re-invented: scope via `Hierarchy` / `FarmerAccessScope`, mobile via `mobile_number`.
- Processors implement `ExchangeProcessor`; every write goes through `JobContext.run_batch`, and every batch ends with `checkpoint()`.
- Only rows that passed every check register their keys in `SeenKeys`. Phase 1 note: otherwise a discarded row would "claim" a code / mobile / email.

## Anti-Patterns to Avoid
- Calling `FarmerHandler.full_create` per row: N+1 queries plus one Argon2 hash per row, ~10–20× slower.
- `func.lower(email)` without the expression index: full table scan per batch.
- One transaction per file: holds the SQLite write lock (CON-09).
- Echoing passwords into the discarded-rows report. The password column is left blank there.
- `OFFSET` pagination for export.

## Risks
- **Concurrent API writes** (someone creates the same mobile through the app while the import runs) can make a bulk insert fail with IntegrityError. Mitigation: retry that batch row by row, each row in its own savepoint; only the clashing rows are discarded ("saved by someone else at the same time").
- **First run of the index** on a very large `users` table takes seconds. It runs in the worker, so the API is not blocked.
- **SQLite ceiling ~2,000 farmers/s.** PostgreSQL in production (Phase 5 note) can use COPY / multi-row VALUES for much more.

## Recommendations for Planning
1. Plan 2.1: farmer sheet spec + bulk repository + index + export processor + cached template.
2. Plan 2.2: import processor (validate → classify → pre-check → dedupe → hash → bulk write → report), dry-run, fallback path.
3. Plan 2.3: VLCC scope + options API + farmer endpoints (409 carries the active `job_id`) + worker registration + end-to-end and benchmark.
