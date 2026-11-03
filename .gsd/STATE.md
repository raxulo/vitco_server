---
updated: 2026-10-25T00:00:00+05:30
---

# Project State

## Current Position

**Phase:** 7 - Super Admin Recycle Bin
**Status:** ✅ Complete (verified 2026-11-04) — awaiting commit approval
**Plan:** 7.1 (Soft-delete admins & purge engine), 7.2 (Recycle Bin web page & tests)
**Branch:** current working branch; commit after `/verify` and user approval

## Last Action

- 2026-11-04: Phase 7 researched, planned, executed and verified (VERIFICATION.md): recycle bin module + page, admin soft delete, who / when shown, VLCC delete now stores deleted_at / deleted_by, cleaner sidebar. 16 new tests; full suite 304 passed, 2 pre-existing failures.

## Next Steps

1. Commit Phase 7 after user approval.

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
