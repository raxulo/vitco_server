# Plan 27.2 Summary: Live portal and live chat UI

**Status:** ✅ Complete (2026-11-22), visual sign-off by the user pending

## What was built
- `support_live.js` (dependency-free): one socket, heartbeat, exponential backoff, `last_event_id` catch-up,
  reload of the affected parts on `resync`, polling every 20 s while the socket is down. Markup always comes from
  the server's own pages (fetched and picked apart), never built in JavaScript.
- Topbar badge Live / Reconnecting / Offline; sidebar badges and the tab title `(n)` update live
  (`/support/_live/counts`, which also reports the latest event id).
- Ticket list: refreshes on events, new rows flash (respects reduced motion).
- Ticket detail: new messages and internal notes append without touching the reply box; when scrolled up a
  "New messages" pill shows; the side panel and header refresh (never while a control in it has focus); typing
  indicator ("A colleague / The requester is typing…", hides after 5 s); `read` is sent only while the tab is visible.
- Toasts for new tickets, new messages and tickets assigned to the member; optional soft sound and desktop
  notification behind "Sound and desktop alerts" in the profile menu (off by default, permission asked on that click).

## Verification in a real browser
`live_e2e` run: real uvicorn + headless Chrome driven over DevTools, a farmer acting through the mobile API.
New ticket row 0.4 s after the API call, with badge, title count and highlight; requester message and internal
note appear live; typing indicator shows; after the socket was cut server-side a ticket created during the outage
appeared after reconnect (1.2 s) and the badge returned to Live.

## Deferred
- Delivered / read ticks per message and per-member unread counts: unread stays one counter per side on the ticket
  (database is the truth; Redis holds nothing of it), which is correct for a team queue; per-member read state can
  come with the reports work.
- Checked with a fake shared Redis and with Redis down; no real Redis server was available here.
