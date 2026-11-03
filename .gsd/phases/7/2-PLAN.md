---
phase: 7
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/web/recycle_bin/router.py
  - app/web/recycle_bin/controller.py
  - app/web/router.py
  - app/web/templates/pages/recycle_bin/list.html
  - app/web/templates/pages/recycle_bin/partials/confirm.html
  - app/modules/dashboard/presentation/navigation.py
  - tests/test_recycle_bin.py
must_haves:
  - "Recycle Bin" appears under General for Super Admin only
  - Tabs per entity type with search + pagination; each row has a Permanently Delete button
  - The confirm dialog shows what will be removed (tree + data counts) before the delete runs
---

# Plan 7.2: Recycle Bin web page & tests

## Tasks

<task type="auto">
  <name>Task 1: Web routes, controller, navigation</name>
  <files>app/web/recycle_bin/*, app/web/router.py, app/modules/dashboard/presentation/navigation.py</files>
  <action>
    - `GET /recycle-bin?type=&search=&page=` (page), `GET /recycle-bin/{type}/{id}/impact` (confirm partial),
      `POST /recycle-bin/{type}/{id}/purge` (HTMX; success toast + row removed).
    - Navigation: `Recycle Bin` (`fa-solid fa-trash-can`, `SUPER_ADMIN_ONLY`) in the General group.
    - AVOID: a JSON API — the feature is web-panel only.
  </action>
  <verify>Admin login gets 403 on every recycle-bin route; Super Admin sees the menu item.</verify>
  <done>Page renders for Super Admin.</done>
</task>

<task type="auto">
  <name>Task 2: Templates</name>
  <files>app/web/templates/pages/recycle_bin/list.html, app/web/templates/pages/recycle_bin/partials/confirm.html</files>
  <action>
    - Follow `pages/sub_admin/list.html` styling (table, search, pagination).
    - Confirm modal lists counts (users by role, active records in the tree, collections, payments, rate charts…)
      and requires typing the record code / name before the delete button enables.
  </action>
  <verify>Rendering both templates with sample data succeeds.</verify>
  <done>User can purge from the page.</done>
</task>

<task type="auto">
  <name>Task 3: Tests (real SQLite)</name>
  <files>tests/test_recycle_bin.py</files>
  <action>
    - Soft delete of a Sub Admin; listing per type; non-super-admin forbidden; purge of an active
      (not deleted) record refused; VLCC purge removes farmers / collections / dispatches / payments and
      restores the surviving MCC balance; Admin purge removes its whole tree; Super Admin never purged.
  </action>
  <verify>`.venv\Scripts\python.exe -m pytest tests/test_recycle_bin.py`</verify>
  <done>All green, full suite unchanged.</done>
</task>
