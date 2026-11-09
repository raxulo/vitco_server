# Phase 10 Verification: Control Center — Catalog

**Date:** 2026-11-09
**Verdict:** Pass

## Test suite

Full suite without `test_large_import_throughput`: 475 passed, 1 failed. The failure is
`test_owner_options_super_admin`, which also fails on `a345c6f` (see Phase 8). The throughput test was excluded because it
takes about 2 minutes and already fails on this machine without any of this work.

## Runtime check in real Chrome

Real server on an isolated database and media folder. Demo listings were created through the real forms, with real uploads.

| Check | Result |
|-------|--------|
| 7 pages at 1440 px, 1200 px and 390 px | No horizontal overflow |
| Add and remove a size row | Row count and row index update, focus moves to the new row |
| Breed list after choosing Buffalo | Only buffalo breeds are selectable |
| Pregnant status | "Months pregnant" computed display goes from `none` to `block` |
| Male animal | Milk and lactation section computed display goes from `block` to `none` |
| Delete dialog | Opens with the listing's name; Cancel keeps the row; Delete removes it and shows "Deleted." |
| Server log | No tracebacks |
| Development database | Checksum unchanged |

Console errors: only 404s for `/static/images/favicon.ico` and the avatar of a user without a profile image. Neither comes
from the Control Center.

## Found by looking at screenshots, then fixed

- The sizes table overflowed its card and two headers ran together.
- The search icon overlapped the placeholder.
- The sidebar group closed on Control Center sub-pages.
- "Months pregnant" stayed visible because `.mk-field` overrode the `hidden` attribute. The first browser check read only
  the attribute and passed, so it now reads the computed style.

## Must-haves

- [x] Every catalog write calls `SellerPolicy`; masters are Super Admin only
- [x] Publishing without a size or image is refused, and draft saving is allowed
- [x] A broken or oversized image never reaches storage
- [x] Only sellers reach the panel, tested with 5 other roles for reads and 2 for writes
- [x] Validation errors keep the entered values and name the field
- [x] Create, edit, publish and delete work through the real app
- [x] Responsive at 1440, 1200 and 390 px

## Limits

- Gallery arrows and image removal were checked on the server through the kept-image order, not clicked in the browser.
- Keyboard use was not walked through end to end. Controls are native and have visible focus styles.
- Contrast was chosen for WCAG AA but not measured. Phase 15 runs the accessibility audit.
- The overview's order and enquiry tiles stay at 0 until Phases 13 and 14 create those records.
- REST admin API is deferred to Phase 15.
- Removing a product soft-deletes it and keeps its images, so they stay in storage.
