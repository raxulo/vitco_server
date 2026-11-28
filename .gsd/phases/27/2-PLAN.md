---
phase: 27
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/web/static/js/support_live.js
  - app/web/static/js/support.js
  - app/web/static/css/support.css
  - app/web/templates/support/partials/topbar.html
  - app/web/templates/support/partials/sidebar.html
  - app/web/templates/support/pages/tickets/*.html
  - app/modules/support/application/unread.py
  - tests/support/test_live_ui.py
must_haves:
  - A new ticket, assignment, message, status change, note or call shows on open screens without a refresh
  - Sidebar badges, tab title count, toast and soft sound update live
  - Live badge shows Live / Reconnecting; the client reconnects with backoff and replays missed events
  - Polling fallback every 20 s when the socket is down
  - Live chat in the ticket detail shows typing and delivered / read state
  - Unread counts are correct after reload (database is the source, Redis only caches)
gap_closure: false
---

# Plan 27.2: Live portal and live chat UI

## Objective
Make the portal feel instant and calm, with no refresh needed (REQ-73 to REQ-75, D-11, D-13).

## Context
- Plan 27.1; docs/TECHNICAL_SUPPORT_PLAN.md section 6 (event table) and 10A
- app/web/static/js/htmx.js for swapping fragments

## Tasks

<task type="auto">
  <name>Live client and list updates</name>
  <files>support_live.js, support.js, topbar, sidebar, ticket list templates</files>
  <action>A small dependency-free client: connect, authenticate, heartbeat, exponential backoff, `last_event_id`
  replay, polling fallback, one event dispatcher. Handlers: insert / update / remove list rows (server-rendered row
  fragment fetched with HTMX by id, so markup stays in templates), update badges and tab title, toast with link, soft
  sound (toggle in the profile menu, off by default for Viewers), optional browser notification when the tab is in the
  background (asks permission once). `aria-live="polite"` announcements. Reduced-motion respected for row highlight.
  AVOID: duplicating row markup in JavaScript; sound before the user has interacted with the page.</action>
  <verify>headless-browser script with two sessions: create ticket through the API, row appears for the team in
  under 2 s; assigned ticket leaves another member's list; kill the socket, reconnect, missed event appears</verify>
  <done>No refresh needed for any event in the plan-doc table.</done>
</task>

<task type="auto">
  <name>Live chat and unread counts</name>
  <files>pages/tickets/detail.html, unread.py</files>
  <action>Conversation appends messages live, scrolls only when the user is at the bottom (otherwise shows a "New
  messages" pill), typing indicator, sent / delivered / read ticks, reply sent optimistically with retry on failure.
  `unread.py`: per (ticket, member) last-read id in the database, counts computed from it and cached in Redis; opening a
  ticket marks it read and publishes `unread.changed`. Requester-side read state comes from the mobile `read` call.
  AVOID: marking messages read while the tab is hidden.</action>
  <verify>two-session chat test; unread count equals database truth after Redis flush; screenshots at 1440 and 390 px;
  user visual review</verify>
  <done>Live conversation works between a requester socket and two staff sessions with correct unread counts.</done>
</task>

## Must-Haves
- [ ] Redis flushed or stopped mid-session: portal falls back and recovers without a page reload

## Success Criteria
- [ ] Tests green; Phase 27 verification written; commit message proposed
