# Phase 12 Verification: Storefront Design System & Home

**Date:** 2026-11-09
**Verdict:** Pass. The user reviewed the screenshots and asked to start Phase 13 with no design changes (2026-11-09), recorded as approval.

## Test suite

Full suite without `test_large_import_throughput`: 587 passed, 1 failed. The failure is `test_owner_options_super_admin`,
which also fails on `a345c6f` (see Phase 8).

## Runtime check in real Chrome

Guest session on a real server with an isolated database and media folder. Demo content was created through the real
Control Center forms. Pictures are blurred placeholders, not photographs.

| Check | Result |
|-------|--------|
| Home at 1440, 1024, 768, 390 and 360 px | No horizontal overflow, no broken images |
| Slideshow pause, play and dots | Work; choosing a dot moves the slide and stops autoplay |
| Console and JS errors | None |
| Server log | No tracebacks |
| Development database | Checksum unchanged |

## Found by review, then fixed

- `.st-offer`: `min-height` with `aspect-ratio` widened it past a 360 px screen, causing 29 px of overflow.
- With banners present, the page had no `h1`.
- Category tiles left empty space on desktop.

## Must-haves

- [x] Standalone design, with no dashboard shell
- [x] Guests open it without login; `/admin/marketplace` and other pages still require login
- [x] Drafts, deleted, archived and sold listings and inactive categories never appear
- [x] Sections follow the Control Center order; empty sections hide themselves
- [x] Query count does not grow with the number of cards
- [x] No outside assets
- [x] User approval of the visual direction

## Limits

- Links to `/marketplace/animals`, `/marketplace/products`, `/marketplace/search`, listing details and policy pages return
  404 until Phase 13.
- Products have no add-to-cart until Phase 14.
- The look has not been seen with real photographs.
- Contrast was chosen for WCAG AA but not measured. Phase 15 runs the accessibility audit.
