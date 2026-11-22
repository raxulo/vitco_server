# Plan 27.1 Summary: Redis, event bus, presence and WebSocket endpoints

**Status:** ✅ Complete (2026-11-22)

## What was built
- `REDIS_URL` (empty = off) and `SUPPORT_EVENT_BUFFER` settings; `redis==8.1.0`; `app/infrastructure/redis_client.py`:
  every call returns `None` / `False` instead of raising when Redis is off or down, and waits 5 s before retrying.
- `EventBus`: events are queued on the database session and published only on `after_commit`, dropped on rollback.
  With Redis up, ids come from `INCR` and delivery from pub/sub (so several processes agree); otherwise the process
  delivers directly. A bounded ring lets a reconnecting client replay what it missed; too old an id answers
  `resync`. Typing is ephemeral (no id, never stored).
- `audience.can_receive`: pure rules over permission and team scope (requester: own public events; Super Admin:
  all; team staff: Manager / `view_all` the team, `view_assigned` their own tickets and the one just taken from
  them, Ticket Assigner the unassigned ones; nobody hears another team or the pool).
- `SocketHub`: open sockets, bounded send queue per socket (a slow one is closed and catches up), presence = open
  socket here + Redis key with expiry for other processes.
- `/ws/support` (staff, cookie sign-in, same-origin only) and `/ws/support/app` (requesters, token in the first
  message within `authentication_timeout`): `hello` (`latest_id`, `resync`), replay filtered by audience, client
  `ping` / `typing` / `read`, close codes 4401 / 4403 / 1013.
- `TicketHandler` emits `ticket.created`, `ticket.updated` (assigned, status, priority, category, routed),
  `message.created`, `note.created` (staff only).

## Decided while building
- Audience is computed per delivery from the permissions loaded when the socket opened; a role change applies at
  the next reconnect (a disabled member cannot reconnect).
- Event ids start at the server start time in milliseconds, so ids from an older run are recognised and trigger a reload.
- Redis is used only for delivery across processes, ids and presence; tickets and counts never depend on it.

## Tests
`tests/support/test_realtime.py` — 28 tests: audience rules, ids and replay, commit / rollback, Redis down, two
processes on a fake shared Redis, presence, and the socket endpoints (auth failures, origin check, audience per
role, assignment hand-over, requester never sees notes or staff details, replay, typing, read, 2 staff + 1
requester chat, connection limit, disabled member).
