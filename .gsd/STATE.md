---
updated: 2026-10-25T00:00:00+05:30
---

# Project State

## Current Position

**Milestone:** v1.1.0 — Excel Data Exchange
**Phase:** 3 - VLCC Excel Exchange
**Status:** ✅ Complete (verified at runtime, 17/17 tests PASS) — awaiting phase commit approval
**Plan:** 3.1 ✅ spec + export, 3.2 ✅ import + worker, 3.3 ✅ endpoints + e2e
**Branch:** `feature/excel-import-export` (from `develop`; Git Flow: main / develop / feature/* / bugfix/* / hotfix/*)

## Last Action

- Phase 3 planned and executed across all 3 plans:
  - Plan 3.1: 44-column `VLCC_SHEET`, `VlccExchangeRepository`, `VlccExportProcessor`, `vlcc_template_path`.
  - Plan 3.2: `VlccImportProcessor` with multi-table upsert, hierarchy code conflict check, seen-keys dedupe, Argon2 caching, registered in `ExchangeWorker`.
  - Plan 3.3: `OwnerScope`, IoC container wiring, `/api/v1/excel/vlccs/*` endpoints, end-to-end integration verified.
- 17/17 automated tests passing in `tests/dataexchange`.

## Next Steps

1. Phase 3 commit (after user approval).
2. Proceed to Phase 4: Prodata Rate-Chart Excel Exchange (all-or-nothing replace, range & overlap validation).

## Active Decisions

| Decision | Choice | Made | Affects |
|----------|--------|------|---------|
| DateTime Storage | `now_naive_ist()` from `app.core.clock` | 2026-10 | All database models & SQLite / Postgres comparisons |
| API Envelopes | Standard list (`items`, `total`, `limit`, `offset`) & single (`data`) | 2026-10 | All `/api/v1/` endpoints |
| Marketplace Access | Public for browsing catalog/products/animals; Protected for orders/selling | 2026-10 | `app/middleware/authentication.py`, `app/api/v1/routers/marketplace.py` |
| GSD Workflow | Active in repository under `.gsd/` | 2026-10 | Planning, execution, and state memory |
| Excel processing | Background jobs, fresh ContextVar context, batch commits (DECISION-001) | 2026-10-25 | Phases 1–5 |
| Excel library | openpyxl 3.1.5 read_only / write_only (DECISION-002) | 2026-10-25 | Phases 1–4 |
| Import semantics | Upsert by code, per-row discard, blank = keep (DECISION-003) | 2026-10-25 | Phases 2–3 |
| Selection by role | VLCC for farmers, owner for VLCCs, locked when single (DECISION-004) | 2026-10-25 | Phases 2, 3, 5 |
| Prodata import | Atomic replace of one chart (DECISION-005) | 2026-10-25 | Phase 4 |
| Default password | `Vitco@123`, hashed once per job (DECISION-006) | 2026-10-25 | Phases 2–3 |
| Crash isolation | Jobs only in a separate worker process supervised by the API (DECISION-008) | 2026-10-25 | Phases 1–5 |
| Uploads | Resumable chunks, no DB transaction during upload (DECISION-009) | 2026-10-25 | Phases 1, 5 |
| DB lock budget | ≤ 250 ms per write transaction, adaptive batch 20–500 (DECISION-010) | 2026-10-25 | Phases 1–4 |
| Bounded resources | Disk-backed dedupe, zip / XML bomb guard, sheet split, disk guard, 429 backpressure (DECISION-011) | 2026-10-25 | Phases 1–5 |
| Commits | One professional Conventional Commit per completed phase, after `/verify` and user approval | 2026-10-25 | All phases |
| Excel engine | Own expat streaming reader + xlsxwriter 3.3.0; openpyxl dev-only (DECISION-012) | 2026-10-25 | Phases 1–4 |
| API responses | `JSONResponse(content=jsonable_encoder(...))` — ORJSONResponse is deprecated in FastAPI 0.141 | 2026-10-25 | New routers |

## Blockers

None.

## Concerns

- Open question for Plan 3.3: may Super Admin pick "Self" as VLCC owner? (DECISION-004)
- MCC treated as a locked VLCC owner — assumption, confirm during Phase 3.
- Confirm the server's SQLite version is ≥ 3.35 (`claim_next` uses UPDATE … RETURNING); `.venv` has 3.50.4.
- Pre-existing: `LoggerManager.shutdown()` leaves file handlers open; its log dir is a relative `logs/`.
- Existing routers still use the deprecated `ORJSONResponse`.
- If the deployment ever runs several API processes, each would start its own exchange worker; `claim_next` is race-free so jobs never run twice, but total concurrency would multiply — set `EXCHANGE_WORKER_ENABLED=0` on all but one.

## Session Context

- Code standards for every change: `AGENTS.md`, `.agents/rules/code_standards.md`, `.gsd/STANDARDS.md`.
- The user reviews every change as a diff (Edit / Write only, no shell patch scripts).
- **Commit policy (user, 2026-10-25):** after a phase passes `/verify`, present a professional Conventional Commit message and commit locally once the user approves. This replaces GSD's per-task commits.
  - Subject: `type(scope): imperative summary`, ≤ 72 characters.
  - Body: what + why, grouped by layer; the decisions and REQ / NFR ids covered; verification evidence.
  - Footer: `Refs: .gsd/phases/N` and the Co-Authored-By trailer.
- Git is local only: never push to the `production` remote.

---
*Last updated: 2026-10-25*
