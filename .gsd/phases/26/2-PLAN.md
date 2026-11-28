---
phase: 26
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/api/v1/routers/support.py
  - app/api/v1/schemas/support.py
  - app/api/v1/router.py
  - app/modules/support/application/attachment_service.py
  - tests/support/test_support_api.py
must_haves:
  - Only MCC, VLCC, Farmer and VLCC_FARMER logins can use the requester API; others get 403
  - Create, list, detail, post message, attach file, mark read, reopen, rate-less close are available
  - Standard envelopes (single record `data`, list `items/limit/offset/total/pages/next_page/has_more`)
  - Attachments are images or PDF up to 10 MB, stored through the media service
  - A requester can reach only their own tickets (others return 404)
gap_closure: false
---

# Plan 26.2: Mobile REST API for tickets, messages and attachments

## Objective
Everything the mobile app needs to raise and follow tickets (REQ-67, REQ-70, REQ-71, DECISION-031).

## Context
- Plan 26.1; docs/TECHNICAL_SUPPORT_PLAN.md section 6A
- app/api/v1/routers/marketplace.py and profile.py for envelope, `_compute_pagination`, `request.state.user` handling

## Tasks

<task type="auto">
  <name>Endpoints and schemas</name>
  <files>routers/support.py, schemas/support.py, router.py</files>
  <action>Prefix `/api/v1/support`. `GET /categories`; `POST /tickets` (subject, description, category_id,
  device_model, os_version, app_version, `client_request_id`; returns 201 with ticket_no); `GET /tickets`
  (status filter, limit / offset); `GET /tickets/{id}` (ticket, public timeline, status labels);
  `GET /tickets/{id}/messages?after_id=&limit=`; `POST /tickets/{id}/messages` (text, `client_request_id`);
  `POST /tickets/{id}/attachments` (multipart); `POST /tickets/{id}/read` (clears unread); `POST /tickets/{id}/reopen`;
  `POST /tickets/{id}/close`. Pydantic v2 request / response models; role check helper returns 401 / 403 per AGENTS.md.
  Internal notes and internal events are filtered at handler level, never in the router.
  AVOID: exposing assignee phone or internal member ids; accepting `requester_id` from the body.</action>
  <verify>tests/support/test_support_api.py: each role (Super Admin 403, MCC / VLCC / Farmer / VLCC_FARMER 200),
  other user's ticket 404, pagination envelope, duplicate request id, oversize / wrong type attachment 422</verify>
  <done>API behaves as listed and the OpenAPI page documents it with examples.</done>
</task>

<task type="auto">
  <name>Attachments</name>
  <files>attachment_service.py</files>
  <action>Validate type (jpeg, png, webp, pdf) and size (10 MB), store with the existing media service under
  `support/{ticket_id}/`, record in `support_attachments`, return a signed or auth-checked URL (staff and the ticket's
  requester only; not under a public path).
  AVOID: adding any path to the public routes list.</action>
  <verify>test download allowed for requester and team staff, 403 / 404 for others</verify>
  <done>Files are private to the ticket's participants.</done>
</task>

## Must-Haves
- [ ] API behaviour matches section 6A of the design document

## Success Criteria
- [ ] Tests green; no regressions
