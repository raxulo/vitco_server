# Plan 29.1 Summary: Call log and call UI

**Status:** ✅ Complete (2026-11-22), visual sign-off by the user pending

## What was built
- Migration `0008`: `support_call_logs` (ticket, member, requester, started, finished, outcome, duration, note).
- `CallHandler`: `start_call` needs `support.call.make` and a ticket the member may see; records the intent, a
  staff-only timeline event (`CALL_STARTED`), an audit row and a live update, and returns the number. One open call
  per member: pressing Call again on the same ticket keeps one record, another ticket is refused (409) until the
  outcome is recorded. `finish_call`: only the member who called, once; outcome Connected / Not reachable / Busy /
  Callback requested, optional length (0-6 h) and note (≤ 1000); `CALL_LOGGED` event and audit row.
- Portal: the phone number stays visible to everyone (D-6); a Call button (`tel:`) only with the permission. The
  click records the call first (`POST /support/tickets/{id}/calls`, JSON) and then dials. Back on the page (or after
  4 s on a computer without a phone app) the side panel shows "How did the call go?" (outcome chips, minutes, note;
  not a blocking modal, nothing auto-submitted). An open call on another ticket shows a reminder with a link. Call
  history card on the ticket; call lines in the timeline. Requesters never see call events.
- Seeing the requester's number is audited (`ticket.phone_viewed`) once per member, ticket and day (REQ-64); the
  number itself is never written to the audit meta or the logs.

## Tests
`tests/support/test_calls.py` — 12 tests: permission per role, ticket scope, one open call, ownership and outcome
validation, events and audit rows, nothing for the requester, Call button per role, the portal flow end to end,
refusals as JSON / notice, the reminder, phone-view audit once a day.

## Not verified
A real phone dialling from the `tel:` link (needs a device); the flow around it is tested.
