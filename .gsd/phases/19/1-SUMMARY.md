---
phase: 19
plan: 1
status: complete
commit: pending user approval
---

# Plan 19.1 Summary: List Pagination & MCC Milk Specs

Branch `feature/list-pagination`, from `feature/mcc-visible-member`. Requested by the user.

## Pagination
- `components/pagination.html` with `app/web/framework/pagination.py` shows First, Prev, the current page with two pages either side, Next and Last. Page 10 of 20 shows 8 9 10 11 12.
- Near the ends the window slides, so five numbers stay visible.
- Links are built from the current URL with only `page` changed, so every search and filter is kept.
- Used by farmers, VLCCs, MCCs, rate charts, VLCC and MCC collections, units, routes, items, sub admins, advance items, Recycle Bin and VLCC dispatches. The Control Center lists use the same window in their own style.
- Removed the collection lists' separate pager and `page_window`.

## MCC collection list
- New Milk Specs column: milk type and FAT / SNF to two places. Entries without a reading show "—".

## Not changed
The customer store's product and animal lists keep their Previous / Next pager.
