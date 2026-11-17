---
phase: 25
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/administration/domain/enums.py
  - app/modules/support/domain/entities.py
  - app/modules/support/domain/enums.py
  - app/modules/support/domain/permissions.py
  - app/modules/support/domain/exceptions.py
  - app/modules/support/domain/irepository.py
  - app/modules/support/infrastructure/models.py
  - app/modules/support/infrastructure/repository.py
  - app/modules/support/application/command.py
  - app/modules/support/application/handler.py
  - app/modules/support/application/guard.py
  - app/core/database/migrations/versions/20261118_0005_support_foundation.py
  - app/modules/configurator.py
  - app/modules/dependencies.py
  - tests/support/test_foundation.py
must_haves:
  - Role.SUPPORT = 8 exists and Roles 1 to 7 are unchanged
  - Only Super Admin can create a team; creating it creates its one Manager user
  - Manager creates members; one member, one team, one support role
  - Five role templates are seeded per team; permissions are checked on the server with team scope
  - Every create / update / disable writes an audit row
  - Works on PostgreSQL and SQLite (migration 0005)
gap_closure: false
---

# Plan 25.1: Support domain, tables, permissions and team / member handlers

## Objective
The data and rules of the support module: roles, teams, members, permissions and the audit log (REQ-58 to REQ-61,
REQ-63, REQ-64, DECISION-031). No screens yet.

## Context
- docs/TECHNICAL_SUPPORT_PLAN.md (sections 2, 3, 4)
- .gsd/STANDARDS.md, AGENTS.md; mirror the layout of `app/modules/marketplace` (domain / infrastructure / application)
- app/modules/administration (user creation handler, `Role`, hierarchy) and `app/core/clock.py`

## Tasks

<task type="auto">
  <name>Role, domain and permissions</name>
  <files>administration/domain/enums.py, support/domain/*</files>
  <action>Add `SUPPORT = 8` at the end of `Role`. Domain (no framework imports, `@dataclass(slots=True)`):
  `SupportTeam`, `SupportRole`, `SupportMember`, `AuditEntry`. `permissions.py`: `SupportPermission` StrEnum with the
  list in plan doc section 4 and `ROLE_TEMPLATES` (Technical Support, Ticket Assigner, Chat Agent, Caller, Viewer)
  mapped to permission sets. `has_permission(member, perm)` returns True for the manager. Exceptions: `TeamNotFound`,
  `MemberNotFound`, `TeamAlreadyHasManager`, `PermissionDenied`, `DuplicateTeamCode` (HTTP codes as in other modules).
  AVOID: reusing the old dairy `Permission` enum (different concern); hard-coding roles in handlers.</action>
  <verify>unit tests: template sets, manager passes every check, unknown permission rejected</verify>
  <done>Domain imports without FastAPI / SQLAlchemy; permission rules covered by tests.</done>
</task>

<task type="auto">
  <name>Tables, repository and migration 0005</name>
  <files>support/infrastructure/models.py, repository.py, migration 0005</files>
  <action>Models (Base, UUIDMixin, AuditMixin, SoftDeleteMixin where noted, `now_naive_ist`): `support_teams`
  (name, code unique, is_active, manager_user_id unique), `support_roles` (team_id, name, permissions JSON,
  is_system), `support_members` (user_id unique, team_id, role_id, is_manager, is_active),
  `support_audit_log` (actor_id, team_id, action, entity, entity_id, meta JSON, created_at; indexed team + created_at).
  Repository implements the domain interface (async, no commits inside). Migration 0005 creates tables only when
  missing and works on SQLite and PostgreSQL (follow 0004).
  AVOID: foreign keys that break soft delete; querying inside JSON columns.</action>
  <verify>`alembic upgrade head` and `downgrade -1` on SQLite and the local PostgreSQL recipe; repository tests</verify>
  <done>Tables exist on both databases and repository round-trips every entity.</done>
</task>

<task type="auto">
  <name>Handlers, guard and DI</name>
  <files>support/application/*, configurator.py, dependencies.py, tests/support/test_foundation.py</files>
  <action>`SupportTeamHandler` (`__slots__`, transactions): `create_team` (Super Admin only; creates the Manager user
  with `Role.SUPPORT` through the existing user-creation path, the team, five seeded roles, the manager member, an
  audit row, all in one transaction), `update_team`, `set_team_active`. `SupportMemberHandler`: create / update /
  disable member (manager of that team or Super Admin), `set_member_role`. `SupportRoleHandler`: list, create, edit
  permissions (not the manager). `guard.py`: `SupportContext` resolved from the current user (member, team, role,
  permissions) plus `require(perm)` used by every later handler. Register repositories and handlers in
  `ModuleConfigurator` and helpers in `dependencies.py`.
  AVOID: a second user table; letting a member edit their own role; trusting a team id from the client.</action>
  <verify>tests/support/test_foundation.py: Super Admin creates a team (manager user, five roles, audit row); Admin /
  Manager / member cannot; manager adds and disables members in own team only; second manager for a team rejected;
  guard denies a permission the role lacks; one transaction rolls back completely on a duplicate mobile</verify>
  <done>Teams, members and roles work through handlers with audit rows, on SQLite and PostgreSQL.</done>
</task>

## Must-Haves
- [ ] Role 8 added without touching 1 to 7
- [ ] Every write is in a transaction and audited
- [ ] Team scope enforced in the guard, not in screens

## Success Criteria
- [ ] Tests green on SQLite and PostgreSQL; no regressions in the existing suite