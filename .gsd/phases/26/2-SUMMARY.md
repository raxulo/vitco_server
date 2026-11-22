# Plan 26.2 Summary: Mobile REST API for tickets, messages and attachments

**Status:** ✅ Complete (2026-11-22)

## What was built
`/api/v1/support` for MCC, VLCC, Farmer and VLCC_FARMER logins (everyone else gets 403, no token 401):

| Call | Purpose |
|---|---|
| `GET /categories` | active categories |
| `POST /tickets` | raise a ticket; 201, or 200 with the first ticket for a repeated `client_request_id` |
| `GET /tickets` | own tickets, `status` filter, standard list envelope |
| `GET /tickets/{id}` | ticket, public messages, public timeline, `can_reply / can_close / can_reopen` |
| `GET /tickets/{id}/messages?after_id=&limit=` | newer messages, `next_after_id` |
| `POST /tickets/{id}/messages` | send a message (idempotent by `client_request_id`) |
| `POST /tickets/{id}/attachments` | multipart photo / PDF |
| `POST /tickets/{id}/read`, `/reopen`, `/close` | |
| `GET /attachments/{id}` | download, only for the ticket's requester (or staff of the ticket's team) |

- Response models (`schemas/support.py`) list exactly what the app may see: staff are "Support team", never a name,
  id, phone or team; statuses use requester wording ("Received", "In review", "Waiting for your reply"); internal
  notes and internal events are filtered in the handler.
- `AttachmentService`: JPEG, PNG, WebP, PDF, 10 MB, content signature checked (not only the declared type), file
  name sanitised, stored under `support/<ticket>/` of the media storage. That folder is not a `MediaCategory`, so the
  public `/api/v1/media/` route cannot serve it; files are removed again when the transaction rolls back.
- No path was added to the public routes list.

## Tests
`tests/support/test_support_api.py` — 25 tests: roles, envelopes, idempotency, 404 on other users' tickets for every
endpoint, no leaks of notes / assignee / team ids, message paging, close / reopen, attachment accept / reject
(wrong type, wrong signature, empty, over 10 MB), private downloads, OpenAPI paths.
