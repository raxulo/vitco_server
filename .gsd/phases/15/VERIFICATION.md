# Phase 15 Verification: Public API, SEO & Launch Hardening

**Date:** 2026-11-09
**Verdict:** Pass, with the final visual sign-off still with the user (NFR-15)

## Test suite

Full suite including `test_large_import_throughput`: **831 passed, 1 failed**. The failure is `test_owner_options_super_admin`, which also fails on `a345c6f` (see Phase 8) and passes when run alone.

`test_large_import_throughput` failed on both commits in Phase 8 and passes now that SQL is no longer logged.

## Performance (NFR-16)

Real server, one process, on an isolated database with 1,000 products and 1,000 animals, which is twice the target catalog. The load client ran on the same machine. 200 requests per page, p95 in ms:

| Page | One at a time | 5 at once | 10 at once |
|------|---------------|-----------|------------|
| Home | 42 | 145 | 311 |
| Products | 30 | 133 | 321 |
| Products, page 20 | 33 | 143 | 324 |
| Products, search | 31 | 180 | 313 |
| Animals | 23 | 97 | 256 |
| Animals, filtered | 43 | 107 | 228 |
| Product detail | 25 | 106 | 226 |
| Animal detail | 24 | 97 | 230 |
| Site search | 36 | 141 | 355 |
| Sitemap (2,027 links) | 48 | 276 | 643 |
| API home | 33 | 147 | 325 |
| API products | 23 | 119 | 252 |

- The target is met one at a time and with 5 requests always in flight.
- With 10 always in flight, which is about 35 requests a second, home and product list pages are slightly over 300 ms (311 to 324 ms). That is the capacity of one process on this machine.
- These numbers are from a development machine. The server has not been measured.

## Parallel orders on the real server

100 orders, 20 at a time, for a size with 50 in stock:

| Result | Count |
|--------|-------|
| Placed (`201`) | 50, all with different references |
| Out of stock (`409`) | 12 |
| Total changed, because the item had sold out (`422`) | 38 |
| Stock afterwards | 0 |
| Order lines for that size | 50 lines, 50 pieces |

Nothing oversold and nothing failed with a server error. This run was before the logging fix.

## Accessibility (NFR-15)

axe-core 4.10.2 in real Chrome, rules WCAG 2.0 and 2.1 A and AA plus best practices. 12 store pages and 14 Control Center pages at 1440 px and 390 px, 52 checks in all.

| | Before fixes | After fixes |
|---|---|---|
| Rules failing | 7 | 0 |
| Pages with a violation | Most | 0 |

Keyboard:
- On store pages the first Tab stop is "Skip to content". Control Center pages have no skip link and start at the logo.
- 14 Tab stops were checked on each of 4 store pages and 3 Control Center pages, and all show focus.
- Sidebar groups open and close with Enter, Space and the mouse.

Limits of this check:
- axe can't judge text over a photo, so banner text needs checking once real photos are in.
- No screen reader was used.

## Shared shell

Dashboard, MCC list and Control Center were opened after the landmark changes: `<main>` present and no sideways scroll, on desktop for all and on a 390 px phone for the Control Center.

## Security (NFR-17)

| Check | Result |
|-------|--------|
| 21st tracking attempt on the real server | `429` with `Retry-After`; the website form was then also `429` |
| API never exposes seller ids, exact stock or tracked buyer details | Tested |
| Wrong reference and wrong phone give the same answer | Tested |
| Client can't set price, status or payment | Tested |
| Hostile title in JSON-LD | Inert, and still correct for search engines |
| `\|safe` or `innerHTML` in store and Control Center code | None |
| SQL values in logs | 1.5 MB of log in a full audit run, down from over 200 MB; tested with `DATABASE_ECHO` off and on |

## No CDN (NFR-18)

No script, style or font loads from another site. The only outside links are `wa.me` links that people click.

## Isolation

Every run used its own database. The checksum of `storage/database/realtime_transfer.db` was the same before and after each audit and the final test run.

**Exception:** logs ignore `LOG_PATH` and always go to the relative `logs/` folder. Audit runs before the logging fix wrote about 230 MB of test SQL to `logs/application.log*` in this workspace. The folder is ignored by git. Rotation may also have pushed out older local log lines. The files were left for the user to remove.
