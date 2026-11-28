---
phase: 26
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/support/domain/entities.py
  - app/modules/support/domain/enums.py
  - app/modules/support/domain/ticket_rules.py
  - app/modules/support/domain/irepository.py
  - app/modules/support/infrastructure/models.py
  - app/modules/support/infrastructure/ticket_repository.py
  - app/modules/support/application/ticket_command.py
  - app/modules/support/application/ticket_handler.py
  - app/modules/support/application/routing.py
  - app/core/database/migrations/versions/20261119_0006_support_tickets.py
  - app/modules/configurator.py
  - app/modules/dependencies.py
  - tests/support/test_tickets.py
must_haves:
  - Ticket, message, event, attachment and category tables on PostgreSQL and SQLite (migration 0006)
  - Status flow is enforced in the domain; every change writes a timeline event
  - Routing by category default team, else unassigned pool; manual assign by Manager / Ticket Assigner
  - Internal notes are flagged and never returned to requester queries
  - Ticket number TS-YYYY-NNNNNN is unique and gap-tolerant
gap_closure: false
---

# Plan 26.1: Ticket domain, tables and handlers

## Objective
The ticket engine, without any screen or API yet (REQ-66, REQ-68, REQ-69, REQ-70, REQ-71).

## Context
- docs/TECHNICAL_SUPPORT_PLAN.md sections 4, 5, 7
- Phase 25 `SupportContext` / `require(perm)`; `app/modules/media` for attachment storage and validation

## Tasks

<task type="auto">
  <name>Domain and tables</name>
  <files>domain/*, infrastructure/models.py, migration 0006</files>
  <action>Enums `TicketStatus`, `TicketPriority`, `MessageKind` (TEXT, ATTACHMENT, SYSTEM), `EventType`. Entities
  `Category`, `Ticket`, `TicketMessage` (`is_internal`), `TicketEvent`, `TicketAttachment`. `ticket_rules.py`: allowed
  transitions (NEW to ASSIGNED, ASSIGNED to IN_PROGRESS, IN_PROGRESS to WAITING_ON_USER or RESOLVED, RESOLVED to CLOSED
  or REOPENED, any open state to ESCALATED, requester reply on WAITING_ON_USER back to IN_PROGRESS), which permission
  each transition needs and who may trigger it. Tables: `support_categories`, `support_tickets` (ticket_no unique,
  requester_user_id, category_id, team_id nullable, assigned_to nullable, priority, status, subject, description,
  device_model, os_version, app_version, client_request_id unique per requester, first/last message at, resolved_at,
  closed_at, and nullable `sla_due_at` kept for Version 2), `support_ticket_messages`, `support_ticket_events`,
  `support_attachments`. Indexes: (team_id, status), (assigned_to, status), (requester_user_id), (ticket_id, id).
  AVOID: storing status as free text; unbounded message queries (always keyset by id).</action>
  <verify>unit tests for every legal and illegal transition; migration up / down on both databases</verify>
  <done>Rules and tables ready; illegal transitions raise a domain error.</done>
</task>

<task type="auto">
  <name>Handlers and routing</name>
  <files>application/ticket_*.py, routing.py, repository, configurator, dependencies</files>
  <action>`TicketHandler` (`__slots__`, transactions): `create` (requester; idempotent on `client_request_id`;
  assigns `ticket_no` from a yearly counter row; routes through `routing.py`), `list_for_requester`,
  `list_for_staff(scope=unassigned|all|mine, filters, keyset)`, `get` (visibility rules: requester only own and no
  internal notes; staff by team and `view_all` / `view_assigned`), `post_message`, `add_internal_note`, `assign` (needs
  `support.ticket.assign`; target must be an active member of the same team), `change_status`, `change_priority`,
  `reopen`. Every change appends an event and an audit row. `routing.py`: category default team, else
  unassigned (team_id null, visible to Super Admin only). `CategoryHandler`: Super Admin CRUD.
  Super Admin may route an unassigned ticket to a team.
  AVOID: trusting `team_id` / `assigned_to` from the client; sending internal notes through shared message queries.</action>
  <verify>tests/support/test_tickets.py: create twice with same client_request_id returns one ticket; routing both
  ways; assign across teams rejected; requester never sees internal notes or others' tickets; viewer cannot reply</verify>
  <done>All ticket operations work through handlers with events and audit rows.</done>
</task>

## Must-Haves
- [ ] Permission and team scope are checked in handlers (REQ-63)
- [ ] Phone, device and app version are available to every member on ticket read (REQ-62), dairy data never

## Success Criteria
- [ ] Tests green on SQLite and PostgreSQL
