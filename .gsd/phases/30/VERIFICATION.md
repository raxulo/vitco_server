# Phase 30 Verification: Hardening, API Document and Verification

**Date:** 2026-11-28 · **Branch:** `feature/support-foundation` (uncommitted, on top of 31f0433)
**Local stack:** PostgreSQL 18.7 (Docker `vitco-pg18`), Redis 7 (Docker), Windows 11, Python 3.14 venv

## Permission matrix (`tests/support/test_permissions_matrix.py`, 831 cases)
17 kinds of user (anonymous, Super Admin, Admin, Sub Admin, a support login without a team, MCC, VLCC, Farmer,
VLCC Farmer, the Manager, the five role templates, a custom "assign only" role, another team's Manager) against:

| Area | Cases | How allow / deny is judged |
|---|---|---|
| 25 portal screens | 425 | 200 vs anything else; anonymous goes to `/login`; another team's Manager sees none of this team's tickets, members, roles, activity or audit |
| 8 ticket actions × unassigned / own ticket | 192 | the change in the database (message, internal note, assignee, priority, category, status, call log, team) |
| 8 administration actions | 136 | the change in the database (team, category, member, role) |
| Mobile API (11 endpoints) | 17 roles | 401 anonymous, 403 non-requesters, 404 someone else's ticket, 2xx for each requester role on its own ticket |
| Sockets | 34 handshakes + 10 message cases | `hello` / 4401 / 4403; `not_found` for tickets the user may not follow |
| Other | | internal files never reach the requester; size and type limits (422); no support path is public (53 routes); audit rows for assignment, phone view, call start and outcome, member and role creation; no phone number or token in any log record |

The expected table is written out in the test (`GRANTS`, `sees`), not read from `ROLE_TEMPLATES`.

## Found and fixed
| # | Found by | Problem | Fix |
|---|---|---|---|
| 1 | matrix | A role with only `support.ticket.assign` saw the unassigned queue but could not open those tickets | `_staff_can_see` follows the same rule as the socket audience and queue counts |
| 2 | matrix | Team activity sent a Manager away when `?team=` named another team | `?team=` only for Super Admin, as on members, roles and audit |
| 3 | example run | "A in progress ticket cannot be moved to reopened." | "A ticket that is in progress cannot be reopened." (requester words for the app) |
| 4 | test run | Tests used the developer's Redis from `.env` | `REDIS_URL` empty in tests unless `TEST_REDIS_URL` is given |
| 5 | code review | With Redis on, event ids came from the local clock only (INCR started at 1), and two events published together could share an id, so a reconnect could skip one | Local id reserved before any await; Redis counter lifted atomically (Lua `incr_at_least`) |
| 6 | code review | One push that raised (bad key, odd Firebase answer) left the rest of its batch in SENDING until a restart | Per-row error handling: back to PENDING with backoff, FAILED after 5 tries; stuck rows also released hourly |
| 7 | code review | `release_stuck` measured from the due time, so a restarting process could resend a push another process was sending | A SENDING row's `next_attempt_at` is its claim time |
| 8 | code review | An open staff socket kept the permissions it had when it connected (disabled member still heard the team) | Access re-checked every 30 s: closed with 4403 when gone, audience updated on a role change |
| 9 | code review | A socket signed in with an `Authorization` header could not resume (`last_event_id` ignored) | `?last_event_id=` read for header and cookie sign-in |
| 10 | code review | Two retries with the same `client_request_id` at the same moment gave a 500 | Unique clash becomes `DuplicateClientRequestException`; the handler answers with the saved ticket or message |
| 11 | code review | The status event of an assignment carried the old assignee, so the new assignee's screen missed it | The status event names the new assignee |
| 12 | code review | A member with `support.role.manage` could edit the role they hold and give themselves anything | No editing one's own role; only permissions one holds can be given |
| 13 | security review | Same through `support.member.manage`: a login created by the member could get a stronger role | The role given to a member may not exceed the actor's own access (Manager and Super Admin not limited) |
| 14 | code review | The app socket showed raw internal status codes without the app's label | `status_label` added to requester status events |
| 15 | user | The portal's live badge said "Reconnecting" on every page change (the socket closes and reopens with each page) | "Reconnecting" only after 3 s down (counted from the first drop); closing because of `pagehide` is not a drop; a page opened right after a live one starts as Live (inline check before paint). Headless Chrome, 6 page changes: only "Live" painted; server stopped: "Reconnecting" after 3.0 s |

The security review's only candidate (#13) scored 5/10 in its false-positive check, below the reporting bar of 8, so
the security report has no findings. It was fixed anyway because it is the same gap as #12 by another route.

Each fix has a test that fails without it.

## Automated
| Check | Result |
|---|---|
| Support + notification suites, PostgreSQL 18.7 + real Redis (`TEST_DATABASE_URL`, `TEST_REDIS_URL`) | 1104 passed, 1 failed before the test update for fix 11; realtime file re-run: 35 passed |
| Support + notification suites, SQLite | 1103 passed, 3 skipped (12 clean runs in a row); see "Open" for an intermittent SQLite lock |
| Full suite, SQLite (before the review fixes) | 2170 passed, 2 skipped |
| Full suite, SQLite (final, all fixes) | **2181 passed, 3 skipped** (5 min 40 s), including `large_import_throughput` |

## End-to-end (real uvicorn on PostgreSQL 18.7 + Redis, pushes to a file sender)
Own database `quickyee_verify_<hex>` and Redis container on port 6380, both removed afterwards. **43/43 checks passed**
(run again after the review fixes: 43/43):
Super Admin signs in, creates a team and a category; the Manager signs in and creates a member; a farmer registers a
device and raises a ticket by API (a retry returns the same ticket); the Manager hears it live in ~110 ms, the
assigned-only member does not; assignment and status changes reach the member and the app (no staff details);
reply, internal note (never on the app socket, API or push), farmer answer, call with outcome; pushes for the reply
and the resolve while the app is closed (right token, `source=support`, ticket id); farmer closes; with Redis
stopped tickets are still raised and delivered in-process and the counts say Redis is down; after Redis is back
delivery goes through it again; a reconnecting socket replays what it missed; no server tracebacks.

### Load check
| Measure | Value |
|---|---|
| Sockets open at once | 200 / 200 (150 staff, 50 app) |
| Tickets in the burst | 100, 20 in parallel, 6.0–6.3 s |
| Deliveries | 20 000 / 20 000, none lost, no socket closed |
| Event after the API answer | p50 0 ms, p95 0 ms (events arrive before the HTTP answer) |
| Ticket API during the burst | p50 ≈ 0.85 s, p95 ≈ 3–4 s |
| One ticket on a quiet server | API 54–57 ms, all 200 sockets within 43–44 ms |

Delivery adds nothing measurable; under a 20-parallel burst the ticket API itself is the slow part
(~16 tickets/s on this laptop, client and server on one machine). Far above the expected support load.

## Not verified
- Real Firebase delivery (no service-account JSON yet; the FCM HTTP v1 sender is tested against a fake Google).
- Dialling from a real phone (`tel:`).
- Several API processes sharing one Redis (covered by tests with a shared fake Redis and the atomic counter test on
  real Redis, not by running two uvicorn processes).

## Open
- **Rate limits** on ticket and message creation: Version 3 in the plan (§11A), not built.
- **Intermittent SQLite `database is locked`** in the matrix (WAL snapshot upgrade), seen in 3 of 25 full support runs
  on SQLite (0 in the last 12), never on PostgreSQL; see STATE for what was ruled out.

## Must-haves
- [x] A permission matrix test covers every support endpoint and screen for every role
- [x] `docs/SUPPORT_API.md` lets app developers integrate without reading code (REST, WebSocket, push payloads, errors)
- [x] End-to-end run on PostgreSQL with Redis and the real worker passes
- [x] Realtime load check for 200 sockets and a burst of 100 tickets shows no loss and acceptable latency
- [ ] The user signs off the UI at desktop and phone widths
