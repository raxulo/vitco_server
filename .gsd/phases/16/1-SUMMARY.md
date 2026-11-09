---
phase: 16
plan: 1
status: complete
commit: pending milestone commit (user: commit after all phases)
---

# Plan 16.1 Summary: Control Center & Store Visual Refresh

Requested by the user after Phase 15. URLs and buying rules are unchanged.

**Control Center**
- Uses the app's blue accent; green is kept for status only.
- A header card with "View store" and grouped tabs: Overview, then sales, catalog, and storefront.
- Orders and Enquiries show their new counts on every page, loaded by a router dependency.
- Overview puts orders and enquiries first and adds a Latest orders list.
- Quieter tables and row actions, and a soft focus ring on fields.

## Store redesign undone (user, 2026-11-09)

After seeing it, the user asked for the store to go back to its earlier look. These were reverted:
- White canvas and the new palette
- Borderless cards
- Lighter doors
- Trust row

The cream, forest green and ghee gold design of DECISION-020 is back. Category tiles keep their icons in place of the first letter. The Control Center changes stay.

## Demo data

`scripts/seed_marketplace_demo.py` adds 12 products, 10 animals, 5 banners, 5 trending links and blank store settings. It can run again safely, and `--remove` takes out only what it added. It refuses to run in production, and it opens only the database, so it can't disturb Excel jobs on a running server. Pictures are drawn icons on gradients, not photographs.
