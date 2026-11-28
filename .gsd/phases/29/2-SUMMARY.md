# Plan 29.2 Summary: My Activity dashboard, manager team view and audit screen

**Status:** ✅ Complete (2026-11-22), visual sign-off by the user pending

## What was built
- `ActivityRepository`: every number is an aggregate query over ticket events, messages, call logs and tickets —
  no counter tables, nothing counted in Python. One grouped query per metric for any number of members (the test
  checks the statement count is the same for one member and five). Metrics: assigned to me, replies, internal
  notes, assignments made, reassigned, resolved, closed, calls by outcome, average time to first reply; day-wise
  actions; open tickets by status; recent actions. Date maths per dialect (SQLite `julianday`, PostgreSQL `epoch`).
- `ActivityQuery`: periods Today / Last 7 days / Last 30 days / Custom (max one year). Scope: a member sees only
  their own page (asking for another → 403, redirected to their own); Manager or `support.report.view` sees the
  team's members (another team's member → 404); Super Admin sees every team. Cards follow the member's role; a
  Viewer gets an honest empty state.
- Screens: `/support/activity` (stat cards, actions-per-day bar chart as inline SVG with hover titles and a
  screen-reader table, open now, calls by outcome, recent actions; member picker for managers),
  `/support/activity/team` (sortable comparison table with totals; Super Admin picks the team),
  `/support/audit` (Manager: own team, Super Admin: every team; filters member / action / ticket / dates; rows read
  as sentences, e.g. "Priya Shah assigned TS-2026-000004 to Ravi Menon"; read-only — no screen or API edits or
  deletes audit rows).
- Sidebar group "Insights": My activity (members), Team activity (`report.view`), Audit log (Manager / Super Admin).
- Support home: the member's open tickets and today's cards; Super Admin sees open tickets, the pool and teams
  (the Phase 25 "tickets arrive in the next phase" placeholder is gone).

## Decided while building
- The audit list uses offset pages like the other screens (it shows a total), not keyset.
- "Assigned to me" counts assignment events in the period, so a ticket handed over twice counts twice.
- Average first reply is over the tickets whose first staff reply this member wrote in the period.

## Tests
`tests/support/test_activity.py` — 13 tests: every metric against seeded work, trend and periods, cards per role,
scope (own / team / other team / Super Admin), constant query count, the three screens, sidebar per role, home page,
audit sentences, filters and team scope.
