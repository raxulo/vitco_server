# Technical Support Module — Discussion & Design Document

> Status: **DRAFT (discussion phase)** — implement nahi karna jab tak yeh document final na ho.
> Date: 2026-11-18 · Branch idea: `feature/technical-support` (from `develop`)

---

## 1. Yeh kya hai? (Vision)

**Technical Support** = Quickyee app ke users (MCC, VLCC, Farmer, Sub-admin etc.) ki queries/problems ko
**receive, manage, solve, contact (chat / call) aur status dena**.

Yeh ek **poora alag portal** hoga:

- Alag URL space (`/support/...`), alag layout, **alag sidebar**.
- Existing sidebar (MCC / VLCC / Payments / Marketplace...) se **koi lena dena nahi**.
- Support-team ke log sirf support portal dekhenge, dairy data (collections, payments) nahi (jab tak explicitly permission na ho).
- Super Admin hi **Support Team** bana sakta hai.

---

## 2. Actors (Kaun kya hai)

| Actor | Kaun | Kya karta hai |
|---|---|---|
| **Super Admin** | Existing role | Support Team banata hai, Team Manager assign karta hai, global settings/categories/SLA, sab kuch dekh sakta hai |
| **Support Team Manager** | Team ka head (ek team ka) | Apni team ke members banata/edit/disable karta hai, unke roles-permissions set karta hai, tickets assign/reassign, team ka dashboard/report dekhta hai. Team ke andar **sab kuch** dekh + manage kar sakta hai |
| **Support Member** | Team ke andar, alag-alag *support roles* ke saath | Permissions ke hisaab se kaam |
| **App User (Requester)** | MCC / VLCC / Farmer / Sub-admin | App se query/ticket raise karta hai, chat karta hai, status dekhta hai |

### Support Member ke role types (examples — fully configurable)

| Support Role | Typical kaam |
|---|---|
| **Technical Support** | Technical issue dekhna, reply, resolve, call |
| **Ticket Assigner (Dispatcher)** | Incoming tickets apni team ke members ko assign karta hai |
| **Read-only / Viewer** | Sirf dekh sakta hai (audit / trainee / QA) |
| **Chat Agent** | Sirf user se chat reply |
| **Caller** | Call karne ki permission |

> Roles **hard-coded nahi** — Manager (ya Super Admin) permission-set se naye support roles bana sake
> (e.g. "Senior Resolver" = view + reply + resolve + call + reopen).

---

## 3. Data hierarchy

```
Super Admin
 └── Support Team (many)                       -- sirf Super Admin banata hai
      ├── Team Manager (1 ya zyada)
      └── Members (many)  ── each has ── Support Role ── Permissions
```

- Ek user **ek hi team** ka member (v1 decision; multi-team baad mein, see Q-3).
- Ek team ke **multiple managers** ho sakte hain? (Q-2)

---

## 4. Permission Model (granular)

Permissions string-based hain, jaise existing `Permission` StrEnum (`user.create`...). Naya namespace `support.*`:

| Permission | Matlab |
|---|---|
| `support.ticket.view_all` | Team ke saare tickets dekhna |
| `support.ticket.view_assigned` | Sirf apne assigned tickets dekhna |
| `support.ticket.reply` | Ticket/chat mein reply |
| `support.ticket.assign` | Dusre member ko assign/reassign |
| `support.ticket.resolve` | Resolved mark karna |
| `support.ticket.close` / `reopen` | Close / reopen |
| `support.ticket.change_priority` | Priority/category badalna |
| `support.ticket.internal_note` | Internal note (user ko nahi dikhta) |
| `support.ticket.delete` | (rare) soft delete |
| `support.chat.use` | User se live chat |
| `support.call.make` | User ko call karna (phone number dikhna + call log) |
| `support.member.manage` | Members create/edit/disable (Manager) |
| `support.role.manage` | Support roles/permissions edit (Manager) |
| `support.report.view` | Team dashboard/reports |
| `support.team.manage` | Team create/edit (**Super Admin only**) |

Rules:
- **Baseline access (permission nahi chahiye)**: requester ka **basic profile / MCC-VLCC info + device/machine details + app version** har support member dekh sakta hai (Viewer samet). Iske liye alag permission nahi hai. Dairy data (collections, payments) kisi ko nahi (D-6).
- **Phone number bhi baseline hai**: requester ka phone number **har support member dekh sakta hai**. Sirf **call karna** (`tel:` button + call log) `support.call.make` se controlled hai. Number dekhna audit log mein jayega.
- **Super Admin** = `*`. **Team Manager** = team scope ke andar saari `support.*` (except `team.manage`).
- Permission check **server side** (router/handler) — sirf UI hide karna kaafi nahi.
- Member ka scope hamesha **uski team** tak limited (team_id filter har query mein).

