# Technical Support API (v1)

The API the mobile app uses to raise support tickets, follow them, chat with the support team, send photos
or PDFs, get live updates over a WebSocket and receive push notifications.

Support staff do not use this API. They work in the web portal at `/support`.

Every example below is a real response from the API (test data, shortened where a list is long).

---

## Contents

1. [Basics](#1-basics)
2. [Response format](#2-response-format)
3. [Errors](#3-errors)
4. [Categories](#4-categories)
5. [Tickets](#5-tickets)
6. [Messages](#6-messages)
7. [Attachments](#7-attachments)
8. [Live updates (WebSocket)](#8-live-updates-websocket)
9. [Push notifications](#9-push-notifications)
10. [Values and enums](#10-values-and-enums)
11. [App flow checklist](#11-app-flow-checklist)
12. [Endpoint summary](#12-endpoint-summary)

---

## 1. Basics

| Item | Value |
|------|-------|
| Base path | `/api/v1/support` |
| Format | JSON in, JSON out (`Content-Type: application/json`). File uploads use `multipart/form-data`. |
| Login | **Required.** Send `Authorization: Bearer <access_token>` from `POST /api/v1/auth/login`. |
| Who can use it | MCC, VLCC, Farmer and VLCC Farmer logins. Any other login gets `403`. |
| Dates | ISO 8601 without a timezone, in Indian time (IST), e.g. `"2026-11-28T14:31:04.117467"` |
| Ticket IDs | UUIDs (`id`). Show people the readable `ticket_no` (e.g. `TS-2026-000001`). |
| Message IDs | Whole numbers that only go up. Use them to fetch newer messages (`after_id`). |

**Only your own tickets.** Every call works only on tickets the signed-in user raised. Another user's ticket
answers `404`, the same as a ticket that does not exist.

**What the app never sees.** Internal notes written by support staff, internal files, which staff member works
on the ticket, staff phone numbers, and the staff-only timeline rows (assignment, priority, routing, calls) are
removed on the server. Replies from staff carry the name `"Support team"`.

**Safe retries.** `POST /tickets` and `POST /tickets/{id}/messages` accept an optional `client_request_id`.
Make one unique text (for example a UUID) per ticket or message, and send the same value again if a request
times out. The server then returns the first result instead of creating a second one.

**Not in this API:** rate limits (planned for a later version), voice notes, ratings, FAQ.

---

## 2. Response format

One record:

```json
{
  "status": true,
  "code": 200,
  "message": "Ticket fetched successfully",
  "data": { "...": "..." }
}
```

A list:

```json
{
  "status": true,
  "code": 200,
  "message": "Tickets fetched successfully",
  "items": [ { "...": "..." } ],
  "limit": 20,
  "offset": 0,
  "total": 1,
  "pages": 1,
  "next_page": null,
  "has_more": false
}
```

`code` is the same as the HTTP status. `201` means something new was created.

---

## 3. Errors

Errors use a different shape:

```json
{
  "success": false,
  "error": {
    "code": "SUPPORT_TICKET_NOT_FOUND",
    "message": "Ticket not found.",
    "details": {}
  }
}
```

`message` is written for people and can be shown in the app. Use `code` in your logic.

| HTTP | `error.code` | When |
|------|--------------|------|
| 401 | `AUTH_UNAUTHORIZED` | No token, or the token is wrong or expired. Log in again. |
| 403 | `SUPPORT_ACCESS_DENIED` | The login is not an MCC, VLCC, Farmer or VLCC Farmer. |
| 403 | `SUPPORT_ACCESS_ONLY` | A support staff login called an API outside Technical Support. |
| 404 | `SUPPORT_TICKET_NOT_FOUND` | The ticket or file does not exist, or belongs to someone else. |
| 404 | `SUPPORT_CATEGORY_NOT_FOUND` | The `category_id` is unknown or switched off. |
| 404 | `SUPPORT_MESSAGE_NOT_FOUND` | Deleting a message that is not in this ticket. |
| 409 | `SUPPORT_MESSAGE_NOT_DELETABLE` | Deleting someone else's message, or the ticket's first message. |
| 409 | `SUPPORT_TICKET_CLOSED` | Sending to a closed ticket. Reopen it first. |
| 409 | `SUPPORT_INVALID_TRANSITION` | Closing or reopening a ticket whose status does not allow it. |
| 422 | `SUPPORT_VALIDATION_ERROR` | A rule on the content failed (file type, size, empty text). |
| 422 | (no `error`, see below) | The request body does not match the fields in this document. |

Examples:

```json
{ "success": false, "error": { "code": "SUPPORT_TICKET_CLOSED",
  "message": "This ticket is closed. Reopen it to continue.", "details": {} } }
```

```json
{ "success": false, "error": { "code": "SUPPORT_INVALID_TRANSITION",
  "message": "A ticket that is in progress cannot be reopened.", "details": {} } }
```

A body that does not match the fields gets the standard FastAPI answer, with one entry per field:

```json
{
  "detail": [
    { "type": "string_too_short", "loc": ["body", "subject"],
      "msg": "String should have at least 3 characters", "input": "x", "ctx": { "min_length": 3 } },
    { "type": "missing", "loc": ["body", "description"], "msg": "Field required", "input": { "subject": "x" } }
  ]
}
```

---

## 4. Categories

### `GET /categories`

The categories a user picks from when raising a ticket. Only active ones are listed, sorted by name.

```json
{
  "status": true,
  "code": 200,
  "message": "Categories fetched successfully",
  "items": [
    { "id": "3e463e18-75b0-47ce-8a50-2faa75a598ef", "name": "Rate chart" },
    { "id": "b8da7855-0c91-493e-ab2e-02b90c180bf4", "name": "Sync problem" }
  ],
  "limit": 2, "offset": 0, "total": 2, "pages": 1, "next_page": null, "has_more": false
}
```

The category decides which support team gets the ticket. The app does not choose a team.

---

## 5. Tickets

### `POST /tickets` — raise a ticket

```json
{
  "subject": "Sync is not working",
  "description": "The app shows 'sync failed' since morning.",
  "category_id": "b8da7855-0c91-493e-ab2e-02b90c180bf4",
  "device_model": "Redmi 9",
  "os_version": "Android 13",
  "app_version": "2.4.1",
  "client_request_id": "a3f1c9e2-1b7d-4c55-8a9e-0d2f6b7c1e44"
}
```

| Field | Rule |
|-------|------|
| `subject` | Required, 3 to 200 characters |
| `description` | Required, 5 to 4000 characters. It also becomes the first message. |
| `category_id` | Required, from `GET /categories` |
| `device_model`, `os_version`, `app_version` | Optional, up to 300 characters each. Please always send them: support uses them to help faster. |
| `client_request_id` | Optional, up to 64 characters (see [Basics](#1-basics)) |

Answer: `201` with the full ticket (the same shape as `GET /tickets/{id}`):

```json
{
  "status": true,
  "code": 201,
  "message": "Ticket raised successfully",
  "data": {
    "id": "381ef83b-b5d1-46f6-911d-8e1a71e994fe",
    "ticket_no": "TS-2026-000001",
    "subject": "Sync is not working",
    "status": "NEW",
    "status_label": "Received",
    "is_open": true,
    "priority": "MEDIUM",
    "category_id": "b8da7855-0c91-493e-ab2e-02b90c180bf4",
    "category_name": "Sync problem",
    "unread": 0,
    "created_at": "2026-11-28T14:31:04.117467",
    "updated_at": "2026-11-28T14:31:04.117473",
    "last_message_at": "2026-11-28T14:31:04.111109",
    "description": "The app shows 'sync failed' since morning.",
    "device_model": "Redmi 9",
    "os_version": "Android 13",
    "app_version": "2.4.1",
    "resolved_at": null,
    "closed_at": null,
    "messages": [
      { "id": 1, "kind": "TEXT", "body": "The app shows 'sync failed' since morning.", "from_you": true,
        "sender_label": "You", "created_at": "2026-11-28T14:31:04.118439", "attachments": [] }
    ],
    "timeline": [
      { "id": 1, "type": "CREATED", "from_status": null, "to_status": "Received",
        "created_at": "2026-11-28T14:31:04.121383" }
    ],
    "can_reply": true,
    "can_reopen": false,
    "can_close": true
  }
}
```

The same `client_request_id` again returns the same ticket with `200` and the message `"Ticket already raised"`.

### `GET /tickets` — my tickets

| Query | Default | Rule |
|-------|---------|------|
| `status` | all | One status from [Values](#10-values-and-enums) |
| `limit` | 20 | 1 to 100 |
| `offset` | 0 | 0 or more |

The ticket with the latest message comes first. Each item is a ticket card:

```json
{
  "status": true,
  "code": 200,
  "message": "Tickets fetched successfully",
  "items": [
    {
      "id": "381ef83b-b5d1-46f6-911d-8e1a71e994fe",
      "ticket_no": "TS-2026-000001",
      "subject": "Sync is not working",
      "status": "IN_PROGRESS",
      "status_label": "In progress",
      "is_open": true,
      "priority": "MEDIUM",
      "category_id": "b8da7855-0c91-493e-ab2e-02b90c180bf4",
      "category_name": "Sync problem",
      "unread": 1,
      "created_at": "2026-11-28T14:31:04.117467",
      "updated_at": "2026-11-28T14:31:04.230309",
      "last_message_at": "2026-11-28T14:31:04.226477"
    }
  ],
  "limit": 20, "offset": 0, "total": 1, "pages": 1, "next_page": null, "has_more": false
}
```

`unread` counts support replies the user has not opened yet. Show it as a badge.

### `GET /tickets/{ticket_id}` — one ticket

The card fields plus the conversation and the timeline:

```json
{
  "status": true,
  "code": 200,
  "message": "Ticket fetched successfully",
  "data": {
    "id": "381ef83b-b5d1-46f6-911d-8e1a71e994fe",
    "ticket_no": "TS-2026-000001",
    "status": "IN_PROGRESS",
    "status_label": "In progress",
    "...": "the card fields, then description, device_model, os_version, app_version, resolved_at, closed_at",
    "messages": [
      { "id": 2, "kind": "TEXT", "body": "It still fails after logging in again.", "from_you": true,
        "sender_label": "You", "created_at": "2026-11-28T14:31:04.169326", "attachments": [] },
      { "id": 4, "kind": "TEXT", "body": "Please open Settings > Sync and tap 'Sync now'. Does it show an error?",
        "from_you": false, "sender_label": "Support team", "created_at": "2026-11-28T14:31:04.226477",
        "attachments": [] }
    ],
    "timeline": [
      { "id": 1, "type": "CREATED", "from_status": null, "to_status": "Received", "created_at": "..." },
      { "id": 3, "type": "REQUESTER_REPLIED", "from_status": null, "to_status": null, "created_at": "..." },
      { "id": 6, "type": "STATUS_CHANGED", "from_status": "Received", "to_status": "In review", "created_at": "..." },
      { "id": 7, "type": "STATUS_CHANGED", "from_status": "In review", "to_status": "In progress", "created_at": "..." },
      { "id": 8, "type": "REPLIED", "from_status": null, "to_status": null, "created_at": "..." }
    ],
    "can_reply": true,
    "can_reopen": false,
    "can_close": true
  }
}
```

- `messages` holds up to 200 messages, oldest first. For longer chats use `GET /tickets/{id}/messages`.
- `from_status` and `to_status` in the timeline are already the app's words (`status_label`), ready to show.
- Use `can_reply`, `can_reopen` and `can_close` to show or hide the buttons. Do not work them out yourself.
- Opening a ticket does not clear `unread`. Call `POST /tickets/{id}/read` when the user has seen the chat.

### `POST /tickets/{ticket_id}/read`

Marks the support replies as seen. No body.

```json
{ "status": true, "code": 200, "message": "Ticket marked as read",
  "data": { "ticket_id": "381ef83b-b5d1-46f6-911d-8e1a71e994fe", "unread": 0 } }
```

### `POST /tickets/{ticket_id}/close`

The user no longer needs help. Allowed while the ticket is open or resolved. Answers the ticket card:

```json
{ "status": true, "code": 200, "message": "Ticket closed",
  "data": { "id": "381ef83b-b5d1-46f6-911d-8e1a71e994fe", "ticket_no": "TS-2026-000001",
            "status": "CLOSED", "status_label": "Closed", "is_open": false, "...": "..." } }
```

### `POST /tickets/{ticket_id}/reopen`

The problem came back. Allowed when the ticket is resolved or closed. Answers the ticket card with
`"status": "REOPENED"`. On an open ticket it answers `409 SUPPORT_INVALID_TRANSITION`.

---

## 6. Messages

### `POST /tickets/{ticket_id}/messages`

```json
{ "body": "It still fails after logging in again.", "client_request_id": "m-17" }
```

`body` is 1 to 4000 characters. Answer `201`:

```json
{
  "status": true,
  "code": 201,
  "message": "Message sent successfully",
  "data": { "id": 2, "kind": "TEXT", "body": "It still fails after logging in again.", "from_you": true,
            "sender_label": "You", "created_at": "2026-11-28T14:31:04.169326", "attachments": [] }
}
```

A reply moves the ticket on by itself: `WAITING_ON_USER` goes back to `IN_PROGRESS`, and a `RESOLVED` ticket
is reopened. A closed ticket answers `409 SUPPORT_TICKET_CLOSED`.

### `GET /tickets/{ticket_id}/messages`

Newer messages only, oldest first. Use it to fill the chat without loading the whole ticket.

| Query | Default | Rule |
|-------|---------|------|
| `after_id` | none (from the start) | The last message `id` the app already has |
| `limit` | 50 | 1 to 200 |

```json
{
  "status": true,
  "code": 200,
  "message": "Messages fetched successfully",
  "items": [
    { "id": 3, "kind": "ATTACHMENT", "body": "screen.png", "from_you": true, "sender_label": "You",
      "created_at": "2026-11-28T14:31:04.192375",
      "attachments": [ { "id": "5bc72b23-d33a-4298-b34b-52138f1212db", "file_name": "screen.png",
                         "mime_type": "image/png", "size_bytes": 72,
                         "url": "/api/v1/support/attachments/5bc72b23-d33a-4298-b34b-52138f1212db" } ] },
    { "id": 4, "kind": "TEXT", "body": "Please open Settings > Sync and tap 'Sync now'. Does it show an error?",
      "from_you": false, "sender_label": "Support team", "created_at": "2026-11-28T14:31:04.226477",
      "attachments": [] }
  ],
  "limit": 50, "offset": 0, "total": 2, "pages": 1, "next_page": null,
  "has_more": false,
  "next_after_id": 4
}
```

Ask again with `after_id = next_after_id` while `has_more` is `true`. Here `total` is the number of items in
this answer, not in the whole chat.

Every message also carries `is_deleted` (`false` normally) and `deleted_at` (`null` normally). A deleted
message keeps its place and `id`, with `body: ""` and `attachments: []`: show "This message was deleted".

### `DELETE /tickets/{ticket_id}/messages/{message_id}`

Deletes one of the user's own messages (text, file or voice message). No body. Answer `200`:

```json
{
  "status": true,
  "code": 200,
  "message": "Message deleted",
  "data": { "id": 5, "kind": "TEXT", "body": "", "from_you": true, "sender_label": "You",
            "created_at": "2026-11-28T14:32:10.512004", "is_deleted": true,
            "deleted_at": "2026-11-28T14:33:02.118730", "attachments": [] }
}
```

| Rule | Answer |
|------|--------|
| Only the user's own messages | `409 SUPPORT_MESSAGE_NOT_DELETABLE` |
| The ticket's first message is its description and stays | `409 SUPPORT_MESSAGE_NOT_DELETABLE` |
| Not on a closed ticket | `409 SUPPORT_TICKET_CLOSED` |
| A message id that is not in this ticket | `404 SUPPORT_MESSAGE_NOT_FOUND` |
| Already deleted | `200`, the same answer again (safe to retry) |

The text and the files are removed from the server; support sees "This message was deleted" too. Support can
delete their own replies the same way: the app hears `message.deleted` (section 8).

---

## 7. Attachments

### `POST /tickets/{ticket_id}/attachments`

`multipart/form-data` with one file in the field `file`.

| Rule | Value |
|------|-------|
| Types | JPEG, PNG, WebP images, PDF, and audio for voice messages |
| Audio | M4A / AAC (`audio/mp4`, `audio/aac`), MP3 (`audio/mpeg`), Ogg / Opus (`audio/ogg`), WebM (`audio/webm`), WAV (`audio/wav`), 3GP (`audio/3gpp`) |
| Size | Up to 10 MB (about 10 minutes of AAC voice at 128 kbps; record at 32 to 64 kbps mono for far less) |
| Check | The file content must match its type (a renamed `.exe` is refused) |

Set the file's content type in the multipart part. If the HTTP client can only send
`application/octet-stream`, the server works the type out from the content.

A photo or PDF becomes a message of kind `ATTACHMENT`; an audio file becomes a message of kind `AUDIO` (a
voice message). For both, `body` is the file name and `attachments` holds the one file. Play an `AUDIO`
message from its attachment `url` with the same `Authorization` header; the download answers HTTP range
requests, so players can seek. **Recommended for voice messages:** record AAC in an `.m4a` file
(Android `MediaRecorder` with `MPEG_4` + `AAC`, iOS `AVAudioRecorder` with `kAudioFormatMPEG4AAC`), mono,
32 to 64 kbps; it plays on both phones and in the support portal. Answer `201`:

```json
{
  "status": true,
  "code": 201,
  "message": "File attached successfully",
  "data": {
    "message": { "id": 3, "kind": "ATTACHMENT", "body": "screen.png", "from_you": true, "sender_label": "You",
                 "created_at": "2026-11-28T14:31:04.192375", "attachments": [ { "...": "the attachment below" } ] },
    "attachment": { "id": "5bc72b23-d33a-4298-b34b-52138f1212db", "file_name": "screen.png",
                    "mime_type": "image/png", "size_bytes": 72,
                    "url": "/api/v1/support/attachments/5bc72b23-d33a-4298-b34b-52138f1212db" }
  }
}
```

Refusals answer `422 SUPPORT_VALIDATION_ERROR` with one of these messages:
`"Only JPEG, PNG, WebP images, PDF files and audio recordings can be attached."`, `"The file is empty."`,
`"The file is larger than 10 MB."`, `"The file does not match its type."`.

### `GET /attachments/{attachment_id}`

Downloads the file. Send the same `Authorization` header (the file is private). The answer is the file itself
with its `Content-Type`, and `Cache-Control: private, no-store`: do not keep it in a shared cache.
Put the server address in front of `url`: `https://<host>/api/v1/support/attachments/<id>`.

---

## 8. Live updates (WebSocket)

While a support screen is open, the app can hear about new replies and status changes at once instead of
polling.

### Connect and sign in

1. Open `wss://<host>/ws/support/app`.
2. Within **10 seconds**, send:

   ```json
   { "type": "auth", "token": "<access_token>", "last_event_id": 0 }
   ```

   `last_event_id` is the last event `id` the app received before (0 the first time).
3. The server answers:

   ```json
   { "type": "hello", "latest_id": 1795856462022, "resync": false }
   ```

   Then it sends every event the app missed since `last_event_id`. If it missed too many (`"resync": true`),
   reload the ticket list and the open ticket with REST, then carry on with `latest_id`.

Keep the highest event `id` you have seen, and send it as `last_event_id` when you reconnect.

Instead of the `auth` message, a client that can set headers on the handshake may send
`Authorization: Bearer <access_token>` and put the last id in the address:
`wss://<host>/ws/support/app?last_event_id=1795856462026`. The server then answers `hello` at once.

While the socket is open, the server checks every 30 seconds that the login may still use it. A login that
was switched off is closed with `4403`.

### Messages from the server

| `type` | Meaning |
|--------|---------|
| `hello` | Signed in (see above) |
| `event` | Something changed on one of the user's tickets |
| `typing` | Support is typing on a ticket |
| `pong` | Answer to `ping` |
| `error` | A message from the app named a ticket the user may not follow: `{"type": "error", "error": "not_found", "ticket_id": "..."}` |

Event examples (the app gets only its own tickets, and never staff details):

```json
{ "type": "event", "id": 1795856462023,
  "event": { "id": 1795856462023, "type": "ticket.created", "ticket_id": "12d8e1d4-3c26-4847-8ddb-f404090a9aa6",
             "ticket_no": "TS-2026-000002", "data": {} } }
```

```json
{ "type": "event", "id": 1795856462025,
  "event": { "id": 1795856462025, "type": "ticket.updated", "ticket_id": "12d8e1d4-3c26-4847-8ddb-f404090a9aa6",
             "ticket_no": "TS-2026-000002",
             "data": { "change": "status", "status": "ASSIGNED", "status_label": "In review" } } }
```

```json
{ "type": "event", "id": 1795856462026,
  "event": { "id": 1795856462026, "type": "message.created", "ticket_id": "12d8e1d4-3c26-4847-8ddb-f404090a9aa6",
             "ticket_no": "TS-2026-000002", "data": { "message_id": 7 } } }
```

| `event.type` | `data` | What the app does |
|--------------|--------|-------------------|
| `ticket.created` | `{}` | Add the ticket to the list (a ticket raised from another phone) |
| `ticket.updated` | `change: "status"`, `status`, `status_label` | Update the status chip (show `status_label`); reload the ticket if it is open |
| `message.created` | `message_id` | `GET /tickets/{id}/messages?after_id=<last id>` |
| `message.deleted` | `message_id` | Show that message as deleted (or reload the ticket with `GET /tickets/{id}`) |
| `typing` (message `type: "typing"`) | `typing: true` | Show "Support team is typing…" for a few seconds |

Events carry ids and small facts only, never message text. Fetch the text with REST.

### Messages from the app

| Message | Effect |
|---------|--------|
| `{"type": "ping"}` | The server answers `{"type": "pong"}`. Send one every 25 to 30 seconds to keep the line open. |
| `{"type": "typing", "ticket_id": "..."}` | Support sees that the user is typing |
| `{"type": "read", "ticket_id": "..."}` | Same as `POST /tickets/{id}/read` |

### Closing codes

| Code | Meaning | What to do |
|------|---------|------------|
| `4401` | Not signed in: no `auth` message in time, or a bad or expired token | Refresh the token (log in again), then reconnect |
| `4403` | The login may not use this socket (not a requester) | Do not reconnect |
| `1013` | The server is busy, or the app read events too slowly | Reconnect after a few seconds |

Reconnect with a growing wait (1, 2, 4 … up to 30 seconds) and the last event id. If the socket cannot be
opened at all, poll `GET /tickets` every 30 to 60 seconds while a support screen is open.

---

## 9. Push notifications

### Register the phone

After login, and every time Firebase gives the app a new token:

`POST /api/v1/notifications/devices`

```json
{ "fcm_token": "dQw4w9WgXcQ:APA91bH-example-token-0001", "platform": "android", "app_version": "2.4.1" }
```

| Field | Rule |
|-------|------|
| `fcm_token` | Required, 20 to 512 characters |
| `platform` | `android` or `ios` |
| `app_version` | Optional, up to 30 characters |

```json
{ "status": true, "code": 200, "message": "Device registered",
  "data": { "platform": "android", "app_version": "2.4.1", "is_active": true } }
```

The same token again only refreshes it. A token used by another login on the same phone moves to this user.

The login itself can register the phone: `POST /api/v1/auth/login` accepts the optional fields `fcm_token`,
`platform` and `app_version`, and answers `push_registered: true` when it worked. A bad token never fails the
login.

On logout: `DELETE /api/v1/notifications/devices/{fcm_token}`

```json
{ "status": true, "code": 200, "message": "Device removed", "data": { "removed": true } }
```

### What a push carries

The server sends Firebase Cloud Messaging (HTTP v1) messages of this shape:

```json
{
  "message": {
    "token": "<fcm_token>",
    "notification": { "title": "Reply on TS-2026-000001", "body": "Please open Settings > Sync and tap 'Sync now'…" },
    "data": {
      "source": "support",
      "type": "TICKET_REPLY",
      "reference_id": "381ef83b-b5d1-46f6-911d-8e1a71e994fe",
      "ticket_no": "TS-2026-000001"
    },
    "android": { "priority": "high" },
    "apns": { "payload": { "aps": { "sound": "default" } } }
  }
}
```

When the user taps it, open the ticket `data.reference_id` if `data.source` is `"support"`.

| `data.type` | Title | Body | When |
|-------------|-------|------|------|
| `TICKET_REPLY` | `Reply on TS-…` | The reply, cut to 100 characters (a file: "The support team sent you a file."; a voice message: "The support team sent you a voice message.") | Support replied |
| `TICKET_STATUS` | `TS-…: In review` (the status label) | The ticket subject | Support moved the ticket |
| `TICKET_RESOLVED` | `TS-… is resolved` | "Your problem is marked as solved. Reopen the ticket if it is not." | Support resolved it |

No push is sent for internal notes, or for the user's own messages, close or reopen. Replies and status
pushes are skipped while the app has the live socket open (the user sees them live). Every `data` value is a
string.

---

## 10. Values and enums

### Ticket status

| `status` | `status_label` (show this) | Open? |
|----------|----------------------------|-------|
| `NEW` | Received | yes |
| `ASSIGNED` | In review | yes |
| `IN_PROGRESS` | In progress | yes |
| `WAITING_ON_USER` | Waiting for your reply | yes |
| `ESCALATED` | In progress | yes |
| `RESOLVED` | Resolved | no |
| `CLOSED` | Closed | no |
| `REOPENED` | Reopened | yes |

`WAITING_ON_USER` means support asked the user something: highlight the ticket.

### Priority

`LOW`, `MEDIUM`, `HIGH`, `URGENT`. Support sets it; the app only shows it.

### Message kind

| `kind` | Meaning |
|--------|---------|
| `TEXT` | A typed message |
| `ATTACHMENT` | A file; `body` is the file name and `attachments` holds the file |
| `AUDIO` | A voice message; `attachments` holds the audio file (show a player, not the file name) |
| `SYSTEM` | A line written by the server |

Any kind can come with `is_deleted: true` (see section 6).

### Timeline types the app can see

`CREATED`, `STATUS_CHANGED`, `REPLIED` (support replied), `REQUESTER_REPLIED`, `ATTACHMENT_ADDED`,
`MESSAGE_DELETED`.

---

## 11. App flow checklist

1. Log in; register the FCM token (in the login body or with `POST /notifications/devices`).
2. Support home: `GET /tickets`, badge from `unread`; open the socket while this screen or a ticket is open.
3. New ticket: `GET /categories`, then `POST /tickets` with device details and a fresh `client_request_id`.
4. Ticket screen: `GET /tickets/{id}`, then `POST /tickets/{id}/read`. On `message.created`, fetch with
   `after_id`. Send with `POST /tickets/{id}/messages` (with a `client_request_id`), files with
   `POST /tickets/{id}/attachments`.
5. Buttons from `can_reply`, `can_close`, `can_reopen`.
6. Push tap with `source = "support"`: open ticket `reference_id`.
7. Logout: `DELETE /notifications/devices/{fcm_token}`, close the socket.

---

## 12. Endpoint summary

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/support/categories` | Categories to choose from |
| POST | `/api/v1/support/tickets` | Raise a ticket |
| GET | `/api/v1/support/tickets` | My tickets |
| GET | `/api/v1/support/tickets/{ticket_id}` | One ticket with chat and timeline |
| POST | `/api/v1/support/tickets/{ticket_id}/read` | Mark replies as seen |
| POST | `/api/v1/support/tickets/{ticket_id}/close` | Close |
| POST | `/api/v1/support/tickets/{ticket_id}/reopen` | Reopen |
| GET | `/api/v1/support/tickets/{ticket_id}/messages` | Newer messages |
| POST | `/api/v1/support/tickets/{ticket_id}/messages` | Send a message |
| DELETE | `/api/v1/support/tickets/{ticket_id}/messages/{message_id}` | Delete my message |
| POST | `/api/v1/support/tickets/{ticket_id}/attachments` | Send a photo, PDF or voice message |
| GET | `/api/v1/support/attachments/{attachment_id}` | Download a file |
| POST | `/api/v1/notifications/devices` | Register the phone for pushes |
| DELETE | `/api/v1/notifications/devices/{fcm_token}` | Stop pushes (logout) |
| WS | `/ws/support/app` | Live updates |
