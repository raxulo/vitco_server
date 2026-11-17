---
phase: 26
plan: 3
wave: 3
depends_on: [1, 2]
files_modified:
  - app/web/support/tickets_controller.py
  - app/web/support/categories_controller.py
  - app/web/templates/support/pages/tickets/*.html
  - app/web/templates/support/pages/categories/*.html
  - app/web/static/js/support.js
  - app/web/static/css/support.css
  - tests/support/test_ticket_screens.py
must_haves:
  - Queues - Unassigned, All tickets, My tickets, each shown only with the right permission
  - Ticket detail is a 3-part screen - conversation and composer, requester card, ticket meta and timeline
  - Reply / internal-note toggle, assign, status, priority actions appear only with permission
  - Requester card shows basic profile, MCC / VLCC info, phone, device and app version; never dairy data
  - Super Admin manages categories and default teams; routes unassigned tickets to a team
gap_closure: false
---

# Plan 26.3: Portal queues, ticket detail and categories

## Objective
The daily working screens of a support member, in the design of docs section 10A (REQ-62, REQ-72, REQ-66, REQ-65).

## Context
- Plans 25.2 (components) and 26.1; docs/TECHNICAL_SUPPORT_PLAN.md sections 9 and 10A

## Tasks

<task type="auto">
  <name>Queues and filters</name>
  <files>tickets_controller.py, pages/tickets/list.html</files>
  <action>One list screen with three scopes and a filter bar (status chips, priority, category, assignee, search by
  ticket no / subject / requester name or phone, date range), keyset pagination, row = ticket number, subject,
  requester + role chip, category, priority dot, status chip, assignee avatar, age. Unread dot per row. Empty state per
  scope. Counts for the sidebar badges from one query.
  AVOID: N+1 queries (load requester and assignee in the list query).</action>
  <verify>query-count test for 50 rows; permission tests per scope</verify>
  <done>Lists are fast and each role sees only its scopes.</done>
</task>

<task type="auto">
  <name>Ticket detail and actions</name>
  <files>pages/tickets/detail.html, partials, categories pages</files>
  <action>Conversation with bubbles (requester, staff, internal-note style, system events), composer with
  Reply / Internal note toggle and attachment button (HTMX posts, no full reload). Right column: requester card
  (name, role, MCC / VLCC name, phone with copy, device model, OS, app version), ticket meta with inline controls
  (assign dropdown of team members, status, priority, category) and the timeline. Resolve / close / reopen with confirm
  dialogs. Categories screen for Super Admin (name, default team, active). Unassigned tickets get a "Send to team"
  action for Super Admin.
  AVOID: showing any collection, payment or ledger data; a second primary button on the page.</action>
  <verify>tests for visibility and actions per permission; headless screenshots at 1440 and 390 px; user visual review</verify>
  <done>A member can open, reply, note, assign and resolve a ticket end to end without leaving the page.</done>
</task>

## Must-Haves
- [ ] Viewer role sees tickets read-only with no action controls

## Success Criteria
- [ ] Tests green; Phase 26 verification written; commit message proposed