---

## 5. Ticket lifecycle

```
NEW ──► OPEN/ASSIGNED ──► IN_PROGRESS ──► WAITING_ON_USER ──► RESOLVED ──► CLOSED
                │                                   │             │
                └──────────── ESCALATED ◄───────────┘             └──► REOPENED
```

| Status | Meaning |
|---|---|
| NEW | User ne raise kiya, kisi ne uthaya nahi |
| ASSIGNED | Kisi member/team ko diya gaya |
| IN_PROGRESS | Member kaam kar raha hai |
| WAITING_ON_USER | User se info chahiye (SLA timer pause) |
| ESCALATED | Manager/senior ko bheja |
| RESOLVED | Solution diya, user confirm kare |
| CLOSED | Final (auto-close agar user 3-7 din reply na kare) |
| REOPENED | User ne resolved ke baad phir problem batayi |

Har ticket ke fields: `ticket_no` (e.g. `TS-2026-000123`), requester, requester_role, category, priority
(LOW/MEDIUM/HIGH/URGENT), subject, description, attachments (screenshot/photo), device/app-version info,
team_id, assigned_to, status, timestamps (`now_naive_ist`), SLA due times, rating/feedback.

**Har change timeline mein** (audit): `TicketEvent` (status change, assign, note, call, priority change — kisne, kab).

---

## 6. Realtime (user ki query turant dikhe)

Abhi codebase mein sirf `app/config/websocket.py` (config) hai — **WebSocket implementation nahi hai**. Naya banana hoga.

- **Support portal (web)**: WebSocket (ya SSE) se naya ticket / naya message / assignment badge + sound/toast.
- **Permission-based fanout**:
  - naya ticket → team ke un members ko jinke paas `view_all` hai + assigners + manager.
  - assigned ticket → sirf assignee + manager.
  - user ka message → ticket ke assignee + manager (+ view_all wale).
- **App user side**: chat/status updates ke liye same WS (mobile app) + **push notification (FCM)** jab app band ho (Q-6).
- **No-refresh rule (user requirement, D-11)**: support member ko kabhi page refresh nahi karna padega. Jo bhi change ho, **turant screen par** aaye:

  | Event | Portal mein kya hoga |
  |---|---|
  | Naya ticket aaya | Queue / All Tickets / My Tickets list mein row upar apne aap judti hai (highlight), sidebar badge count +1, toast + halki sound |
  | Ticket assign / reassign hua | Assignee ki "My Tickets" mein turant, purane assignee ki list se hat jaye, notification |
  | User ka naya message | Khuli ticket ke chat mein message turant, list mein unread dot, browser tab title mein `(3)` count |
  | Status / priority badla | List row aur ticket detail ka status badge live badle |
  | Internal note / call log add hua | Ticket ki timeline mein turant |
  | Dashboard counts | My Activity / Manager dashboard ke cards live update |

- **Reliability**: WebSocket drop ho to auto-reconnect; reconnect par **chhute hue events catch-up** (last seen event id se) taaki kuch miss na ho; connection status chhota indicator ("Live" / "Reconnecting"). Browser notification (tab background mein ho tab) optional, permission maangkar.
- **Permission-safe**: event sirf unhi ko jayega jinhe us ticket ko dekhne ki permission hai (server side filter, client par nahi).
- **Redis (D-3)**: WebSocket event broadcast pub/sub se, presence (online/typing), unread-count cache. Redis down ho to DB counts + polling fallback.
- Fallback: polling (agar WS drop) — taaki kuch miss na ho. Unread counts DB mein.

### 6A. Mobile app side (MCC / VLCC / Farmer / VLCC_FARMER) — D-12

Requester sirf **mobile app** se ticket aur chat karte hain (web portal sirf support staff ka hai). Isliye backend ko mobile ke liye **API + WebSocket** dono dene honge.

