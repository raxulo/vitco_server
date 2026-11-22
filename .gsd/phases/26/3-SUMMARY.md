# Plan 26.3 Summary: Portal queues, ticket detail and categories

**Status:** ✅ Complete (2026-11-22), visual sign-off by the user pending

## What was built
- Sidebar group "Tickets": Unassigned queue, All tickets, My tickets, each shown only with its permission
  (`view_all`, `assign`, `view_assigned`), with open-ticket badges from one query. Super Admin also gets
  Categories. The default queue is the first one the member may use.
- `/support/tickets?scope=` one list for the three queues: search (ticket number, subject, requester name or phone),
  status, priority, category, assignee and date filters, pager, unread dot, empty states per queue.
- `/support/tickets/{id}`: problem, conversation (requester / staff / internal-note / system bubbles, image
  thumbnails and file links), composer with Reply / Internal note toggle and attachment (HTMX, only the conversation
  is swapped), requester card (profile, parent, phone with copy, email, device, OS, app version; no dairy data),
  ticket meta with assign, priority, category, "Move to" (confirm dialogs for resolve / close / reopen) and, for
  Super Admin, "Send to a team"; timeline.
- Actions are plain form posts that redirect back with a short notice code; every one is checked by the handler.
- `/support/attachments/{id}` serves a file with `no-store` and `nosniff`; another team's staff get 404.
- `/support/categories` (Super Admin): list, create, edit (default team and priority), enable / disable.

## Decided while building
- "All tickets" needs `view_all`; a member with only `view_assigned` uses "My tickets".
- Calling and "My Activity" stay in Phase 29; no Call button yet.
- A Manager does not manage categories yet (REQ-66 mentions it): Super Admin only for now.
- Viewing the phone number is not audited yet (Phase 29 adds the audit screens and number-view rows).

## Tests
`tests/support/test_ticket_screens.py` — 24 tests: sidebar per role, badges, queue permissions, filters and empty
states, no per-row queries (≤ 5 statements for 50 rows), detail content and controls per role, every action and its
refusals, HTMX reply / note / file / errors, closed ticket, categories CRUD, isolation of other roles.
