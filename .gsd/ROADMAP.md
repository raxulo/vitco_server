---
milestone: Excel Data Exchange
version: 1.1.0
updated: 2026-10-25T00:00:00+05:30
---

# Roadmap

> **Current Milestone:** v1.1.0 — Excel Data Exchange
> **Goal:** Farmers, VLCCs and Prodata rate-chart rows can be exported to and imported from Excel
> (web panel + mobile API), streamed so that very large data sets never crash the server or lose data.
> **Current Phase:** 1 - Exchange Foundation
> **Status:** Planning
> **Branch:** `feature/excel-import-export` (from `develop`)
> **Previous milestone:** [v1.0.0 — Core Dairy ERP & APIs](milestones/v1.0.0/ROADMAP.md)

## Must-Haves (from SPEC Goal 6)

- [ ] Farmers of one selected VLCC export to / import from Excel (upsert by farmer code)
- [ ] VLCCs of one selected Admin / Sub Admin export to / import from Excel (upsert by VLCC code), including user, address, bank, settings and milk quality columns
- [ ] Prodata rate-chart rows export to / import into an existing chart (all-or-nothing replace)
- [ ] One job-based REST API serves both the web panel and the mobile app
- [ ] Selection rules follow the login role (locked when the role has only one choice) and are enforced on the server
- [ ] Every import reports total / inserted / updated / discarded and offers a discarded-rows file
- [ ] **Never freeze, lag or crash, whatever the data size** (user rule): jobs run in a separate supervised worker process; memory, DB-lock time, disk and queue length are bounded; proven with a 1,000,000-row load test and kill tests (NFR-01 … NFR-14)

## Nice-to-Haves

- [ ] Dry-run (validate-only) import
- [ ] Cancel a running job
- [ ] Resume an interrupted import from the last committed batch

---

## Phases

### Phase 1: Exchange Foundation
**Status:** ✅ Complete (verified at runtime 2026-10-25, commit 8d51666)
**Objective:** Build the reusable, crash-proof `dataexchange` foundation: job table, separate supervised worker process, streaming xlsx with any row count, hostile-file and disk guards, disk-backed duplicate detection, resumable uploads and job APIs — so each later phase only adds an entity adapter.
**Requirements:** REQ-01 … REQ-05, NFR-01 … NFR-14
**Decisions:** DECISION-001, 002, 007, 008, 009, 010, 011
**Discovery:** Level 2 — see [phases/1/RESEARCH.md](phases/1/RESEARCH.md)

**Plans:**
- [x] Plan 1.1: Job domain & persistence (wave 1) — [1-PLAN.md](phases/1/1-PLAN.md)
- [x] Plan 1.2: Column specs & streaming xlsx (wave 2) — [2-PLAN.md](phases/1/2-PLAN.md)
- [x] Plan 1.3: File safety — storage, hostile-file guard, disk guard, duplicate store (wave 2) — [3-PLAN.md](phases/1/3-PLAN.md)
- [x] Plan 1.4: Worker process engine (wave 3) — [4-PLAN.md](phases/1/4-PLAN.md)
- [x] Plan 1.5: Supervisor, handler & backpressure (wave 4) — [5-PLAN.md](phases/1/5-PLAN.md)
- [x] Plan 1.6: Resumable upload & job REST API (wave 5) — [6-PLAN.md](phases/1/6-PLAN.md)

---

### Phase 2: Farmer Excel Exchange
**Status:** ✅ Complete (verified at runtime 2026-10-25 — [VERIFICATION.md](phases/2/VERIFICATION.md)); phase commit pending approval
**Objective:** Export, template and upsert import of the farmers in one selected VLCC, with VLCC selection by role.
**Requirements:** REQ-06, REQ-07, REQ-08, REQ-09, REQ-10, REQ-11
**Depends on:** Phase 1

**Discovery:** Level 1 — see [phases/2/RESEARCH.md](phases/2/RESEARCH.md) (measured: SQLite ceiling ~2,300 farmers/s, Core bulk 2,068/s, `lower(email)` index 64 → 17 ms)

