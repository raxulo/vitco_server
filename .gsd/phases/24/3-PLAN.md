---
phase: 24
plan: 3
wave: 3
depends_on: [2]
files_modified:
  - app/web/sub_admin/controller.py
  - app/web/sub_admin/router.py
  - app/web/auth/controller.py
  - app/web/templates/pages/sub_admin/column_layout.html
  - app/web/templates/pages/sub_admin/list.html
  - app/web/templates/pages/sub_admin/view.html
  - app/web/templates/pages/auth/profile.html
  - app/web/static/js/column_layout.js
  - tests/dataexchange/test_column_layout_web.py
must_haves:
  - Super Admin, Admin and Sub Admin open "Excel Column Order" from their profile and change their own layout
  - Super Admin (any Admin / Sub Admin) and Admin (own Sub Admins) open it from the user's list / view page
  - The page reorders by drag and drop and by up / down buttons (keyboard), shows / hides columns, saves and resets
gap_closure: false
---

# Plan 24.3: "Excel Column Order" web page

## Objective
Let users manage the layout on the website (REQ-55, REQ-57).

## Tasks

<task type="auto">
  <name>Page and links</name>
  <files>sub_admin controller / router, auth controller, column_layout.html, list / view / profile templates,
  column_layout.js</files>
  <action>`GET /sub-admin/column-layout[?user_id=]` renders the list (header, MCC / VLCC badges, visible toggle,
  up / down buttons, drag handle); `POST` saves through `ColumnLayoutHandler`, "Reset to default" calls reset.
  Links: profile (managers only), Admin / Sub Admin list row actions and view page when `can_manage`.
  Same permission rules as the API; flash message after save.
  AVOID: a new JS library (native drag and drop); hiding the last visible column (button disabled + server 422).</action>
  <verify>web tests: allowed and refused users per rule; save then export follows it; /verify in real Chrome on
  Postgres as Super Admin, Admin, Sub Admin, MCC and VLCC: open the downloaded files</verify>
  <done>The order saved on the page is the order in the MCC and VLCC downloads of that user and its MCCs / VLCCs.</done>
</task>
