---
phase: 25
plan: 3
wave: 3
depends_on: [1, 2]
files_modified:
  - app/web/support/teams_controller.py
  - app/web/support/members_controller.py
  - app/web/support/roles_controller.py
  - app/web/templates/support/pages/teams/*.html
  - app/web/templates/support/pages/members/*.html
  - app/web/templates/support/pages/roles/*.html
  - app/web/templates/partials/sidebar.html
  - tests/support/test_team_screens.py
must_haves:
  - Super Admin lists, creates, edits, disables teams and sets the manager's login in one form
  - Manager lists, creates, edits, disables members and picks their support role
  - Manager edits role permissions with a clear grouped checklist
  - Every screen has loading, empty, error and success states and respects permissions
gap_closure: false
---

# Plan 25.3: Teams, members and roles screens

## Objective
The management screens of Phase 25 on the new design system (REQ-59 to REQ-61, REQ-65).

## Context
- Plans 25.1 and 25.2; docs/TECHNICAL_SUPPORT_PLAN.md sections 3, 4, 9
- Existing sub_admin web controller for the HTMX form / list pattern (`app/web/framework/htmx.py`)

## Tasks

<task type="auto">
  <name>Teams (Super Admin)</name>
  <files>teams_controller.py, pages/teams/*, dairy sidebar entry</files>
  <action>`/support/teams`: table (name, code, manager, members, status) with search; create / edit form with
  manager name, mobile, email, password (existing validators); enable / disable with confirm dialog. Add the single
  "Technical Support" entry for Super Admin in the dairy sidebar.
  AVOID: letting Admin / Sub Admin see the entry.</action>
  <verify>tests: Super Admin creates team through the form; others 403; duplicate code and mobile show field errors</verify>
  <done>A team with its manager can be created and the manager can log in to /support.</done>
</task>

<task type="auto">
  <name>Members and roles (Manager)</name>
  <files>members_controller.py, roles_controller.py, pages/members/*, pages/roles/*</files>
  <action>`/support/members`: table (name, role, status, last seen) + create / edit / disable. `/support/roles`:
  roles list; edit page with permissions grouped (Tickets, Chat and Call, Team) as a checklist with one-line help per
  permission; system templates can be copied, the manager's own permissions are not editable. All writes through the
  handlers of 25.1 (no logic in controllers).
  AVOID: showing menu entries the member lacks `support.member.manage` / `support.role.manage` for.</action>
  <verify>tests: manager of team A cannot open team B's member (404); member without permission gets 403; role edit
  changes what the guard allows; headless screenshots at 1440 and 390 px</verify>
  <done>Manager can build a team of technical, assigner and viewer members; the sidebar of each reflects their role.</done>
</task>

## Must-Haves
- [ ] End-to-end: Super Admin creates team, manager logs in, creates members, members log in and see only their menus

## Success Criteria
- [ ] Tests green; screenshots reviewed by the user
- [ ] Phase 25 verification written (`VERIFICATION.md`) and commit message proposed
