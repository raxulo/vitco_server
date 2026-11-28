---
phase: 27
plan: 1
wave: 1
depends_on: []
files_modified:
  - requirements.txt
  - app/core/config.py
  - app/config/settings.py
  - app/infrastructure/redis_client.py
  - app/modules/support/application/events.py
  - app/modules/support/application/event_bus.py
  - app/modules/support/application/presence.py
  - app/modules/support/application/audience.py
  - app/api/v1/routers/support_ws.py
  - app/bootstrap/lifespan.py
  - app/middleware/authentication.py
  - tests/support/test_realtime.py
must_haves:
  - Redis client is optional; with REDIS_URL unset or Redis down the app starts and events use the in-process bus
  - Events are published after the database commit, never before
  - Audience is computed on the server from permission and team scope
  - Staff WebSocket and mobile WebSocket authenticate with the existing token within the configured timeout
  - Reconnect with last_event_id replays missed events; events carry an increasing id
  - Presence (online, typing) is kept in Redis with expiry
gap_closure: false
---

# Plan 27.1: Redis, event bus, presence and WebSocket endpoints

## Objective
The realtime backbone (REQ-73, REQ-74, REQ-75, DECISION-032).

## Context
- docs/TECHNICAL_SUPPORT_PLAN.md section 6; app/config/websocket.py (already holds limits and timeouts)
- app/bootstrap/lifespan.py for start / stop; CON-08 (single process, so keep work light)

## Tasks

<task type="auto">
  <name>Redis and event bus</name>
  <files>requirements.txt, settings, redis_client.py, events.py, event_bus.py, presence.py, lifespan.py</files>
  <action>Add `redis` (asyncio client); `REDIS_URL` setting (empty = disabled). Client wrapper with connect-on-demand,
  timeouts and a `healthy` flag. `events.py`: event types (ticket.created, ticket.updated, ticket.assigned,
  message.created, note.created, call.logged, unread.changed) with a compact JSON shape. `event_bus.py`: `publish`
  (Redis pub/sub channel plus a capped Redis stream or in-memory ring for replay, event id from a counter), `subscribe`
  per socket, in-process fallback when Redis is unavailable, automatic switch back. Handlers register events in the
  unit of work and the bus publishes them after commit (post-commit hook in the database manager). `presence.py`: set /
  clear online with TTL heartbeat, typing with a 5 s TTL, `is_online(user_id)`.
  AVOID: failing a request because Redis is down; publishing inside an open transaction; blocking calls.</action>
  <verify>tests with a fake Redis and with Redis disabled: event reaches the in-process subscriber; publish after
  rollback sends nothing; replay returns events after `last_event_id`; presence expires</verify>
  <done>Events flow with and without Redis and are never sent for rolled-back work.</done>
</task>

<task type="auto">
  <name>Audience and WebSocket endpoints</name>
  <files>audience.py, support_ws.py, authentication.py</files>
  <action>`audience.py`: from an event and the ticket, return the user ids that may see it - the requester (public
  events only), the assignee, the team Manager, members with `support.ticket.view_all` in the team, Ticket Assigners
  for unassigned-in-team events, Super Admin for the unassigned pool. `support_ws.py`: `/ws/support` for staff and
  `/ws/support/app` for requesters; first message carries the token (checked within `authentication_timeout`), then the
  server sends `hello` with the latest event id. Client messages: `ping`, `typing`, `read` (ticket id). Server messages:
  events, `typing`, `presence`. Honour `max_connections`; close with clear codes. Register the paths so the HTTP
  authentication middleware does not reject the upgrade but the socket still authenticates itself.
  AVOID: filtering on the client; letting a socket subscribe to a ticket id it cannot read.</action>
  <verify>tests: member without view_all never receives another member's ticket event; requester never receives
  internal notes; bad token closes the socket; reconnect with `last_event_id` replays; 2 staff + 1 requester chat</verify>
  <done>Events are delivered only to permitted users on both socket types.</done>
</task>

## Must-Haves
- [ ] Redis outage does not break tickets, chat REST or the dairy features

## Success Criteria
- [ ] Tests green with Redis on and off