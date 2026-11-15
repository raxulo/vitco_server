---
phase: 24
plan: 3
status: complete
verified: 2026-11-15
---

# Plan 24.3 Summary: "Excel Column Order" web page

## Delivered (REQ-55, REQ-57)
- `/sub-admins/column-layout[?user_id=]` (GET page, POST save, POST `/reset`) in `ColumnLayoutController`; same
  handler and rules as the API. Save shows a success toast; a refused save an error toast; reset reloads the page.
- `pages/sub_admin/column_layout.html` + `static/js/column_layout.js` (no library): drag and drop, up / down
  buttons that keep keyboard focus, show / hide checkbox, MCC / VLCC badges, live preview of both header rows,
  Save disabled with a warning when an export would have no column, "Reset to default" disabled while on default.
- Links: "Excel Column Order" on the profile (Super Admin / Admin / Sub Admin), on the Admin / Sub Admin list
  rows and on the view page (own, or an Admin / Sub Admin the viewer manages).

## Verification
- `tests/dataexchange/test_column_layout_web.py`: 12 passed on SQLite and PostgreSQL.
- /verify on a real server + exchange worker with PostgreSQL: 29 of 30 checks passed; the one miss was the check's
  own expectation (a partial API list re-inserts left-out columns after their default predecessor, as documented).
  Downloaded files: defaults, red deleted row, Sub Admin's web-saved order in its own, its MCC's, its VLCC's and
  the MCC-made VLCC's MCC / VLCC files, other Admin unchanged, Super Admin edit, Admin reset. No server errors.
  `node --check` on the JS.
- Not checked in a real browser: the drag and drop itself (markup, form posts and JS syntax were checked).

## Follow-up: sidebar entry + page redesign (user request)
- Sidebar "System Setup" -> "Excel Maps" (`/sub-admins/column-layout`) for Super Admin / Admin / Sub Admin
  (`dashboard/presentation/navigation.py`). The own page has no Back button; another user's page goes back to them.
- Page redesigned: breadcrumb, page actions in the header (status, Discard, Reset, Save; no sticky bar),
  a flat "You are editing the column order of X" strip with a Back link for another user's order, live counters (shown / MCC / VLCC columns), toggle switches,
  hover arrows + Alt+ArrowUp/Down, drop-position line, MCC / VLCC tabbed spreadsheet preview with column letters
  (A, B…), "Good to know" notes, unsaved-changes status and a leave-page warning; Save is enabled only when
  something changed.
- 8 more tests (sidebar item per role, link on the page); 144 passed across layout + navigation suites.
  Checked by screenshots at 1440px and 390px (headless Edge); real drag and drop still not exercised.

## Also
- `tests/dataexchange/test_vlcc_api.py::test_owner_options_super_admin` (the known order-dependent failure) now
  searches by a unique tag, so other tests' Admins can't push its users off the first page.
- Full suite on SQLite (throughput test excluded): 1050 passed, 1 failed (that test, fixed afterwards and passing).
  `test_large_import_throughput[100000]` ran at 312 rows/s on this busy machine (bar 1,000), untouched by this phase.
