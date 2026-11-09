---
phase: 17
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/collections/mcc_collection/domain/listing.py
  - app/modules/collections/mcc_collection/infrastructure/listing_sql.py
  - app/modules/collections/mcc_collection/infrastructure/repository.py
  - app/modules/collections/vlcc_collection/infrastructure/repository.py
  - app/web/framework/collection_list.py
  - app/web/mcc_collection/controller.py
  - app/web/vlcc_collection/controller.py
  - app/web/templates/pages/collections_shared/_list_ui.html
  - app/web/static/css/collections.css
  - tests/test_collection_list_filters.py
must_haves:
  - Totals cover every entry matching the filters, not only the current page
  - Totals are limited to what the user may see and leave out deleted entries
  - Start and end shift work with the dates as one range
gap_closure: false
---

# Plan 17.1: Collection Totals & Filters

## Objective
On the VLCC and MCC collection lists, show total quantity, total amount, average FAT, average SNF and total entries for the current search and filters.

**Filters**
- VLCC: farmer search, VLCC shop, milk type, start date, end date, start shift, end shift.
- MCC: VLCC search, MCC, supplying VLCC shop, milk type, start date, end date, start shift, end shift.

## Decisions
- Averages are weighted by quantity, as on the dashboard and in reports. Entries without a FAT or SNF reading don't count towards them.
- Deleted entries stay visible in the list but are left out of totals.
- Quantity is labelled KG, the same as the table below it.

## Tasks

<task type="auto">
  <name>Filters and totals</name>
  <files>listing.py, listing_sql.py, both repositories and handlers</files>
  <action>
    Add the filters to the existing list and count queries, and add a totals query using the same conditions.

    AVOID: adding up rows in Python or in the template, because that only sees one page.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/test_collection_list_filters.py -q</verify>
  <done>Totals, scope, shift range and search are proven against a real database.</done>
</task>

<task type="auto">
  <name>Pages</name>
  <files>both controllers and list.html, _list_ui.html, collections.css</files>
  <action>
    Header card, five totals, filter card and pagination that keeps every filter. Filters a role can't use are hidden.
  </action>
  <verify>Screenshots in real Chrome on an isolated database at 1440, 768 and 390 px; axe-core run</verify>
  <done>Reviewed against the user's reference images.</done>
</task>
