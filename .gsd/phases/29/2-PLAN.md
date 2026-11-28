---
phase: 29
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/modules/support/application/activity_query.py
  - app/modules/support/infrastructure/activity_repository.py
  - app/web/support/activity_controller.py
  - app/web/support/audit_controller.py
  - app/web/templates/support/pages/activity/*.html
  - app/web/templates/support/pages/audit/*.html
  - app/web/templates/support/pages/dashboard.html
  - tests/support/test_activity.py
must_haves:
  - My Activity shows what the member did and how much for today, week, month or a custom range
  - Cards depend on the member's role; trend chart is day-wise
  - Manager sees every member's page and a team comparison table; Super Admin sees all teams
  - A member sees only their own numbers
  - Audit screen with filters is available to Manager and Super Admin only
  - All numbers come from events, messages and call logs through aggregate queries (no new counter tables)
gap_closure: false
---

# Plan 29.2: My Activity dashboard, manager team view and audit screen

## Objective
Personal and team activity dashboards plus the audit log screen (REQ-79, REQ-80, D-10).

## Context
- docs/TECHNICAL_SUPPORT_PLAN.md section 9A; `.gsd` skill `dataviz` for the one small trend chart (use inline SVG,
  no CDN, NFR-18)

## Tasks

<task type="auto">
  <name>Activity queries and screens</name>
  <files>activity_query.py, activity_repository.py, activity_controller.py, pages/activity/*, dashboard.html</files>
  <action>One aggregate per metric over a date range: assigned to me, resolved, closed, replies, internal notes,
  assignments made, reassigns, calls by outcome, average first reply time (from events). Index additions only if the
  explain plan needs them. "My Activity" page: stat cards, my open tickets by status, recent timeline, day-wise
  trend (inline SVG). Manager: member picker, comparison table (sortable). The support Dashboard home shows the member's
  cards for today plus the team's open count.
  AVOID: storing counters; loading events into Python to count them.</action>
  <verify>tests with seeded events: each metric exact; member A cannot request member B (403); Manager of another
  team (404); query count and explain on 10,000 events</verify>
  <done>Numbers match the seeded data and respect scope.</done>
</task>

<task type="auto">
  <name>Audit screen</name>
  <files>audit_controller.py, pages/audit/*</files>
  <action>Table of audit rows with filters (member, action, ticket, date), keyset pagination, readable action text
  ("Rahul assigned TS-2026-000123 to Priya") and links to the ticket or member. Read-only, no delete.
  AVOID: editing or deleting audit rows through any screen or API.</action>
  <verify>tests for permission and filters; screenshot at 1440 and 390 px</verify>
  <done>Manager can answer who did what and when.</done>
</task>

## Must-Haves
- [ ] Viewer role's activity page is an honest empty state, not an error

## Success Criteria
- [ ] Tests green; Phase 29 verification written; commit message proposed
