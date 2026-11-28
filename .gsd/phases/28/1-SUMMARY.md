# Plan 28.1 Summary: Device tokens, outbox and FCM sender

**Status:** ✅ Complete (2026-11-22); the mobile app side comes later (DECISION-033)

## Shape (user, 2026-11-22: "notifications will be used by other modules too")
Push notifications are a **shared module**, `app/modules/notification/`, that knows no feature. Technical Support
is its first user through a small adapter. DECISION-034.

```
app/modules/notification/
├── domain/          DeviceToken, Notification (source, type, reference_id, data, skip_if_online), statuses
├── infrastructure/  notification_device_tokens, notification_outbox (migration 0007), repository
└── application/     NotificationService.notify / notify_many   ← what any module calls
                     DeviceHandler (register / remove)          ← /api/v1/notifications/devices
                     FcmSender / DisabledSender, PushWorker (add_presence for "online" checks)
```

## How another module sends a push
Inside the transaction of the change being reported:

```python
await notifications.notify(
    user_id=farmer_user_id, source="payments", type="PAYMENT_RECEIVED",
    title="Payment received", body="₹ 2,450 for 1-15 Nov", reference_id=str(payment.id),
)
```
`NotificationService` is in the container (`GetHandler.notification_service`, or inject it in the configurator).
The phone gets `source`, `type` and `reference_id` in the data to open the right screen. Use `skip_if_online=True`
only for chat-like messages the user already sees live (and register a presence check for that module).

## What was built
- Migration `0007`: `notification_device_tokens` (one row per FCM token, moves to the last user who registers it,
  many devices per user) and `notification_outbox` (source, type, reference_id, title, body, data, skip_if_online,
  status PENDING / SENDING / SENT / FAILED / SKIPPED, attempts, next attempt, last error). No foreign key to any
  feature table; both cascade when the user is deleted.
- API for every signed-in app user: `POST /api/v1/notifications/devices` (`fcm_token`, `platform` android | ios,
  `app_version`; idempotent) and `DELETE /api/v1/notifications/devices/{fcm_token}` (logout; own token only).
- `NotificationService.notify` / `notify_many`: checks `source` (short lowercase module name) and `type`, cuts the
  title to 120 and body to 180 characters, writes nothing while push is disabled.
- `FcmSender` (HTTP v1, no Google SDK: RS256 service-account JWT → OAuth access token, cached, renewed once on 401).
  Errors sorted into dead token / retry later / failed. Tokens and message text are never logged.
- `PushWorker`: asyncio task in the API process with a fresh context and short own transactions; guarded claim
  (two workers never send the same row), `skip_if_online` checked against registered presence checks (a failing
  check counts as offline), sends to every active device, switches dead tokens off, backoff 30 s doubling to
  30 min, 5 attempts, releases rows left SENDING by a crash, deletes finished rows after 30 days. Not started
  without a Firebase credential.
- Support adapter `support/application/push_messages.py` (source `support`): `TICKET_REPLY` (cut to 100,
  `skip_if_online`), `TICKET_STATUS` for staff moves including the move to ASSIGNED, `TICKET_RESOLVED` (always
  sent). Never for internal notes or the requester's own moves. The support sockets are registered as the
  presence check.
- Recycle Bin: purging a tree now deletes the tickets its users raised and clears their name on other tickets'
  messages, events and attachments (before, the users' foreign key would have stopped the purge); devices and
  notifications cascade with the user.

## Decided while building
- No Firebase credential = nothing is written and the worker does not start (rows nobody sends would only grow the
  table, and on SQLite a worker marking them competed with requests for the write lock — seen as "database is locked").
- Online skipping is per notification, not global: a payment push must not be dropped because the user has the
  support chat open.
- The realtime bus drops events queued inside a savepoint that rolled back while the outer transaction commits.

## Firebase setup (for later)
1. Firebase console → Project settings → Service accounts → "Generate new private key" (a JSON file).
2. Put it on the server outside the repository, readable only by the app user, e.g. `/etc/quickyee/firebase.json`
   (`chmod 600`).
3. `.env`: `FIREBASE_CREDENTIALS_FILE=/etc/quickyee/firebase.json` (or `FIREBASE_CREDENTIALS_JSON='{...}'` on one
   line). Optional `PUSH_POLL_SECONDS` (default 3).
4. Restart; the log no longer says push notifications are disabled.
5. The app sends its Firebase token **with the login** (user, 2026-11-22): `POST /api/v1/auth/login` takes optional
   `fcm_token`, `platform` (android | ios) and `app_version`; the response says `push_registered`. A missing or bad
   token never fails the login. When Firebase rotates the token while logged in, the app sends it to
   `POST /api/v1/notifications/devices`; on logout it calls `DELETE /api/v1/notifications/devices/{fcm_token}`.
   A tapped push is routed by `source` + `type` + `reference_id`.

## Tests
- `tests/notification/test_notifications.py` (feature-free): devices for every app role, token move, validation,
  the service (limits, checks, notify_many, disabled, rollback on PostgreSQL), the worker with a fake sender
  (sent, per-notification online skip, failing presence check, retry, give-up, dead tokens, no device, disabled,
  crash release, purge), the FCM sender against a fake Google.
- `tests/support/test_push.py`: what support queues (reply, file, statuses, resolved, none for notes / own moves,
  rollback on PostgreSQL).
- `tests/test_recycle_bin.py`: purge with tickets, devices and notifications.

## Found, not fixed (pre-existing)
On SQLite a released savepoint commits (no pysqlite BEGIN recipe on the engine), so an outer rollback cannot undo
work done in a nested `transaction()`. PostgreSQL is correct; the rollback tests run there only. STATE.md concerns.
