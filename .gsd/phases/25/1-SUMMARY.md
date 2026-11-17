# Plan 25.1 Summary: Support domain, tables, permissions and team / member handlers

**Status:** ✅ Complete (2026-11-18)

## What was built
- `Role.SUPPORT = 8` added after VLCC_FARMER (1 to 7 unchanged).
- New module `app/modules/support/` (domain / infrastructure / application):
  - `domain/permissions.py`: `SupportPermission` (16 `support.*` strings), `ROLE_TEMPLATES` (Technical Support,
    Ticket Assigner, Chat Agent, Caller, Viewer), `PERMISSION_GROUPS` (labels for the role editor), `has_permission`.
    `support.team.manage` is Super Admin only and can never be given to a team role.
  - `domain/entities.py`, `enums.py` (`AuditAction`), `exceptions.py`, `irepository.py`.
  - `infrastructure/models.py`: `support_teams`, `support_roles`, `support_members`, `support_audit_log`.
  - `infrastructure/repository.py`: `SupportRepository` (staff name / mobile / e-mail joined from `users`).
  - `application/guard.py`: `SupportGuard.resolve(user)` → `SupportContext` (Super Admin, or an active member of an
    active team; everyone else `SupportAccessDeniedException`), `require`, `team_scope`, `can_access_team`.
  - `application/handler.py`: `SupportTeamHandler`, `SupportMemberHandler`, `SupportRoleHandler`. One transaction per
    use case, audit row in the same transaction. Staff logins are created through the existing `UserHandler.create`.
- Migration `0005` (`20261118_0005_support_foundation.py`): the four tables, and on PostgreSQL
  `ALTER TYPE role ADD VALUE IF NOT EXISTS 'SUPPORT'` (inside the migrator's single transaction; PostgreSQL 12+).
- DI: `SupportRepository` and the three handlers in `ModuleConfigurator`; `GetHandler.support_*_handler`.

## Rules worth remembering
- A team has exactly one Manager (`support_teams.manager_user_id` unique, member row `is_manager`, no role).
- A Manager holds every team permission; it cannot be re-roled or disabled from the members screen (only by
  disabling the team). Nobody can change their own role or disable themselves.
- Another team's member / role answers 404, not 403.
- Disabling a member also sets `users.is_active = false` (sign-in stops); a disabled team blocks all its members in the guard.

## Tests
`tests/support/test_foundation.py` — 26 tests (rules without DB, teams, members, roles, audit, rollback of a failed
create, cross-team isolation).
