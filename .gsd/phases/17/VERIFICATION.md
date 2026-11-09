# Phase 17 Verification: Collection Totals & Filters

**Date:** 2026-11-09
**Verdict:** Pass, waiting for the user's review and commit approval

## Test suite

Full suite, before the final restyle: **901 passed, 1 failed**. The failure is `test_owner_options_super_admin`, which also fails on `a345c6f`. After the restyle, which changed only CSS and templates, the 71 collection-related tests pass.

`tests/test_collection_list_filters.py` covers totals across pages, weighted averages, deleted entries, every filter, the shift range, access scope for each role, the pager and hand-edited links.

## Real Chrome, isolated database

1,080 VLCC collections (12 deleted) and 180 MCC collections.

| Check | Result |
|-------|--------|
| Totals against direct SQL, VLCC | Quantity 11155.12, amount 475677.73, FAT 5.33, SNF 8.50, entries 1068: all match |
| Totals against direct SQL, MCC | Quantity 28065.98, amount 900090, FAT 4.80, SNF 8.60, entries 180: all match |
| Filling and submitting the form | Rows and totals change together, and the next-page link keeps the filters |
| Clear button | Clears every filter |
| Sideways scroll at 360, 390, 768, 1100 and 1440 px | None |
| axe-core on the new header, totals, filters and pager | No violations on either page |
| Server errors | None |
| Real database | Checksum unchanged |

## Found by the SQL check

Average SNF showed 8.49% when every entry was exactly 8.5, and a regression test then showed FAT at 4.09% when every entry was 4.1. There were two causes:
- SQLAlchemy rounded each summed quantity × FAT to the Numeric column's 2 places before the division, so 279.415 became 279.41. The sums are now read as plain numbers.
- Float addition can leave 8.4999999, which the app's truncation would cut to 8.49. Averages are now settled to 4 places before truncating.

Both have regression tests.

## Not fixed

axe also reports two problems in the existing tables, which this phase did not change: row checkboxes have no label, and some small grey text is low contrast.

## Not checked

- Speed on a very large list. The totals query scans every matching row. It was only run on about 1,000 rows, so it should be watched on the server, where a list can have many more.
