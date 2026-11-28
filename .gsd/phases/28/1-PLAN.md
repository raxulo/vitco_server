---
phase: 28
plan: 1
wave: 1
depends_on: []
files_modified:
  - requirements.txt
  - app/config/settings.py
  - app/modules/support/domain/entities.py
  - app/modules/support/infrastructure/models.py
  - app/modules/support/infrastructure/notification_repository.py
  - app/modules/support/application/notification_handler.py
  - app/modules/support/application/push_sender.py
  - app/modules/support/application/push_worker.py
  - app/api/v1/routers/support.py
  - app/api/v1/schemas/support.py
  - app/bootstrap/lifespan.py
  - app/core/database/migrations/versions/20261120_0007_support_push.py
  - tests/support/test_push.py
must_haves:
  - POST and DELETE /api/v1/support/devices register and remove FCM tokens; many devices per user
  - Notifications are written to an outbox in the same transaction as the ticket change
  - A background sender delivers through FCM with retry and removes invalid tokens
  - Users who are online (Redis presence) are skipped
  - Without Firebase credentials the sender is disabled, logs only, and nothing else breaks
  - Credentials come from environment or a file path, never from the repository
gap_closure: false
---

# Plan 28.1: Device tokens, outbox and FCM sender

## Objective
Everything on the backend for push; the mobile app joins later (REQ-76, REQ-77, DECISION-033).

## Context
- docs/TECHNICAL_SUPPORT_PLAN.md section 6A; Phase 27 presence and event bus
- app/bootstrap/lifespan.py for how the Excel worker is started (CON-01: own context and transactions)

## Tasks

<task type="auto">
  <name>Tokens, outbox and handlers</name>
  <files>models.py, notification_repository.py, notification_handler.py, routers/support.py, migration 0007</files>
  <action>Tables `support_device_tokens` (user_id, fcm_token unique, platform, app_version, last_seen, is_active) and
  `support_notification_outbox` (user_id, ticket_id, type, title, body, data JSON, status PENDING / SENT / FAILED /
  SKIPPED, attempts, next_attempt_at, sent_at). API: `POST /devices` upserts by token (moves it to the current user),
  `DELETE /devices/{token}` on logout. `NotificationHandler.enqueue(...)` is called from the ticket handlers for:
  staff reply, status change, assignment to the requester's ticket, ticket resolved. Titles and bodies are short
  English strings; message text is cut to 100 characters and never includes internal notes.
  AVOID: sending anything inside the request transaction; leaking other users' ticket text.</action>
  <verify>tests: token upsert and removal; outbox row created with the ticket change and rolled back with it; internal
  note never creates a requester notification</verify>
  <done>Outbox rows appear exactly for the events listed above.</done>
</task>

<task type="auto">
  <name>Sender and worker</name>
  <files>push_sender.py, push_worker.py, lifespan.py, settings.py</files>
  <action>`FcmSender` using the Firebase HTTP v1 API with a service-account credential read from
  `FIREBASE_CREDENTIALS_FILE` (or JSON in an environment variable); an interface plus a `DisabledSender` that logs.
  `push_worker`: an asyncio task started in lifespan (own transactions), polls PENDING rows in small batches, skips
  users who are online, sends to every active token, marks SENT, retries with backoff (max 5), deactivates tokens FCM
  reports as unregistered, marks SKIPPED / FAILED with the reason. Stops cleanly on shutdown.
  AVOID: a second process for this (volume is small; CON-08); logging tokens or message bodies.</action>
  <verify>tests with a fake FCM: success, transient failure then success, unregistered token removed, online user
  skipped, disabled mode only logs</verify>
  <done>Push works end to end against a fake FCM; with no credentials the app starts and stays quiet.</done>
</task>

## Must-Haves
- [ ] A short setup note for the Firebase credential is added to the Phase 28 summary

## Success Criteria
- [ ] Tests green; Phase 28 verification written; commit message proposed
