---
updated: 2026-10-25T00:00:00+05:30
---

# Project State

## Current Position

**Milestone:** v1.1.0 — Excel Data Exchange
**Phase:** 1 - Exchange Foundation
**Status:** Executed — awaiting `/verify 1` (independent verifier), then the phase commit
**Plan:** 1.1–1.6 ✅ all executed (182 tests green; live uvicorn kill + upload smoke checks); SUMMARY per plan in `.gsd/phases/1/`
**Branch:** `feature/excel-import-export` (from `develop`; Git Flow: main / develop / feature/* / bugfix/* / hotfix/*)

## Last Action

- Archived milestone v1.0.0 roadmap to `.gsd/milestones/v1.0.0/ROADMAP.md`.
- Created milestone v1.1.0: SPEC Goal 6, `ROADMAP.md` (5 phases), `REQUIREMENTS.md` (REQ-01…19, NFR-01…06, CON-01…07), `DECISIONS.md` (DECISION-001…007).
- Phase 1 researched (`phases/1/RESEARCH.md`, level 2) and planned.
- Hardened for the user rule "kitna bhi bada data ho, kabhi freeze, lag ya server crash na ho": DECISION-008…011 (separate supervised worker process, resumable uploads outside the request transaction, ≤ 250 ms write budget with adaptive batches, bounded memory / disk / queue, hostile-file guard), NFR-01…14 made measurable, Phase 1 re-planned into 6 plans over 5 waves, Phase 5 extended with 1M-row load and chaos tests.

## Next Steps

1. `/verify 1` — fresh gsd-verifier checks the codebase (not the SUMMARYs) → `.gsd/phases/1/VERIFICATION.md`
2. Phase 1 commit (professional Conventional Commit message, after user approval)
3. `/plan 2` — farmer exchange plans (use `run_batch` / `checkpoint` / `SeenKeys` / xlsx reader & writer; only register keys of valid rows)

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
