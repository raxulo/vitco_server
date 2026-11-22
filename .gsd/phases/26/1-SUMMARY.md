# Plan 26.1 Summary: Ticket domain, tables and handlers

**Status:** ✅ Complete (2026-11-22)

## What was built
- Domain: `TicketStatus`, `TicketPriority`, `MessageKind`, `EventType`, `Scope`; entities `Category`, `Ticket`,
  `TicketMessage`, `TicketEvent`, `TicketAttachment`; `ticket_rules.py` with the legal staff moves, the narrower
  requester moves, the permission each target status needs and the requester-facing status labels.
- Migration `0006` (`20261119_0006_support_tickets.py`): `support_categories`, `support_ticket_counters`,
  `support_tickets`, `support_ticket_messages`, `support_ticket_events`, `support_attachments`. Status, priority, kind
  and event type are plain string columns (no native enum), so a new value never needs a PostgreSQL migration.
  `sla_due_at` and `sla_minutes` are kept nullable for Version 2.
- `TicketRepository` (lists load requester, assignee, category and team in one query) and `TicketHandler`:
  create (idempotent on `client_request_id`), requester and staff lists / reads, messages, internal notes, assign,
  route to team, status, priority, category, requester close / reopen, unread marks. Every change appends a timeline
  event; staff actions also write an audit row in the same transaction.
- `routing.py`: category default team, else the unassigned pool (also when that team is switched off).
- Ticket numbers `TS-YYYY-NNNNNN` from a per-year counter row (atomic `UPDATE ... RETURNING`).

## Decided while building
- Messages and events use an integer id (BIGINT, INTEGER on SQLite), not a UUID, so "everything after id N" works for
  mobile paging and for the Phase 27 catch-up.
- Staff ticket lists use limit / offset (the standard list envelope needs a total); only messages page by id.
- A member who only holds `view_assigned` may open the "All" scope but sees only their own tickets; the portal does
  not offer it to them.
- A requester reply on a WAITING_ON_USER ticket resumes it; on a RESOLVED ticket it reopens it.
- Internal notes stay allowed on a closed ticket; replies do not.
- A concurrent duplicate `client_request_id` is stopped by the unique constraint, not by a retry loop.

## Tests
`tests/support/test_tickets.py` — 58 tests: every legal and illegal move, creation and idempotency, both routing
paths, assignment and team scope, per-permission visibility, internal notes, unread counters, status flow, audit and
timeline rows.