| Cheez | Kaise |
|---|---|
| Ticket create / list / detail | REST `/api/v1/support/tickets...` (existing envelopes, existing app login token) |
| Chat messages bhejna / history | REST (send, list with `after_id` paging) |
| Live chat (app khula ho) | WebSocket `/ws/support` — same app auth token, handshake par verify (`authentication_timeout` config) |
| Attachments (screenshot) | multipart upload, image/PDF 10 MB tak |
| Status dekhna | ticket status + timeline (internal notes **kabhi nahi**) |
| Device info / app version | App ticket ke saath bhejti hai (`device_model`, `os_version`, `app_version`) — support member ko wahi dikhta hai (D-6) |
| User sirf **apne** tickets | server side `requester_id = current user` filter |

**Push notification (D-4 revised): BACKEND abhi banega, MOBILE app baad mein (user).** App band ho tab bhi user ko support ka reply push se pahunche:
- **Device token API**: `POST /api/v1/support/devices` (register: `fcm_token`, platform, app_version) aur `DELETE` (logout par hatao). Table `support_device_tokens` (user_id, token, platform, last_seen, is_active). Ek user ke multiple devices.
- **Notification service (backend)**: jab requester ko kuch dikhana ho (staff ka naya reply, status change, ticket assign/resolved) to outbox se **FCM** ke through push bhejta hai. Payload: `type`, `ticket_id`, `title`, `body` (mobile baad mein isi par deep-link karega).
- **Outbox pattern**: event pehle DB (`support_notification_outbox`) mein, background worker FCM bhejta hai (retry, invalid token cleanup). Isse ticket save hone par push fail ho to bhi ticket safe rahe.
- **Rule**: agar user us waqt WebSocket par online hai (Redis presence) to push skip, warna push.
- **FCM credentials**: Firebase project ka service-account JSON chahiye (secret `.env` mein, repo mein nahi) — user dega. Jab tak credentials nahi, push sender "disabled" mode mein (log karega) taaki baaki kaam na ruke.
- **Mobile (baad mein)**: token register karna, notification receive/dikhana, tap par ticket kholna — yeh hum baad mein banayenge.
- Support staff (web) ko FCM nahi — unhe WebSocket + browser notification.

**App developers ke liye**: backend ban jaye to `docs/SUPPORT_API.md` alag se likhenge (jaise `docs/MARKETPLACE_API.md`) — endpoints, WS events, error codes, example payloads.

**Offline**: app mein ticket bhejte waqt internet na ho to app apne aap retry kare; server `client_request_id` se duplicate ticket rok sakta hai (idempotency).

---

## 7. Chat

- Har ticket ke andar **thread** (ticket = conversation). Alag "general chat" v1 mein nahi (Q-4).
- Message types: text, image/file attachment, system event ("Ticket assigned to X").
- **Internal notes** alag — requester ko kabhi nahi dikhte.
- Delivered/seen indicators, "typing…" (optional).
- Canned/quick replies (templates) — member jaldi jawab de.
- Chat sirf `support.chat.use` / `ticket.reply` wale kar sakte; viewer sirf padh sakta.

---

## 8. Calling

Practical approach (v1): **Click-to-call** (`tel:` link) + **Call Log**.

- Button sirf `support.call.make` wale ko dikhe.
- Call ke baad member **outcome** log kare: connected / not-reachable / callback-requested + note + duration.
- Call log ticket timeline mein.
- Requester ka number har support member ko dikhta hai; sirf call button permission-controlled hai. Har call **audit log** mein jata hai.
- Future (v2): in-app VoIP / Exotel-Twilio style cloud telephony (Q-7).

---

## 9. Support Portal ke pages (alag sidebar)

**Sidebar by role/permission** (jo permission nahi, vo menu dikhe hi nahi):

| Menu | Kaun dekhe |
|---|---|
| Dashboard (open/overdue/today resolved) | sab |
| **My Activity** (member ka personal dashboard — niche §9A dekho) | sab members |
| Unassigned Queue | assigners, manager |
| All Tickets | view_all |
| My Tickets | view_assigned |
| Ticket detail (thread + timeline + notes + call log) | permission-wise |
| Chat inbox | chat.use |
| Team Members | manager (member.manage) |
| Roles & Permissions | manager (role.manage) |
| Categories / Canned Replies / SLA | manager |
| Reports (volume, SLA, per-agent, CSAT) | report.view |
| Support Teams (create/manage) | **Super Admin only** |
| My Profile / Availability | sab |

### 9A. Member ka personal dashboard — "My Activity" (V1, user decision)

