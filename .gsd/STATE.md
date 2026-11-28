---
updated: 2026-11-08T00:00:00+05:30
---

# Project State

## Current Position

**Milestone:** v1.3.0 - Technical Support
**Phase:** 29 - Calls, Audit Views and My Activity
**Status:** ✅ Phases 26 to 29 executed and verified (uncommitted); visual sign-off and commits await the user
**Plan:** Next: Phase 30 (hardening, `docs/SUPPORT_API.md`, end-to-end verification)
**Branch:** `feature/support-foundation` (Phase 25 committed as 058cf5a; Phases 26 to 29 uncommitted on top of it)

## Last Action

- 2026-11-22: **Phase 29 executed (uncommitted).** Migration 0008 (`support_call_logs`), click-to-call with outcome,
  phone-number views audited once a day, My Activity / Team activity / Audit log screens from aggregate queries,
  new support home. Related suites: SQLite 286 + 2 skipped, PostgreSQL 287 + 1 skipped.
- 2026-11-22: The app sends its FCM token with `POST /api/v1/auth/login` (optional `fcm_token`, `platform`,
  `app_version`; never fails the login).

- 2026-11-22: **Phase 28 reshaped at the user's request:** push notifications are now the shared module
  `app/modules/notification/` (DECISION-034) for every feature; support only keeps its texts. Tables
  `notification_device_tokens` / `notification_outbox`, API `/api/v1/notifications/devices`. Also fixed: Recycle Bin
  purge of users who raised tickets. SQLite 237 + 2 skipped, PostgreSQL 259 + 1 skipped on the related suites.

- 2026-11-22: **Phase 28 executed (uncommitted).** Migration 0007, device-token API, push outbox written with the
  ticket change, FCM HTTP v1 sender (no SDK), in-process push worker; disabled (nothing written, no worker) without
  a Firebase credential. Support suites 227 passed + 1 skipped on SQLite, 228 on PostgreSQL. Found a pre-existing
  SQLite savepoint problem (see Concerns). Open item: Firebase service-account JSON from the user.

- 2026-11-22: **Phase 27 executed (uncommitted).** Redis wrapper (optional), commit-safe event bus with replay,
  permission-based audience, `/ws/support` and `/ws/support/app`, live portal client. Support suites 200 passed on
  SQLite, 202 on PostgreSQL; real uvicorn + headless Chrome run 13/13. Not checked against a real Redis server.

- 2026-11-22: **Phase 26 executed (uncommitted).** Ticket engine (migration 0006, rules, handlers, routing), mobile
  API `/api/v1/support` (tickets, messages, private attachments), portal queues, ticket detail with HTMX composer,
  categories. Support suites 167 passed on SQLite, 171 (with the migration test) on PostgreSQL. Screens reviewed in
  headless Chrome at 1440 and 390 px. Waiting for the user's visual review and commit approval.

- 2026-11-18: **Phase 25 executed (uncommitted)** on `feature/technical-support` (branched from 8f542e5, not from
  `develop`: develop is at b10c5b7 and lacks migrations 0001 to 0004). Support module, `Role.SUPPORT`, migration 0005,
  portal shell + design system, teams / members / roles screens, isolation middleware. Support suites 60 passed on
  SQLite, 64 on PostgreSQL (found and fixed a PostgreSQL-only migration bug). Waiting for the user's visual review
  and commit approval. The plans were committed by the user as 17b3cb6 ("plans") on this branch.

- 2026-11-18: **Technical Support planned (no code yet).** Design document `docs/TECHNICAL_SUPPORT_PLAN.md`
  (decisions D-1 to D-14), DECISION-031 to 033, REQ-58 to REQ-80, ROADMAP "Technical Support (v1.3.0)" with Phases
  25 to 30 and plans in `.gsd/phases/25..30/`. Next: user reviews the plans, then `/execute 25` on a new branch
  `feature/technical-support` (from `develop`). Open item: Firebase service-account JSON (Phase 28, can come later).

- 2026-11-15: Quick task on `feature/sidebar-group-colors` (uncommitted). Each sidebar section heading has its own
  bright colour (General blue, MCC Management orange, VLCC Management green, System Setup purple, Payments cyan,
  Marketplace pink); only the selected item is filled with it, other items stay neutral. The current page's section
  is rendered open and its item active by the server (no open animation on load). Site icon fixed: favicons built
  from `images/logo.png` (`favicon.ico`, 32px, apple-touch, 192/512 + `site.webmanifest`), `/favicon.ico` route
  (public), `head.html` title "VITCO - Dairy Management", description, `noindex, nofollow` for management pages.
  Checked by desktop screenshots; 143 related tests passed.

