# Phase 16 Verification: Control Center & Store Visual Refresh

**Date:** 2026-11-09
**Verdict:** Pass, with the user's visual sign-off still open (NFR-15)

## Test suite

Full suite: **839 passed, 1 failed**. The failure is `test_owner_options_super_admin`, which also fails on `a345c6f`.

New tests: `tests/marketplace/test_ui_refresh_web.py` (tab counts on every page, latest orders, category icons) and `tests/marketplace/test_demo_data.py`.

## Real Chrome, isolated database

| Check | Result |
|-------|--------|
| axe-core on 26 pages at 1440 and 390 px | 52 of 52 clean |
| Keyboard focus on store and Control Center pages | Visible at every stop checked |
| Sideways scroll, store pages at 360, 390 and 768 px | None |
| Sideways scroll, Control Center pages at 360, 390, 768, 1100, 1280, 1366, 1440 and 1920 px | None |
| Tabs at 1366 and 1440 px, read from screenshots | One line; icons only show where they fit |
| Current tab on a phone | Scrolled into view |

The real database checksum was the same before and after each run.

## Found by looking at screenshots

- The Settings tab was cut off, then wrapped onto a second line. Now one line, with icons dropped at laptop widths.

## After the store went back to its earlier look

`store.css` was restored from the copy read before the redesign, with the tile icon as the only change. Re-checked on the demo data: axe-core 52 of 52 clean.

## Demo seeder

| Check | Result |
|-------|--------|
| Add beside a running server, isolated database | 12 products, 10 animals, 5 banners, 5 links |
| Add again | Nothing new |
| Remove | Nothing left, 0 media files |
| Real data during remove (test) | Kept, including the store's own settings |

The user's local database was backed up, then seeded, because the user asked for demo data there.

## Not checked

- Real photographs: the demo pictures are drawn icons, so the look with real photos is unconfirmed.
- The tab row's "2 rows" figure from the width script is unreliable, because a tab with a count sits slightly differently. The screenshots at 1366 and 1440 px are the evidence. Widths around 1100 px weren't reviewed by eye and may wrap to two lines.
