# Phase 11 Verification: Control Center — Merchandising & Settings

**Date:** 2026-11-09
**Verdict:** Pass

## Test suite

Full suite without `test_large_import_throughput`: 555 passed, 1 failed. The failure is `test_owner_options_super_admin`,
which also fails on `a345c6f` (see Phase 8).

## Runtime check in real Chrome

Real server on an isolated database and media folder, with demo content created through the real forms.

| Check | Result |
|-------|--------|
| Banners, Home page and Store settings at 1440, 1200 and 390 px | No horizontal overflow; screenshots reviewed |
| Banner states | Live, Scheduled, Expired and Off all shown correctly |
| Move a home section down | Order changes after the real form submit |
| Server log | No tracebacks |
| Development database | Checksum unchanged |

## Must-haves

- [x] Only Super Admin changes store content and settings, tested with 4 other roles
- [x] Unsafe links (`javascript:`, `data:`, `//host`, control characters) are refused
- [x] A banner is live only inside its window, at its placement, when active
- [x] Built-in home sections can be hidden but not deleted
- [x] Replaced or deleted images leave storage
- [x] Invalid input returns 422 with typed values kept

## Limits

- These settings take effect for customers in later phases: home content in Phase 12; contact numbers in Phase 13; delivery
  charge, minimum order, pincodes, COD and the open or closed switch in Phase 14.
- Times are entered and shown as IST. No other time zone is offered.