- 2026-11-15: Phase 24 executed (uncommitted). Combined collection column catalogue + Chart Rank / Quantity Mode /
  Measurement Mode / Deleted; deleted rows exported in red; per-user layout table `excel_column_layouts`
  (migration `0004`), API `/api/v1/excel/column-layouts/collections`, web page `/sub-admins/column-layout` with
  links on profile / list / view. SQLite full suite 1050 passed (+ the order-dependent owner-options test, now fixed);
  Phase 24 suites 48 passed on PostgreSQL; /verify on PostgreSQL with the real worker passed.
- 2026-11-15: Phase 24 planned. User: per-user collection Excel column order (combined list, hide / show), MCC /
  VLCC logins use their owner's order (MCC-created VLCC → MCC's creator), upward edit rights, deleted rows in red,
  Chart Rank / Quantity Mode / Measurement Mode. DECISION-030, REQ-53 to REQ-57. Phases 22 and 23 were committed
  (bc2328f / ee6669d, 11777d4).

- 2026-11-14: Phase 23 (uncommitted, same working tree as Phase 22): reports print each member on its own page (`report_preview.html` page breaks, new `static/js/report_print.js` prints from a frame). Headless Chrome PDF: 3 members -> 3 pages.

- 2026-11-14: Phase 22 on `feature/mcc-shift-delay`. User: MCC Shift Delay ("HH:MM", default 00:00) in the MCC form and sync; web MCC entries saved at now - delay; entry date and shift read-only and live on both collection forms, shift from the unit's timings. DECISION-029, REQ-50 to REQ-52, migration `0003`. /verify on PostgreSQL 16/16. Found: MCC and VLCC collection edit pages fail (stale `collection_number`), not linked from any page; not fixed.
- 2026-11-13: `docs/MARKETPLACE_API.md` rewritten for app developers (uncommitted, carried on the working tree).
- 2026-11-12: Phase 21 committed (f2d93a1).

- 2026-11-12: Plan 20.3 and Phase 21 on `feature/collection-excel-export`. User: Sub Admin VLCC / farmer Excel failed on PostgreSQL only; asked for MCC / VLCC collection Excel export. Root cause: untyped `literal(owner.id)` in `Hierarchy` with asyncpg UUIDs; also soft delete overflowed `users.mobile` VARCHAR(20) on PostgreSQL. Migration `0002`. DECISION-028, REQ-48, REQ-49. Suites: 972 passed on PostgreSQL and on SQLite, only the known order-dependent failure. /verify on PostgreSQL passed.
- 2026-11-12: `bugfix/mcc-credentials-update` committed (4b56c89): MCC edit no longer double-hashes the password.
- 2026-11-11: Phase 20 (PostgreSQL Support) on `feature/postgresql-support`, from `bugfix/mcc-weight-hide-analyzer-type` (8194f01). DECISION-025, DECISION-026. Plans 20.1 and 20.2 done and verified on SQLite (946 passed, 1 order-dependent failure that passes alone; real legacy DB copy adopted with every row kept). **Blocked:** Plan 20.3 needs the user's local PostgreSQL and its connection details.
- 2026-11-09: Phase 18 executed and verified: Visible Member on FAT / SNF and Fixed Rate MCCs. Full suite: 918 passed, and the 1 failure also occurs on `a345c6f`.
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
| Collection export | Excel job, filters in `params.json`, list scope, no deleted rows (DECISION-028) | 2026-11-12 | Phase 21 |
| Web entry time | Server stamps now - MCC shift delay; shift from morning end; API unchanged (DECISION-029) | 2026-11-14 | Phase 22 |
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

- None. (Plan 20.3 ran on a portable PostgreSQL 16 from `pip install pgserver` in a Python 3.12 scratch venv, with `tzdata`'s zoneinfo copied to its `share/postgresql/timezone`.)

## Concerns

- **SQLite savepoints (pre-existing, found in Phase 28):** nested `database.transaction()` uses `begin_nested()`, but
  the SQLite engine has no pysqlite BEGIN / isolation_level recipe, so releasing a savepoint commits and an outer
  rollback cannot undo it. A handler that wrote inside a nested transaction and the request then failing keeps
  those rows on SQLite (PostgreSQL is correct). Fix = the SQLAlchemy "serializable isolation / savepoints" recipe
  for pysqlite/aiosqlite on the engine; not done because it changes transaction behaviour app-wide.

- MCC and VLCC collection edit (`/mcc-collections/edit/{id}`, `/vlcc-collections/edit/{id}`) fail: the controllers read `collection_number`, which the DTOs and models no longer have. No page links to them. Found in Phase 22, not fixed.

- MCC edit fails with 422 when the FAT / SNF limits were left blank: the form sends the text "None" (found in Phase 18, not fixed).
- PostgreSQL servers: users whose password was changed from the MCC edit form before 4b56c89 must have it set again once.
- `test_owner_options_super_admin` is order-dependent: the owner list is paged (20) and sorted by name, so with many users in the session the Super Admin can fall off page 1.
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