**Plans:**
- [x] Plan 2.1: Farmer sheet, bulk repository & export (wave 1) — [1-PLAN.md](phases/2/1-PLAN.md)
- [x] Plan 2.2: Farmer import pipeline (wave 2) — [2-PLAN.md](phases/2/2-PLAN.md)
- [x] Plan 2.3: VLCC scope, farmer endpoints & end-to-end (wave 3) — [3-PLAN.md](phases/2/3-PLAN.md)

---

### Phase 3: VLCC Excel Exchange
**Status:** ✅ Complete (verified at runtime 2026-10-25 — [VERIFICATION.md](phases/3/VERIFICATION.md)); phase commit pending approval
**Objective:** Export, template and upsert import of the VLCCs owned by one selected Admin / Sub Admin, covering user, VLCC, address, bank, settings and milk quality columns.
**Requirements:** REQ-12, REQ-13, REQ-14, REQ-15, REQ-16
**Depends on:** Phase 2 (reuses the import pipeline built there)

**Plans:**
- [x] Plan 3.1: VLCC column spec (44 columns), template & export — [1-PLAN.md](phases/3/1-PLAN.md)
- [x] Plan 3.2: VLCC import (`created_by` = owner, `code_conflict`, settings & milk quality) — [2-PLAN.md](phases/3/2-PLAN.md)
- [x] Plan 3.3: Owner options API & VLCC endpoints — [3-PLAN.md](phases/3/3-PLAN.md)


---

### Phase 4: Prodata Rate-Chart Excel Exchange
**Status:** ✅ Complete (verified at runtime 2026-10-25 — [VERIFICATION.md](phases/4/VERIFICATION.md))
**Objective:** Export the rows of a Prodata chart and replace them from Excel in one all-or-nothing transaction.
**Requirements:** REQ-17, REQ-18
**Depends on:** Phase 1

**Plans:**
- [x] Plan 4.1: Prodata column spec, template & export — [1-PLAN.md](phases/4/1-PLAN.md)
- [x] Plan 4.2: Prodata import (range / overlap validation, atomic replace) & endpoints — [2-PLAN.md](phases/4/2-PLAN.md)

---

### Phase 5: Web Panel & Hardening
**Status:** ⬜ Not Started
**Objective:** Export / import buttons, selection dropdowns and live progress on the web panel; prove "never freeze, lag or crash" with load and chaos tests.
**Requirements:** REQ-19, NFR-01 … NFR-14
**Depends on:** Phases 2, 3, 4

**Plans (draft — finalised by `/plan 5`):**
- [ ] Plan 5.1: Web panel UI (HTMX progress with `poll_after_ms`, locked dropdowns, summary card, chunked upload in the browser)
- [ ] Plan 5.2: Load test & tuning — 100k / 1M / 5M farmer rows import + export while a traffic generator hits normal endpoints; record worker RSS, API p95 / p99, event-loop lag, "database is locked" count (must be 0) (checkpoint: human-verify)
- [ ] Plan 5.3: Chaos test — kill the worker mid-import, kill the API mid-upload, fill the disk, upload zip bomb / XML bomb / padded sheet; every case ends in a clean, explained state with no half-written rows
- [ ] Plan 5.4: Mobile API guide for the app team (upload → submit → poll → download flow, error codes, Retry-After)

---

## Progress Summary

| Phase | Status | Plans | Complete |
|-------|--------|-------|----------|
| 1 | 🔄 | 0/6 | — |
| 2 | ⬜ | 0/3 | — |
| 3 | ⬜ | 0/3 | — |
| 4 | ⬜ | 0/2 | — |
| 5 | ⬜ | 0/4 | — |

---

## Timeline

| Phase | Started | Completed | Duration |
|-------|---------|-----------|----------|
| 1 | 2026-10-25 | — | — |
| 2 | — | — | — |
| 3 | — | — | — |
| 4 | — | — | — |
| 5 | — | — | — |

---
*Last updated: 2026-10-25*
