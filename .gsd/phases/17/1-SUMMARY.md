---
phase: 17
plan: 1
status: complete
commit: pending user approval
---

# Plan 17.1 Summary: Collection Totals & Filters

Branch `feature/collection-summary-filters`, from the tip of `feature/marketplace-revamp`, because `develop` is 37 commits behind and lacks this work line.

- **Totals on both lists:** Total Qty, Total Amount, Avg. FAT, Avg. SNF and Total Entries. They come from the database and cover every matching entry, not one page.
- **VLCC filters:** farmer search, VLCC shop, milk type, start and end date, start and end shift.
- **MCC filters:** VLCC search, MCC, supplying VLCC shop, milk type, start and end date, start and end shift.
- **Roles:** a VLCC doesn't see the shop filter, an MCC doesn't see the MCC filter, and a farmer or VLCC viewing their own entries sees only what applies. Every filter stays inside the user's access scope.

## Look

The first version followed the reference images, with large cards and fonts. The user asked for it to match the rest of the app, so these pages keep their earlier look: 20px heading, "Collections Found" badge, New Collection button, Apply Filter and Clear buttons, small white cards and 13 to 14px text.

## Behaviour worth knowing

- A shift with its date is a range boundary, such as 1 Nov evening to 5 Nov morning. A shift without a date means that shift only.
- Search on these pages now looks only at the farmer (VLCC list) or the VLCC (MCC list). It used to match the VLCC and MCC names too, which now have their own filters.
- Deleted entries stay visible in the list, but totals leave them out and show how many were left out.
- Averages are weighted by quantity and skip entries with no FAT or SNF reading.

## Changes outside the plan

- The pager showed one link per page, over 1,000 links for 11,000 entries. It now shows the current page, its neighbours and both ends, and it keeps every filter.
- `limit=0` in a link crashed the page with a division by zero. `limit` is now kept between 1 and 100.

## Left out

Payment Status, the Limit dropdown and Excel Export appear in the reference images but weren't in the requested filter list.
