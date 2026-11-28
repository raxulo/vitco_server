---
phase: 29
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/support/domain/entities.py
  - app/modules/support/infrastructure/models.py
  - app/modules/support/infrastructure/call_repository.py
  - app/modules/support/application/call_handler.py
  - app/web/support/calls_controller.py
  - app/web/templates/support/pages/tickets/_call_card.html
  - app/core/database/migrations/versions/20261121_0008_support_calls.py
  - tests/support/test_calls.py
must_haves:
  - Phone number is visible to every member; the Call button (tel:) needs support.call.make
  - Pressing Call records an intent, afterwards the member records outcome and note
  - Outcomes - connected, not reachable, busy, callback requested; optional duration and note
  - Call events appear in the ticket timeline and the audit log
gap_closure: false
---

# Plan 29.1: Call log and call UI

## Objective
Click-to-call with a proper record (REQ-78, D-5, D-6).

## Context
- docs/TECHNICAL_SUPPORT_PLAN.md sections 4 and 8; Phase 26 ticket detail

## Tasks

<task type="auto">
  <name>Call log backend</name>
  <files>models.py, call_repository.py, call_handler.py, migration 0008</files>
  <action>Table `support_call_logs` (ticket_id, member_id, requester_user_id, started_at, outcome nullable, duration_s
  nullable, note). `start_call` (needs `support.call.make`, returns the number to dial and creates the row plus an
  event and audit entry), `finish_call` (outcome, duration, note; only the same member). One open call per member.
  AVOID: logging the phone number in plain application logs.</action>
  <verify>tests: permission, ownership, outcome validation, event and audit rows</verify>
  <done>Every call has a record with outcome.</done>
</task>

<task type="auto">
  <name>Call UI</name>
  <files>calls_controller.py, _call_card.html</files>
  <action>In the requester card: phone number with copy, Call button as a `tel:` link only for members with the
  permission. After the user returns to the page (visibility change) a small inline prompt asks for the outcome and an
  optional note; it can be dismissed and finished later from the ticket timeline. Call history list on the ticket.
  AVOID: modal that blocks the page; auto-submitting an outcome.</action>
  <verify>tests for visibility per role; screenshots; manual click on a phone or emulator</verify>
  <done>A member can call, record the outcome and see the history on the ticket.</done>
</task>

## Must-Haves
- [ ] Viewer and chat-only roles see the number but no Call button

## Success Criteria
- [ ] Tests green
