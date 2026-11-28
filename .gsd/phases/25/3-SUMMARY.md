# Plan 25.3 Summary: Teams, members and roles screens

**Status:** ✅ Complete (2026-11-18), visual sign-off by the user pending

## What was built
- Teams (Super Admin): `/support/teams` (search, pager), `/support/teams/new` (team + Manager login in one form),
  `/support/teams/{id}` (stats, manager card, members, roles), `/edit`, `/status` (confirm dialog).
- Members (Manager / `support.member.manage`; Super Admin with `?team=`): `/support/members` (search, pager, enable /
  disable, "(you)" marker, no disable for the manager or oneself), `/new`, `/{id}/edit`, `/{id}/status`.
- Roles (Manager / `support.role.manage`; Super Admin with `?team=`): `/support/roles`, `/new`, `/{id}/edit` with a
  grouped permission checklist (`support.team.manage` never offered).
- `app/web/support/forms.py`: one readable message for business, Pydantic and FastAPI validation errors; pager.
- Dairy sidebar: Super Admin gets "Technical Support" under General (→ `/support/teams`).
- POST → redirect → GET with `?notice=` banners; failed forms re-render with what was typed and status 422.

## Decided while building
- "Last sign-in" column dropped: `users.last_login` is not updated by the login handler, so it would always say Never.

## Tests
`tests/support/test_team_screens.py` — 12 tests (forms, errors kept in place, search, edit, disable, permission and
team checks, Super Admin with `?team=`, dairy sidebar entry).
