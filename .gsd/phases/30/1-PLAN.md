---
phase: 30
plan: 1
wave: 1
depends_on: []
files_modified:
  - docs/SUPPORT_API.md
  - docs/TECHNICAL_SUPPORT_PLAN.md
  - tests/support/test_permissions_matrix.py
  - .gsd/phases/30/VERIFICATION.md
  - .gsd/STATE.md
must_haves:
  - A permission matrix test covers every support endpoint and screen for every role
  - docs/SUPPORT_API.md lets app developers integrate without reading code (REST, WebSocket, push payloads, errors)
  - End-to-end run on PostgreSQL with Redis and the real worker passes (/verify skill)
  - Realtime load check for 200 sockets and a burst of 100 tickets shows no loss and acceptable latency
  - The user signs off the UI at desktop and phone widths
gap_closure: false
---

# Plan 30.1: Review, API document and end-to-end verification

## Objective
Prove the module is secure, documented and works as a whole (all REQ-58 to REQ-80).

## Context
- All earlier phase summaries; the `/verify` skill (launch the API and worker in isolation); local Postgres recipe
  from memory (pgserver); Redis through WSL2 or Docker for the run

## Tasks

<task type="auto">
  <name>Security and permission review</name>
  <files>tests/support/test_permissions_matrix.py</files>
  <action>Generate a matrix: roles (Super Admin, Admin, Sub Admin, MCC, VLCC, Farmer, VLCC_FARMER, Manager, each member
  template, a member of another team, anonymous) against every support route, API endpoint and socket message; expected
  allow / deny table lives in the test. Check: no support path is public, internal notes never reach requester paths
  or sockets, attachments are private, rate and size limits hold, audit rows exist for sensitive actions, no phone
  numbers or tokens in logs. Fix anything found in the owning phase's files.
  AVOID: relaxing a test to make it pass.</action>
  <verify>full matrix test green; `/code-review` and `/security-review` on the branch diff</verify>
  <done>No unexpected allow in the matrix; review findings fixed or recorded.</done>
</task>

<task type="auto">
  <name>API document and verification run</name>
  <files>docs/SUPPORT_API.md, VERIFICATION.md, STATE.md</files>
  <action>Write `docs/SUPPORT_API.md` for app developers in the style of `docs/MARKETPLACE_API.md`: auth, endpoints with
  request / response examples, status values and labels, WebSocket handshake and every event with payload,
  reconnect and replay, device-token and push payload contract, error codes, upload rules, idempotency. Run `/verify`
  on PostgreSQL + Redis: Super Admin creates a team, manager creates members, a requester raises a ticket by API,
  members receive it live, chat, call log, resolve, push through the fake sender, Redis stopped and started. Run the
  load check. Update `docs/TECHNICAL_SUPPORT_PLAN.md` decisions and `.gsd/STATE.md`; propose the milestone commit message.</action>
  <verify>all scenario steps pass; load check numbers recorded in VERIFICATION.md; full test suite on SQLite and the
  support suites on PostgreSQL pass</verify>
  <done>Documented, verified, and ready for the user's sign-off and commit.</done>
</task>

## Must-Haves
- [ ] Mobile developers can start from SUPPORT_API.md alone

## Success Criteria
- [ ] All requirements REQ-58 to REQ-80 marked Complete with evidence