Har support member ka apna dashboard: **usne kya kya kiya aur kitna kiya**.

| Section | Kya dikhega |
|---|---|
| Summary cards (aaj / hafta / mahina / custom date) | assigned tickets, resolved, closed, replies bheje, calls kiye, internal notes, reassign kiye |
| Abhi ka kaam | mere open tickets (status-wise), pending user-reply wale |
| Activity timeline | meri recent actions (ticket #, kya kiya, kab) |
| Calls | kitne calls, outcome-wise (connected / not-reachable / callback) |
| Trend | din-wise resolved/replies ka chhota chart |

Rules:
- Data **ticket events + call logs + messages** se banega (`support_ticket_events`, `support_call_logs`, `support_ticket_messages`) — alag table ki zarurat nahi, sirf aggregate queries.
- Member sirf **apna** dashboard dekhega. **Manager** apni team ke har member ka dashboard dekh sakta hai (member-wise comparison table samet). Super Admin sab.
- Role ke hisaab se cards badlenge (e.g. Ticket Assigner ko "tickets assign kiye", Technical ko "resolved", Viewer ko kuch nahi/khaali).
- Yeh **V1 ka basic personal count dashboard** hai. Team-wide reports, SLA, CSAT, Excel export abhi bhi V2.

---

## 10. Technical design (project standards ke saath)

Module: `app/modules/support/` — **DDD/CQRS 3-layer** (AGENTS.md ke mutabik):

```
app/modules/support/
├── domain/        entities, enums (TicketStatus, Priority, Permission), exceptions, repository, dto
├── infrastructure/ models, repository, mapper
└── application/   command, dto, handler (+ query handlers)
```

Naye tables (draft; migration `0005+`, Alembic):

| Table | Purpose |
|---|---|
| `support_teams` | id, name, code, is_active, audit/soft-delete |
| `support_roles` | id, team_id (null = global), name, permissions (JSON/array), is_system |
| `support_members` | id, user_id (FK users), team_id, support_role_id, is_manager, is_active, availability |
| `support_categories` | id, name, default_team_id, default_priority, sla_minutes |
| `support_tickets` | ticket_no, requester_user_id, category_id, priority, status, team_id, assigned_to, subject, description, sla_due_at, resolved_at, closed_at, rating... |
| `support_ticket_messages` | ticket_id, sender_id, body, is_internal, type, read_at |
| `support_ticket_events` | ticket_id, actor_id, event_type, from/to, meta, created_at |
| `support_attachments` | message/ticket id, file path (existing media module use), mime, size |
| `support_call_logs` | ticket_id, member_id, outcome, duration, note |
| `support_device_tokens` | user_id, fcm_token, platform, app_version, last_seen, is_active |
| `support_notification_outbox` | user_id, ticket_id, type, title, body, status (PENDING/SENT/FAILED), attempts, sent_at |
| `support_canned_replies` | team_id, title, body |

Integration points:
- **Users/Auth**: support staff bhi `users` table mein; naya `Role.SUPPORT = 8` (existing `Role` IntEnum ke end mein, 1–7 touch nahi). Fine-grained permission `support_members`+`support_roles` se. Login ke baad support users ko `/support` pe redirect; wo existing `/dashboard` sidebar nahi dekhein.
- **Web**: naya `app/web/support/` (router/controller) + `templates/layouts/support.html` + alag sidebar partial. HTMX pattern follow (existing `app/web/framework/htmx.py`).
- **API** (mobile app ke liye): `app/api/v1/routers/support.py` — create ticket, list my tickets, get ticket, post message, upload attachment, rate. Standard envelopes (`items/total/pages...`, `data`).
- **Realtime**: naya WebSocket endpoint + connection manager (uses `app/config/websocket.py`).
- **DI**: `configurator.py` + `dependencies.py` mein repo/handler register (AGENTS.md §3).
- **Time**: sab jagah `now_naive_ist()`.
- **Public routes**: nahi — sab authenticated.
- **Existing marketplace Enquiry** (`marketplace` module) alag cheez hai (customer enquiries) — support se mix nahi karna.

---

## 10A. UI Standard — simple, clean, ultra-professional (D-13)

Support portal ek **alag product jaisa** dikhega: kam rang, zyada spacing, saaf typography. Yeh standard har support
page par lagu hai (Phase 25.2 mein banega, baaki phases isi ko reuse karenge).

**Principles**
1. **Ek hi accent colour** (deep indigo/blue) + neutral greys. Status ke liye sirf chhote semantic chips (green / amber / red / blue / grey) — poore page ko rang nahi.
2. **Spacing 4/8 px grid**, cards par subtle 1px border + halka shadow, radius 10px. Koi gradient/heavy animation nahi.
3. **Typography**: ek hi sans-serif family (Inter ya system UI), 14px base, clear hierarchy (page title 20/600, section 14/600, meta 12/500 muted).
4. **Density**: tables comfortable-compact, sticky header, row hover, zebra nahi; ek hi primary action har page par.
5. **Har screen ke 4 states**: loading (skeleton), empty (icon + ek line + action), error (retry), success (toast).
6. **Accessibility**: keyboard navigable, visible focus ring, AA contrast, `aria-live` for live updates, icon-only buttons par tooltip + label.
7. **Responsive**: desktop primary; tablet/mobile par sidebar drawer ban jaye, tables card-list ban jayein.
8. Existing dairy sidebar/CSS se **alag**: nayi `support.css` (sab classes `sp-` prefix), nayi layout `layouts/support.html`; `app.min.css` ko chhoona nahi.

**Layout**
```
┌───────────────┬───────────────────────────────────────────────┐
│  Logo         │  Topbar: page title · search · Live● · 🔔 · 👤 │
│  Sidebar 248  ├───────────────────────────────────────────────┤
│  (grouped,    │  Content (max-width 1280, 24px padding)       │
│  permission   │                                               │
│  based, badge │  Ticket detail = 3 column:                    │
│  counts)      │  [Conversation (flex)] | [Details 320]        │
└───────────────┴───────────────────────────────────────────────┘
```

**Core components** (ek baar banenge, sab jagah reuse): Page header, Stat card, Data table (+filters bar, pagination),
Status chip, Priority dot, Avatar + presence dot, Ticket row, Chat bubble (user / staff / internal-note / system),
Timeline, Empty state, Skeleton, Toast, Confirm dialog, Form field/section, Tabs, Live-connection badge.

**Ticket detail screen**: left = conversation + composer (reply / internal note toggle, attachments, canned-ready slot);
right = requester card (name, role, phone + `Call` button, MCC/VLCC info, device + app version), ticket meta
(status, priority, category, assignee), timeline. Status/assign actions sirf permission wale ko dikhte hain.

---

## 11. Isse better banane ke suggestions

1. **SLA & auto-escalation** — priority/category ke hisaab se first-response & resolution timer; breach pe manager ko alert, auto-escalate.
2. **Auto-assignment rules** — category → team; team ke andar round-robin / least-loaded / availability-based; manual assign bhi.
3. **Availability/Shift status** — Online / Busy / Away; offline member ko auto-assign nahi.
4. **Context auto-attach** — ticket ke saath requester ka role, MCC/VLCC naam, app version, device, last sync time, recent errors — member ko user se baar-baar poochna na pade.
5. **Canned replies + knowledge base/FAQ** — common sawaal (sync fail, rate chart, printer) ka ready jawab; user ko ticket se pehle FAQ suggest.
6. **Duplicate/merge tickets** — same issue ke multiple tickets merge.
7. **CSAT rating** — resolve ke baad user 1–5 star + comment; agent-wise score.
8. **Reports** — volume, avg first response, avg resolution, SLA %, per-agent load, top categories, reopen rate. Excel export (existing Excel exchange reuse).
9. **Audit log** — kisne kya dekha/badla/call kiya (specially phone number access).
10. **Rate limit / spam control** — user ek time pe limited open tickets.
11. **Language** — user Hindi/English likhe; quick-reply templates dono mein. (Voice note attachment bhi useful — farmers ke liye typing mushkil.)
12. **Impersonation-free "view as"** — read-only dikhana ki user ko app mein kya dikh raha hai (v2, sensitive).
13. **Offline-friendly app** — ticket draft offline save, internet aane par sync.

---

## 11A. Version Scope (FINAL — user decision 2026-11-18)

Abhi sirf **Version 1** banega. Baaki versions baad mein, alag discuss karke.

### Version 1 (ABHI — in scope)
- Alag Support Portal: alag layout + alag sidebar (`/support`), login ke baad support users yahin redirect.
- Support Teams (sirf Super Admin banata hai), Team Manager.
- Members + support roles + permissions (`support.*`), manager apni team ke members banata hai.
- Ticket: user app/API se raise kare, list/detail, status flow, assign/reassign (manual), priority/category, attachments (image/PDF), timeline events.
- Internal notes (user ko nahi dikhte).
- Realtime: naya ticket / message / assignment permission-based dikhe (WebSocket).
- Chat: ticket ke andar user se chat.
- Call: click-to-call (`tel:`) + call log + outcome note.
- Manager view: team ke saare tickets/members dekhna aur manage karna, basic dashboard counts.
- **Member ka personal dashboard "My Activity"** (§9A): usne kya kiya aur kitna kiya; Manager team ke har member ka dekh sakta hai.
- **Audit log** (kisne kya kiya, phone number access).

### Version 2 (BAAD MEIN — out of scope abhi)
SLA + auto-escalation, auto-assignment rules, availability/shift status, user context auto-attach (extended),
canned replies, CSAT rating, reports + Excel export.

### Version 3 (OPTIONAL — out of scope abhi)
Voice note, FAQ/knowledge base, merge duplicate tickets, rate limit, "view as".

> Note: V1 ke data model mein V2 ke liye jagah chhodni hai (e.g. tickets mein nullable `sla_due_at`,
> members mein `availability`) taaki baad mein migration bada na ho — lekin unki logic/UI abhi nahi banegi.

---

## 12. Suggested phases (implementation order)

> **Push backend (device tokens + outbox + FCM sender) = nayi phase S3P, S3 ke baad.**
> **V1 = S1 + S2 + S3 + S3P + S4 (+ audit log).** S5 aur S6 Version 2/3 mein.

> **GSD mapping (D-14):** S1 → Phase 25 · S2 → Phase 26 · S3 → Phase 27 · S3P → Phase 28 · S4 + My Activity → Phase 29 · hardening + `SUPPORT_API.md` → Phase 30. Detailed plans: `.gsd/phases/25..30/`.

| Phase | Scope |
|---|---|
| **S1** | Foundation: `Role.SUPPORT`, tables+migration, support teams (Super Admin), members, support roles/permissions, support layout + alag sidebar + login redirect |
| **S2** | Tickets core: user API se ticket create/list/detail, support portal queue/all/my tickets, assign, status flow, timeline, internal notes, attachments |
| **S3** | Realtime + Chat: Redis + WebSocket, permission-based fanout, unread counts, live ticket chat |
| **S3P** | Push backend: device tokens, outbox, FCM sender |
| **S4** | Call: click-to-call, call logs, audit log views, My Activity dashboard |
| **S5** | Manager tools: dashboard, reports, SLA/escalation, auto-assign, canned replies, CSAT |
| **S6** | Polish: KB/FAQ, merge tickets, Excel export, availability |

Har phase ke baad Conventional Commit (project workflow), local commit only.

---

## 13. Open Questions (decide karne hain)

| # | Question | My recommendation |
|---|---|---|
| Q-1 | Support staff ka login: existing `users` table (naya role) ya bilkul alag table? | Existing `users` + `Role.SUPPORT` (ek login system, kam duplication) |
| Q-2 | Ek team ke multiple managers? | ✅ **DECIDED (D-7)**: ek team ka sirf ek Manager |
| Q-3 | Ek member multiple teams mein? | ✅ **DECIDED (D-7)**: nahi, ek hi team |
| Q-4 | Chat sirf ticket ke andar, ya bina ticket general chat bhi? | v1: ticket-based hi |
| Q-5 | Server instances / Redis? | ✅ **DECIDED (D-3)**: ek instance, Linux, Redis use hoga |
| Q-6 | Push notification (FCM)? | ✅ **DECIDED (D-4)**: abhi nahi, baad mein |
| Q-7 | Calling | ✅ **DECIDED (D-5)**: `tel:` + log |
| Q-8 | Ticket kaun raise kar sakta hai? | ✅ **DECIDED (D-9)**: MCC, VLCC, Farmer (Sub-admin nahi) |
| Q-9 | Ticket kis team ko jaye? | ✅ **DECIDED (D-8)**: category se + manager manual; team mein Ticket Assigner member |
| Q-10 | Dairy data dekhna? | ✅ **DECIDED (D-6)**: nahi; basic info + device/version hi |
| Q-11 | Languages: UI Hindi/English dono chahiye? | English UI, Hindi quick-replies |
| Q-12 | Attachments: max size/type (images, PDF, voice)? | Images + PDF + audio, 10 MB |
| Q-13 | SLA targets (first response / resolution) kitne ghante? | Priority ke hisaab se configurable |

---

## 14. Decisions log (jaise jaise final hon, yahan likhenge)

| # | Decision | Date |
|---|---|---|
| D-1 | Pehle sirf **Version 1** implement hoga (see §11A); V2/V3 baad mein | 2026-11-18 |
| D-2 | Audit log V1 mein shamil | 2026-11-18 |
| D-11 | **Live updates, no refresh**: ticket aaye ya koi update ho to support member ko turant dikhe (list, chat, badges, dashboard counts). WebSocket + Redis pub/sub, auto-reconnect + missed-event catch-up (§6) | 2026-11-18 |
| D-12 | MCC/VLCC/Farmer/VLCC_FARMER **mobile app** se hi chat aur queries denge. Backend: REST + WebSocket for mobile (§6A), `docs/SUPPORT_API.md` app developers ke liye. Push nahi, to app band hone par reply app kholne par dikhega | 2026-11-18 |
| D-13 | **UI**: support portal ka UI simple, clean aur ultra-professional (§10A): single accent colour, 4/8 spacing, alag `support.css` (`sp-` prefix) + `layouts/support.html`, har screen ke loading/empty/error/success states | 2026-11-18 |
| D-14 | **Implementation plan**: GSD Phases 25–30 (`.gsd/ROADMAP.md`, `.gsd/phases/25..30/`), Milestone v1.3.0 Technical Support. Phase mapping: S1→25, S2→26, S3→27, S3P→28, S4+My Activity→29, hardening+API doc→30 | 2026-11-18 |
| D-10 | Har support member ka personal dashboard "My Activity" V1 mein (§9A); Manager apni team ke members ka dekh sakta hai | 2026-11-18 |
| D-3 | **Deployment + Redis** (revised): production mein ek hi app instance, server **Linux**. **Redis ab implement hoga** (free, open source; Linux par `apt install redis-server`, dev Windows par WSL2/Docker). Use: WebSocket events ka pub/sub, presence (online/offline, typing), unread-count cache. Python client `redis.asyncio`. Redis down ho to app crash na kare (graceful fallback: DB unread counts + polling). Scope: V1 mein sirf support module; poore app mein use (cache, rate limit) baad mein | 2026-11-18 |
| D-9 | **Requesters**: ticket sirf **MCC, VLCC, Farmer** raise kar sakte hain (app API se). Sub-admin / Admin / Super Admin ticket raise nahi karte. `VLCC_FARMER` (Role 7) bhi Farmer ki tarah ticket raise kar sakta hai (confirmed). Allowed requester roles: MCC, VLCC, FARMER, VLCC_FARMER | 2026-11-18 |
| D-4 | **Push notification (FCM)** (revised 2026-11-18): **backend abhi V1 mein banega** (device tokens, outbox, FCM sender, presence-based skip); **mobile app side baad mein** (§6A). Originally: abhi nahi. V1 mein realtime sirf WebSocket (app khula ho tab) + unread counts DB mein, app khulne par dikhe | 2026-11-18 |
| D-5 | **Calling**: sirf phone dialer (`tel:`) + call log. Cloud telephony nahi | 2026-11-18 |
| D-6 | **Data access**: support member requester ka dairy data (collections, payments etc.) **nahi** dekh sakta. Sirf requester ki **basic info** + **device/machine details + app version** dekh sakta hai. Basic info + device/version **har support member** dekh sakta hai (koi alag permission nahi, `view_profile` permission hata di). Dairy data ka koi permission V1 mein hai hi nahi. Phone number bhi har member dekh sakta hai; sirf call karna `support.call.make` se | 2026-11-18 |
| D-7 | **Team ownership**: ek team ka **sirf ek Manager** (team ka maalik). Team ke andar multiple members alag support roles ke saath (technical, support, ticket-assigner, read-only etc.). Manager hi members banata hai. Ek member ek hi team mein | 2026-11-18 |
| D-8 | **Ticket routing**: dono tareeke. (a) **Category se** default team mein auto-route; (b) **Manager manually** assign/reassign. Team ke andar tickets baantne ke liye ek **Ticket Assigner** role ka member hota hai, jise Manager khud banata hai (Manager khud bhi baant sakta hai). Category ka koi default team na ho to ticket Super Admin ke **Unassigned pool** mein jata hai | 2026-11-18 |
