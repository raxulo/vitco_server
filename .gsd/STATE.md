---
updated: 2026-11-08T00:00:00+05:30
---

# Project State

## Current Position

**Milestone:** v1.2.0 - Marketplace Revamp
**Phase:** 17 - Collection Totals & Filters
**Status:** ✅ Complete (verified 2026-11-09); not committed yet. v1.2.0 phases 8 to 16 are committed (`90d47af`, `0011e8e`)
**Plan:** Next is the user's review and approval of the commit message
**Branch:** `feature/collection-summary-filters`, from `feature/marketplace-revamp`; commit after `/verify` and user approval

## Last Action

- 2026-11-09: Phase 17 executed and verified: totals and fuller filters on the VLCC and MCC collection lists. Totals match direct SQL; axe clean on the new parts.
- 2026-11-09: Phase 16 executed and verified: Control Center refresh with tab counts and latest orders. The store redesign was undone at the user's request, so the store keeps its earlier look. Added `scripts/seed_marketplace_demo.py` and seeded the local database after a backup. axe clean on 52 of 52 checks.
- 2026-11-09: Phase 15 executed and verified: public API, rate limits, SEO, axe and keyboard audits, real-server load runs, release checklist. Audit also stopped SQL values reaching the logs (DECISION-024). Full suite including the throughput test: 831 passed, and the 1 failure also occurs on `a345c6f`.
- 2026-11-09: Phase 14 executed and verified in real Chrome: cart, guest COD checkout, tracking, seller orders, parallel order tests. Full suite without the throughput test: 764 passed, and the 1 failure also occurs on `a345c6f`.
- 2026-11-09: Phase 13 executed and verified in real Chrome: listings, filters, details, search, policies, enquiries, inbox. Full suite without the throughput test: 692 passed, and the 1 failure also occurs on `a345c6f`.
- 2026-11-09: Phase 12 verified in real Chrome and design approved by the user: store layout, design system, public home page. Full suite without the throughput test: 587 passed, and the 1 failure also occurs on `a345c6f`.
- 2026-11-09: Phase 11 executed and verified in real Chrome: banners, home sections, trending links, store settings. Full suite without the throughput test: 555 passed, and the 1 failure also occurs on `a345c6f`.
- 2026-11-09: Phase 10 executed and verified in real Chrome: Control Center at `/admin/marketplace` with overview, products, animals, categories, animal types and breeds. Full suite without the throughput test: 475 passed, and the 1 failure also occurs on `a345c6f`.
- 2026-11-09: Phase 9 executed and verified: 15 `mkt_*` tables, seller policy and scope, catalog repository, starter data, Recycle Bin coverage. Full suite without the throughput test: 385 passed, and the 1 failure also occurs on `a345c6f`.
- 2026-11-09: Phase 8 executed and verified (VERIFICATION.md). Full suite: 336 passed; the 2 failures also occur on `a345c6f`. User asked to keep implementing phase by phase.
- 2026-11-08: Milestone v1.2.0 created: SPEC goal 5 revised, REQ-28 to REQ-47 and NFR-15 to NFR-18 added, DECISION-015 to 022 recorded, phases 8 to 15 on the roadmap, Phase 8 researched and planned. Old roadmap archived to `milestones/v1.1.0/`. No application code changed yet.

## Next Steps

1. User looks over the real pages (final sign-off of NFR-15).
2. Run `/verify`, then make the one milestone commit once the user approves the message.
3. Follow `.gsd/phases/15/RELEASE.md` before deploying.

## Active Decisions

| Decision | Choice | Made | Affects |
|----------|--------|------|---------|
| DateTime Storage | `now_naive_ist()` from `app.core.clock` | 2026-10 | All database models & SQLite / Postgres comparisons |
| API Envelopes | Standard list (`items`, `total`, `limit`, `offset`) & single (`data`) | 2026-10 | All `/api/v1/` endpoints |
| Marketplace legacy | Code removed, tables kept, new `mkt_*` tables (DECISION-015) | 2026-11-08 | Phases 8, 9, Recycle Bin |
| Marketplace sellers | Super Admin only now, policy and scope ready for Admin / Sub Admin (DECISION-016) | 2026-11-08 | Phases 9 to 15 |
| Animal purchase | Call, WhatsApp, enquiry; never in cart (DECISION-017) | 2026-11-08 | Phase 13 |
| Product checkout | Guest + COD, room for payments and accounts (DECISION-018) | 2026-11-08 | Phase 14 |
| Marketplace URLs | Public `/marketplace`, `/api/v1/marketplace`; admin `/admin/marketplace`, `/api/v1/admin/marketplace` (DECISION-019) | 2026-11-08 | Phases 10 to 15, auth middleware |
| Storefront UI | Standalone self-hosted design system (DECISION-020) | 2026-11-08 | Phases 12 to 15 |
| Branch base | Current work line at `a345c6f`; `develop` is 35 commits behind (DECISION-021) | 2026-11-08 | This milestone |
| Marketplace images | `MediaService` (DECISION-022) | 2026-11-08 | Phases 10 to 14 |
| Admin REST API | Not built; Control Center is the website (DECISION-023) | 2026-11-09 | Phase 15 |
| SQL logging | Only with `DATABASE_ECHO`, whole app (DECISION-024) | 2026-11-09 | Logging, privacy |
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
- The server's legacy marketplace rows and whether a mobile app calls the old `/api/v1/marketplace` cannot be checked from this workspace. Confirm both before release (`.gsd/phases/15/RELEASE.md`).
- Log files written before DECISION-024 hold SQL values, including password hashes. Clean them up wherever the app has run.
- New orders raise no alert; sellers only see them by opening the Control Center.
- `develop` and `main` are 35 commits behind this work line (DECISION-021).
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
*Last updated: 2026-11-08*
