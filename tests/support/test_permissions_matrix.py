"""
Technical Support permission matrix (Plan 30.1, REQ-58 to REQ-80, DECISION-031)

Every support screen, portal action, mobile API endpoint and socket is called through the real app by
every kind of user. The expected allow / deny table is written out by hand in this file (`GRANTS`,
`sees`, the page and action tables), so a change to a role template or to a guard fails here.

- Screens: allowed = 200; denied = anything else (a redirect away, 401, 403 or 404), and no data leaks.
- Actions: judged by what changed in the database, never by the redirect alone.
- Mobile API: 401 anonymous, 403 for logins that are not requesters, 404 for someone else's ticket.
- Sockets: close code 4401 / 4403, and `not_found` for a ticket the user may not follow.

Python 3.13+
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import func, select

from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.support.application.call_handler import CallHandler
from app.modules.support.application.command import CreateRoleCommand
from app.modules.support.application.handler import SupportMemberHandler, SupportRoleHandler, SupportTeamHandler
from app.modules.support.application.ticket_command import (
    AddAttachmentCommand,
    AssignTicketCommand,
    PostMessageCommand,
)
from app.modules.support.application.ticket_handler import TicketHandler
from app.modules.support.domain.enums import TicketPriority, TicketStatus
from app.modules.support.domain.permissions import SupportPermission as P
from app.modules.support.infrastructure.models import (
    SupportAuditLogModel,
    SupportCallLogModel,
    SupportCategoryModel,
    SupportMemberModel,
    SupportRoleModel,
    SupportTeamModel,
    SupportTicketMessageModel,
    SupportTicketModel,
)
from app.api.v1.routers import support_ws
from tests.support.test_foundation import _actor, _digits, _make_member, _make_team
from tests.support.test_realtime import FakeSocket, _token
from tests.support.test_tickets import _category, _raise

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PASSWORD = "Passw0rd!x"
API = "/api/v1/support"


# =========================================================
# WHO IS WHO
# =========================================================

# Members of the team under test, by the role they hold
TEAM = ("manager", "technical_support", "ticket_assigner", "chat_agent", "caller", "viewer", "assign_only")

# Everyone who may open the portal: the team, Super Admin and the manager of another team
PORTAL = frozenset({"super_admin", *TEAM, "other_manager"})

REQUESTERS = frozenset({"mcc", "vlcc", "farmer", "vlcc_farmer"})

# Signed in, but neither support staff nor requester (and a support login without a team row)
OUTSIDERS = ("admin", "sub_admin", "no_team")

ACTORS = ("anonymous", "super_admin", *OUTSIDERS, *sorted(REQUESTERS), *TEAM, "other_manager")

_MANAGER = frozenset(P) - {P.TEAM_MANAGE}

# What each role may do, written out (not read from ROLE_TEMPLATES) so a template change is caught
GRANTS: dict[str, frozenset[P]] = {
    "super_admin": frozenset(P),
    "manager": _MANAGER,
    "other_manager": _MANAGER,
    "technical_support": frozenset({
        P.TICKET_VIEW_ASSIGNED, P.TICKET_REPLY, P.TICKET_INTERNAL_NOTE, P.TICKET_CHANGE_PRIORITY,
        P.TICKET_RESOLVE, P.TICKET_REOPEN, P.CHAT_USE, P.CALL_MAKE,
    }),
    "ticket_assigner": frozenset({P.TICKET_VIEW_ALL, P.TICKET_ASSIGN, P.TICKET_CHANGE_PRIORITY, P.TICKET_INTERNAL_NOTE}),
    "chat_agent": frozenset({P.TICKET_VIEW_ASSIGNED, P.TICKET_REPLY, P.TICKET_INTERNAL_NOTE, P.CHAT_USE}),
    "caller": frozenset({P.TICKET_VIEW_ASSIGNED, P.TICKET_INTERNAL_NOTE, P.CALL_MAKE}),
    "viewer": frozenset({P.TICKET_VIEW_ALL}),
    # A custom role: works the unassigned queue and nothing else
    "assign_only": frozenset({P.TICKET_ASSIGN}),
}


def sees(actor: str, where: str) -> bool:
    """May `actor` open a ticket of the team? `pool` = nobody assigned, `own` = assigned to the actor."""
    if actor == "super_admin":
        return True
    if actor not in TEAM:
        return False                                  # other teams, outsiders, requesters, anonymous
    grants = GRANTS[actor]
    if P.TICKET_VIEW_ALL in grants:
        return True
    if where == "own":
        return P.TICKET_VIEW_ASSIGNED in grants
    return P.TICKET_ASSIGN in grants                  # the unassigned queue is the assigner's work


# =========================================================
# THE WORLD (built once for the module)
# =========================================================

@pytest.fixture(scope="module")
async def world(api, database, user_factory, token_for):
    from app.main import app

    container = app.state.application.container
    desk = SimpleNamespace(
        database=database,
        tickets=container.resolve(TicketHandler),
        teams=container.resolve(SupportTeamHandler),
        members=container.resolve(SupportMemberHandler),
        roles=container.resolve(SupportRoleHandler),
        calls=container.resolve(CallHandler),
        admin=_actor(await user_factory(Role.SUPER_ADMIN, name="Matrix Super Admin"), Role.SUPER_ADMIN),
    )

    team, manager = await _make_team(desk)
    other_team, other_manager = await _make_team(desk)
    assign_only_role = f"Assign only {uuid4().hex[:6]}"
    await desk.roles.create_role(
        CreateRoleCommand(name=assign_only_role, permissions=[P.TICKET_ASSIGN.value], team_id=team.id), manager,
    )

    users: dict[str, UUID] = {"super_admin": desk.admin.id, "manager": manager.id, "other_manager": other_manager.id}
    roles: dict[str, Role] = {"super_admin": Role.SUPER_ADMIN}
    members: dict[str, object] = {}
    for key, role_name in (
        ("technical_support", "Technical Support"), ("ticket_assigner", "Ticket Assigner"),
        ("chat_agent", "Chat Agent"), ("caller", "Caller"), ("viewer", "Viewer"), ("assign_only", assign_only_role),
    ):
        member, actor = await _make_member(desk, manager, role_name)
        users[key], members[key] = actor.id, member
    for key in (*TEAM, "other_manager", "no_team"):
        roles[key] = Role.SUPPORT
    users["no_team"] = await user_factory(Role.SUPPORT, name="Support without a team")
    for key, role in (
        ("admin", Role.ADMIN), ("sub_admin", Role.SUB_ADMIN), ("mcc", Role.MCC), ("vlcc", Role.VLCC),
        ("farmer", Role.FARMER), ("vlcc_farmer", Role.VLCC_FARMER),
    ):
        users[key], roles[key] = await user_factory(role, name=f"Matrix {key}"), role

    headers = {key: token_for(users[key], roles[key]) for key in users}
    headers["anonymous"] = {}

    category = await _category(desk, team_id=team.id)
    category_2 = await _category(desk, team_id=team.id)
    owner = _actor(await user_factory(Role.FARMER, name="Ticket Owner"), Role.FARMER)
    stranger = _actor(await user_factory(Role.FARMER, name="Another Farmer"), Role.FARMER)

    pool = await _raise(desk, owner, category)
    mine = await _raise(desk, owner, category)
    await desk.tickets.assign(AssignTicketCommand(ticket_id=mine.id, assignee_user_id=users["technical_support"]), manager)
    _message, attachment = await desk.tickets.attach_for_requester(
        AddAttachmentCommand(ticket_id=pool.id, file_name="photo.png", content_type="image/png", data=PNG), owner,
    )
    roles_of_team = await desk.roles.list_roles(team.id, desk.admin)

    return SimpleNamespace(
        app=app, desk=desk, team=team, other_team=other_team, manager=manager, users=users, roles=roles,
        members=members, headers=headers, category=category, category_2=category_2, owner=owner,
        stranger=stranger, pool=pool, mine=mine, attachment=attachment, token_for=token_for,
        viewer_role=next(role for role in roles_of_team if role.name == "Viewer"),
    )


async def _fresh_ticket(world, *, assign_to: UUID | None = None):
    ticket = await _raise(world.desk, world.owner, world.category)
    if assign_to is not None:
        await world.desk.tickets.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=assign_to), world.manager)
    return ticket


async def _scalar(world, statement):
    async with world.desk.database.transaction() as session:
        return await session.scalar(statement)


async def _ticket_row(world, ticket_id: UUID) -> SupportTicketModel:
    async with world.desk.database.transaction() as session:
        return await session.get(SupportTicketModel, ticket_id)


# =========================================================
# SCREENS
# =========================================================

_TICKET_READERS_POOL = frozenset(actor for actor in PORTAL if sees(actor, "pool"))
_TICKET_READERS_MINE = frozenset({"super_admin", "manager", "ticket_assigner", "viewer", "technical_support"})
_MANAGERS = frozenset({"super_admin", "manager", "other_manager"})
_OWN_TEAM_MANAGERS = frozenset({"super_admin", "manager"})
_VIEW_ALL = frozenset({"super_admin", "manager", "ticket_assigner", "viewer", "other_manager"})

# (path, who gets the page); `{...}` is filled from the world
PAGES: tuple[tuple[str, frozenset[str]], ...] = (
    ("/support", PORTAL),
    ("/support/_kit", frozenset({"super_admin"})),
    ("/support/_live/counts", PORTAL),
    ("/support/teams", frozenset({"super_admin"})),
    ("/support/teams/new", frozenset({"super_admin"})),
    ("/support/teams/{team}", frozenset({"super_admin"})),
    ("/support/teams/{team}/edit", frozenset({"super_admin"})),
    ("/support/members?team={team}", _MANAGERS),
    ("/support/members/new?team={team}", _MANAGERS),
    ("/support/members/{tech_member}/edit?team={team}", _OWN_TEAM_MANAGERS),
    ("/support/roles?team={team}", _MANAGERS),
    ("/support/roles/new?team={team}", _MANAGERS),
    ("/support/roles/{viewer_role}/edit?team={team}", _OWN_TEAM_MANAGERS),
    ("/support/tickets?scope=all", _VIEW_ALL),
    ("/support/tickets?scope=unassigned", _VIEW_ALL | {"assign_only"}),
    ("/support/tickets?scope=mine", PORTAL - {"assign_only"}),
    ("/support/tickets/{pool}", _TICKET_READERS_POOL),
    ("/support/tickets/{mine}", _TICKET_READERS_MINE),
    ("/support/attachments/{attachment}", _TICKET_READERS_POOL),
    ("/support/categories", frozenset({"super_admin"})),
    ("/support/categories/new", frozenset({"super_admin"})),
    ("/support/categories/{category}/edit", frozenset({"super_admin"})),
    # Super Admin has no activity of its own: the page sends it to the team view (checked below)
    ("/support/activity", PORTAL - {"super_admin"}),
    ("/support/activity/team?team={team}", _MANAGERS),
    ("/support/audit?team={team}", _MANAGERS),
)


def _fill(world, path: str) -> str:
    return path.format(
        team=world.team.id, tech_member=world.members["technical_support"].id, viewer_role=world.viewer_role.id,
        pool=world.pool.id, mine=world.mine.id, attachment=world.attachment.id, category=world.category.id,
    )


def test_the_expected_table_is_what_the_roles_say():
    """Guards the hand-written table itself against typos."""
    assert _TICKET_READERS_POOL == {"super_admin", "manager", "ticket_assigner", "viewer", "assign_only"}
    assert {actor for actor in TEAM if sees(actor, "own")} == {
        "manager", "technical_support", "ticket_assigner", "chat_agent", "caller", "viewer",
    }
    assert set(ACTORS) == {"anonymous"} | PORTAL | REQUESTERS | set(OUTSIDERS)


@pytest.mark.parametrize("path, allowed", PAGES, ids=[path for path, _ in PAGES])
@pytest.mark.parametrize("actor", ACTORS)
async def test_screens(api, world, actor, path, allowed):
    response = await api.get(_fill(world, path), headers=world.headers[actor], follow_redirects=False)
    if actor in allowed:
        assert response.status_code == 200, (actor, response.status_code, response.headers.get("location"))
    else:
        assert response.status_code != 200, f"{actor} must not open {path}"
        if actor == "anonymous":
            assert response.headers.get("location") == "/login"


async def test_super_admin_activity_opens_the_team_view(api, world):
    response = await api.get("/support/activity", headers=world.headers["super_admin"], follow_redirects=False)
    assert response.headers.get("location") == "/support/activity/team"


async def test_another_teams_manager_sees_nothing_of_this_team(api, world):
    """The pages it may open show its own team, whatever `?team=` says."""
    headers = world.headers["other_manager"]
    tech = world.members["technical_support"]
    for path in (
        "/support/tickets?scope=all", "/support/tickets?scope=unassigned",
        f"/support/members?team={world.team.id}", f"/support/roles?team={world.team.id}",
        f"/support/activity/team?team={world.team.id}", f"/support/audit?team={world.team.id}",
    ):
        html = (await api.get(path, headers=headers, follow_redirects=False)).text
        for secret in (world.pool.ticket_no, world.mine.ticket_no, tech.email, tech.name, str(world.viewer_role.id)):
            assert secret not in html, (path, secret)


async def test_staff_files_are_private_and_never_cached(api, world):
    ok = await api.get(f"/support/attachments/{world.attachment.id}", headers=world.headers["manager"])
    assert ok.status_code == 200 and ok.content == PNG
    assert "no-store" in ok.headers["cache-control"] and ok.headers["x-content-type-options"] == "nosniff"
    unknown = await api.get(f"/support/attachments/{uuid4()}", headers=world.headers["manager"])
    assert unknown.status_code == 404


# =========================================================
# TICKET ACTIONS (judged by their effect)
# =========================================================

def _target(world, actor: str) -> UUID:
    """Who an `assign` hands the ticket to: never the current assignee."""
    return world.users["caller" if actor == "chat_agent" else "chat_agent"]


async def _did_reply(world, ticket, marker, internal=False) -> bool:
    count = await _scalar(world, select(func.count(SupportTicketMessageModel.id)).where(
        SupportTicketMessageModel.ticket_id == ticket.id,
        SupportTicketMessageModel.body == marker,
        SupportTicketMessageModel.is_internal.is_(internal),
    ))
    return bool(count)


async def _did_call(world, ticket, _marker) -> bool:
    count = await _scalar(world, select(func.count(SupportCallLogModel.id)).where(SupportCallLogModel.ticket_id == ticket.id))
    return bool(count)


# name -> (permissions, any one of which allows it; form; effect)
ACTIONS = {
    "reply": ((P.TICKET_REPLY,), lambda w, a, m: ("messages", {"mode": "reply", "body": m}),
              lambda w, t, m, a: _did_reply(w, t, m)),
    "note": ((P.TICKET_INTERNAL_NOTE,), lambda w, a, m: ("messages", {"mode": "note", "body": m}),
             lambda w, t, m, a: _did_reply(w, t, m, internal=True)),
    "assign": ((P.TICKET_ASSIGN,), lambda w, a, m: ("assign", {"assignee": str(_target(w, a))}),
               None),
    "priority": ((P.TICKET_CHANGE_PRIORITY,), lambda w, a, m: ("priority", {"priority": TicketPriority.URGENT.value}),
                 None),
    "category": ((P.TICKET_CHANGE_PRIORITY,), lambda w, a, m: ("category", {"category": str(w.category_2.id)}),
                 None),
    "escalate": ((P.TICKET_REPLY, P.TICKET_ASSIGN), lambda w, a, m: ("status", {"status": TicketStatus.ESCALATED.value}),
                 None),
    "call": ((P.CALL_MAKE,), lambda w, a, m: ("calls", None), lambda w, t, m, a: _did_call(w, t, m)),
    "route": ((P.TEAM_MANAGE,), lambda w, a, m: ("route", {"team": str(w.other_team.id)}), None),
}


async def _row_effect(world, ticket, action: str, actor: str) -> bool:
    row = await _ticket_row(world, ticket.id)
    match action:
        case "assign":
            return row.assigned_to == _target(world, actor)
        case "priority":
            return row.priority == TicketPriority.URGENT
        case "category":
            return row.category_id == world.category_2.id
        case "escalate":
            return row.status == TicketStatus.ESCALATED
        case "route":
            return row.team_id == world.other_team.id
    raise AssertionError(action)


def _allowed(actor: str, action: str, where: str) -> bool:
    permissions = ACTIONS[action][0]
    if action == "route":                         # Super Admin only, and only a ticket nobody works on
        return actor == "super_admin" and where == "pool"
    if not sees(actor, where):
        return False
    return any(permission in GRANTS[actor] for permission in permissions)


ACTION_CASES = [
    (actor, action, where)
    for action in ACTIONS
    for where in ("pool", "own")
    for actor in (ACTORS if where == "pool" else TEAM)
]


@pytest.mark.parametrize("actor, action, where", ACTION_CASES, ids=[f"{w}-{a}-{x}" for x, a, w in ACTION_CASES])
async def test_ticket_actions(api, world, actor, action, where):
    ticket = await _fresh_ticket(world, assign_to=world.users[actor] if where == "own" else None)
    marker = f"matrix {uuid4().hex}"
    path, form = ACTIONS[action][1](world, actor, marker)
    response = await api.post(
        f"/support/tickets/{ticket.id}/{path}", headers=world.headers[actor], data=form, follow_redirects=False,
    )
    check = ACTIONS[action][2]
    happened = await (check(world, ticket, marker, actor) if check else _row_effect(world, ticket, action, actor))
    expected = _allowed(actor, action, where)
    assert happened is expected, (actor, action, where, response.status_code, response.headers.get("location"))

    if action == "call" and happened:             # one open call per member: finish it for the next case
        call_id = UUID(response.json()["data"]["call_id"])
        await world.desk.calls.finish_call(
            call_id, outcome="CONNECTED", duration_s=30, note=None,
            actor=_actor(world.users[actor], world.roles[actor]),
        )


# =========================================================
# TEAM, MEMBER, ROLE AND CATEGORY ADMINISTRATION
# =========================================================

async def _admin_case(world, name: str):
    """(path, form, effect) for one administration action, on fresh rows."""
    token = uuid4().hex[:8]
    team = world.team
    match name:
        case "team.create":
            code = f"M{token}".upper()
            form = {
                "name": f"Matrix {token}", "code": code, "manager_name": "Matrix Manager",
                "manager_email": f"mx{token}@quickyee-tests.com", "manager_mobile": _digits(),
                "manager_password": PASSWORD,
            }
            return "/support/teams/new", form, lambda: _scalar(
                world, select(func.count(SupportTeamModel.id)).where(SupportTeamModel.code == code))
        case "team.disable":
            fresh, _manager = await _make_team(world.desk)
            return f"/support/teams/{fresh.id}/status", {"active": "0"}, lambda: _scalar(
                world, select(SupportTeamModel.is_active.is_(False)).where(SupportTeamModel.id == fresh.id))
        case "category.create":
            label = f"Matrix category {token}"
            form = {"name": label, "team": str(team.id), "priority": TicketPriority.MEDIUM.value}
            return "/support/categories/new", form, lambda: _scalar(
                world, select(func.count(SupportCategoryModel.id)).where(SupportCategoryModel.name == label))
        case "category.disable":
            fresh = await _category(world.desk, team_id=team.id)
            return f"/support/categories/{fresh.id}/status", {"active": "0"}, lambda: _scalar(
                world, select(SupportCategoryModel.is_active.is_(False)).where(SupportCategoryModel.id == fresh.id))
        case "member.create":
            email = f"mm{token}@quickyee-tests.com"
            form = {"name": f"Matrix {token}", "email": email, "mobile": _digits(),
                    "role_id": str(world.viewer_role.id), "password": PASSWORD}
            return f"/support/members/new?team={team.id}", form, lambda: _scalar(
                world,
                select(func.count(SupportMemberModel.id))
                .join(UserModel, UserModel.id == SupportMemberModel.user_id)
                .where(UserModel.email == email, SupportMemberModel.team_id == team.id),
            )
        case "member.disable":
            fresh, _actor_of = await _make_member(world.desk, world.manager, "Viewer")
            return f"/support/members/{fresh.id}/status?team={team.id}", {"active": "0"}, lambda: _scalar(
                world, select(SupportMemberModel.is_active.is_(False)).where(SupportMemberModel.id == fresh.id))
        case "role.create":
            label = f"Matrix role {token}"
            form = {"name": label, "permissions": [P.TICKET_VIEW_ALL.value]}
            return f"/support/roles/new?team={team.id}", form, lambda: _scalar(
                world, select(func.count(SupportRoleModel.id)).where(
                    SupportRoleModel.name == label, SupportRoleModel.team_id == team.id))
        case "role.edit":
            fresh = await world.desk.roles.create_role(
                CreateRoleCommand(name=f"Fresh {token}", permissions=[P.TICKET_VIEW_ALL.value], team_id=team.id),
                world.manager,
            )
            label = f"Renamed {token}"
            form = {"name": label, "permissions": [P.TICKET_VIEW_ALL.value]}
            return f"/support/roles/{fresh.id}/edit?team={team.id}", form, lambda: _scalar(
                world, select(SupportRoleModel.name == label).where(SupportRoleModel.id == fresh.id))
    raise AssertionError(name)


ADMIN_ACTIONS = {
    "team.create": frozenset({"super_admin"}),
    "team.disable": frozenset({"super_admin"}),
    "category.create": frozenset({"super_admin"}),
    "category.disable": frozenset({"super_admin"}),
    # In this team: another team's manager may manage only its own
    "member.create": _OWN_TEAM_MANAGERS,
    "member.disable": _OWN_TEAM_MANAGERS,
    "role.create": _OWN_TEAM_MANAGERS,
    "role.edit": _OWN_TEAM_MANAGERS,
}


@pytest.mark.parametrize("name", ADMIN_ACTIONS)
@pytest.mark.parametrize("actor", ACTORS)
async def test_administration(api, world, actor, name):
    path, form, effect = await _admin_case(world, name)
    response = await api.post(path, headers=world.headers[actor], data=form, follow_redirects=False)
    happened = bool(await effect())
    assert happened is (actor in ADMIN_ACTIONS[name]), (actor, name, response.status_code, response.headers.get("location"))


async def test_a_manager_cannot_hand_out_the_super_admin_permission(api, world):
    label = f"Sneaky {uuid4().hex[:6]}"
    form = {"name": label, "permissions": [P.TICKET_VIEW_ALL.value, P.TEAM_MANAGE.value]}
    await api.post("/support/roles/new", headers=world.headers["manager"], data=form, follow_redirects=False)
    async with world.desk.database.transaction() as session:
        role = await session.scalar(select(SupportRoleModel).where(SupportRoleModel.name == label))
    if role is not None:                          # refused outright, or saved without it
        assert P.TEAM_MANAGE.value not in role.permissions


# =========================================================
# MOBILE API
# =========================================================

def _ticket_payload(world) -> dict:
    return {
        "subject": "Matrix ticket", "description": "Raised by the permission matrix.",
        "category_id": str(world.category.id), "device_model": "Redmi 9", "os_version": "Android 13",
        "app_version": "2.4.1",
    }


def _api_calls(world, ticket_id: UUID, attachment_id: UUID):
    """(name, method, path, keyword arguments) for every requester endpoint."""
    return (
        ("categories", "GET", "/categories", {}),
        ("list", "GET", "/tickets", {}),
        ("create", "POST", "/tickets", {"json": _ticket_payload(world)}),
        ("detail", "GET", f"/tickets/{ticket_id}", {}),
        ("read", "POST", f"/tickets/{ticket_id}/read", {}),
        ("messages", "GET", f"/tickets/{ticket_id}/messages", {}),
        ("send", "POST", f"/tickets/{ticket_id}/messages", {"json": {"body": "Hello from the matrix"}}),
        ("attach", "POST", f"/tickets/{ticket_id}/attachments", {"files": {"file": ("p.png", PNG, "image/png")}}),
        ("download", "GET", f"/attachments/{attachment_id}", {}),
        ("close", "POST", f"/tickets/{ticket_id}/close", {}),
        ("reopen", "POST", f"/tickets/{ticket_id}/reopen", {}),
    )


_PER_TICKET = {"detail", "read", "messages", "send", "attach", "download", "close", "reopen"}
_NON_REQUESTERS = ("anonymous", "super_admin", *OUTSIDERS, *TEAM, "other_manager")


def _expected_for_non_requester(actor: str, name: str) -> int:
    if actor == "anonymous":
        return 401
    # The file link is shared with the staff who may see the ticket (REQ-71); same rule as the portal
    if name == "download" and actor in PORTAL:
        return 200 if sees(actor, "pool") else 404
    return 403


@pytest.mark.parametrize("actor", _NON_REQUESTERS)
async def test_the_mobile_api_is_only_for_requesters(api, world, actor):
    for name, method, path, kwargs in _api_calls(world, world.pool.id, world.attachment.id):
        response = await api.request(method, f"{API}{path}", headers=world.headers[actor], **kwargs)
        expected = _expected_for_non_requester(actor, name)
        assert response.status_code == expected, (actor, name, response.status_code, response.text[:200])


async def test_someone_elses_ticket_looks_missing(api, world):
    headers = world.token_for(world.stranger.id, Role.FARMER)
    for name, method, path, kwargs in _api_calls(world, world.pool.id, world.attachment.id):
        if name not in _PER_TICKET:
            continue
        response = await api.request(method, f"{API}{path}", headers=headers, **kwargs)
        assert response.status_code == 404, (name, response.status_code)
    assert (await _ticket_row(world, world.pool.id)).status != TicketStatus.CLOSED


@pytest.mark.parametrize("actor", sorted(REQUESTERS))
async def test_every_requester_role_uses_its_own_tickets(api, world, actor):
    headers = world.headers[actor]
    created = await api.post(f"{API}/tickets", headers=headers, json=_ticket_payload(world))
    assert created.status_code == 201, created.text
    ticket_id = UUID(created.json()["data"]["id"])
    uploaded = await api.post(
        f"{API}/tickets/{ticket_id}/attachments", headers=headers, files={"file": ("p.png", PNG, "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = UUID(uploaded.json()["data"]["attachment"]["id"])

    for name, method, path, kwargs in _api_calls(world, ticket_id, attachment_id):
        response = await api.request(method, f"{API}{path}", headers=headers, **kwargs)
        assert 200 <= response.status_code < 300, (actor, name, response.status_code, response.text[:200])
        if name == "list":
            assert str(ticket_id) in response.text


async def test_a_requester_never_gets_an_internal_file(api, world):
    ticket = await _fresh_ticket(world)
    _message, internal = await world.desk.tickets.attach_for_staff(
        AddAttachmentCommand(ticket_id=ticket.id, file_name="note.png", content_type="image/png", data=PNG, internal=True),
        world.manager,
    )
    _message, public = await world.desk.tickets.attach_for_staff(
        AddAttachmentCommand(ticket_id=ticket.id, file_name="reply.png", content_type="image/png", data=PNG),
        world.manager,
    )
    headers = world.token_for(world.owner.id, Role.FARMER)
    assert (await api.get(f"{API}/attachments/{internal.id}", headers=headers)).status_code == 404
    download = await api.get(f"{API}/attachments/{public.id}", headers=headers)
    assert download.status_code == 200 and "no-store" in download.headers["cache-control"]

    detail = (await api.get(f"{API}/tickets/{ticket.id}", headers=headers)).text
    assert "note.png" not in detail and str(internal.id) not in detail


@pytest.mark.parametrize("case", ["too_big", "wrong_type", "long_message", "long_subject"])
async def test_size_and_type_limits(api, world, case):
    headers = world.token_for(world.owner.id, Role.FARMER)
    ticket = world.pool
    match case:
        case "too_big":
            response = await api.post(
                f"{API}/tickets/{ticket.id}/attachments", headers=headers,
                files={"file": ("big.png", PNG + b"\x00" * (10 * 1024 * 1024), "image/png")},
            )
        case "wrong_type":
            response = await api.post(
                f"{API}/tickets/{ticket.id}/attachments", headers=headers,
                files={"file": ("run.exe", b"MZ" + b"\x00" * 64, "application/octet-stream")},
            )
        case "long_message":
            response = await api.post(f"{API}/tickets/{ticket.id}/messages", headers=headers, json={"body": "x" * 4001})
        case "long_subject":
            response = await api.post(
                f"{API}/tickets", headers=headers, json={**_ticket_payload(world), "subject": "x" * 500},
            )
    assert response.status_code == 422, (case, response.status_code, response.text[:200])


@pytest.mark.parametrize("actor, expected", [("anonymous", 401), ("manager", 403), ("farmer", 200)])
async def test_push_device_registration(api, world, actor, expected):
    token = f"matrix-{uuid4().hex}-{uuid4().hex}"
    response = await api.post(
        "/api/v1/notifications/devices", headers=world.headers[actor],
        json={"fcm_token": token, "platform": "android", "app_version": "2.4.1"},
    )
    assert response.status_code == expected, response.text[:200]
    if expected == 200:
        assert (await api.delete(f"/api/v1/notifications/devices/{token}", headers=world.headers[actor])).status_code == 200


# =========================================================
# NOTHING IS PUBLIC
# =========================================================

def _support_routes():
    """Every route of the three support routers, with the prefix the app mounts them under.

    Read from the routers themselves: FastAPI 0.141 keeps included routers behind a wrapper in `app.routes`.
    """
    from app.api.v1.routers.notifications import router as notifications
    from app.api.v1.routers.support import router as support_api
    from app.web.support.router import router as support_web

    for prefix, router in (("", support_web), ("/api/v1", support_api), ("/api/v1", notifications)):
        for route in router.routes:
            if isinstance(route, APIRoute):
                for method in route.methods - {"HEAD", "OPTIONS"}:
                    yield method, prefix + route.path


async def test_no_support_path_is_public(api, world):
    routes = sorted(set(_support_routes()))
    assert len(routes) >= 45                      # every screen, action and endpoint, not a filtered few
    for method, path in routes:
        concrete = path
        for name in ("team_id", "member_id", "role_id", "ticket_id", "category_id", "attachment_id", "call_id"):
            concrete = concrete.replace("{" + name + "}", str(uuid4()))
        concrete = concrete.replace("{fcm_token}", "x" * 30)
        response = await api.request(method, concrete, follow_redirects=False)
        if path.startswith("/api/"):
            assert response.status_code == 401, (method, path, response.status_code)
        else:
            assert response.status_code in (302, 303, 307) and response.headers["location"] == "/login", (method, path)


# =========================================================
# SOCKETS
# =========================================================

async def _socket(world, actor: str, kind: str) -> FakeSocket:
    socket = FakeSocket(world.app).start(kind)
    token = _token(world.headers[actor]) if world.headers[actor] else "not-a-token"
    socket.say({"type": "auth", "token": token})
    return socket


async def _outcome(socket: FakeSocket) -> int | str:
    """`hello`, or the close code."""
    done, _pending = await asyncio.wait({socket.task, asyncio.ensure_future(socket.hear_type("hello", 3))},
                                        return_when=asyncio.FIRST_COMPLETED, timeout=4)
    for task in done:
        if task is not socket.task and not task.exception():
            return "hello"
    if not socket.task.done():
        await asyncio.wait_for(socket.task, 3)
    return socket.close_code


@pytest.mark.parametrize("kind", ["staff", "app"])
@pytest.mark.parametrize("actor", ACTORS)
async def test_socket_handshake(world, actor, kind):
    socket = await _socket(world, actor, kind)
    try:
        outcome = await _outcome(socket)
    finally:
        await socket.stop()
    allowed = PORTAL if kind == "staff" else REQUESTERS
    if actor in allowed:
        assert outcome == "hello", (actor, kind, outcome)
    elif actor == "anonymous":
        assert outcome == support_ws.UNAUTHORIZED
    else:
        assert outcome == support_ws.FORBIDDEN, (actor, kind, outcome)


async def _follows(socket: FakeSocket, ticket_id: UUID) -> bool:
    """Sends `read` then `ping`; False if the server answered `not_found` before the pong."""
    socket.say({"type": "read", "ticket_id": str(ticket_id)})
    socket.say({"type": "ping"})
    while True:
        message = await socket.hear(3)
        if message["type"] == "error" and message.get("ticket_id") == str(ticket_id):
            return False
        if message["type"] == "pong":
            return True


@pytest.mark.parametrize("actor, ticket, follows", [
    ("owner", "pool", True),
    ("stranger", "pool", False),
    ("technical_support", "mine", True),
    ("technical_support", "pool", False),
    ("chat_agent", "mine", False),
    ("viewer", "pool", True),
    ("assign_only", "pool", True),
    ("assign_only", "mine", False),
    ("other_manager", "pool", False),
    ("super_admin", "mine", True),
])
async def test_socket_messages_only_reach_tickets_the_user_may_follow(world, actor, ticket, follows):
    if actor in ("owner", "stranger"):
        person = getattr(world, actor)
        socket = FakeSocket(world.app).start("app")
        socket.say({"type": "auth", "token": _token(world.token_for(person.id, Role.FARMER))})
    else:
        socket = await _socket(world, actor, "staff")
    try:
        await socket.hear_type("hello", 3)
        assert await _follows(socket, getattr(world, ticket).id) is follows
    finally:
        await socket.stop()


async def test_internal_notes_and_note_typing_never_reach_the_requester(world):
    ticket = await _fresh_ticket(world)
    socket = FakeSocket(world.app).start("app")
    socket.say({"type": "auth", "token": _token(world.token_for(world.owner.id, Role.FARMER))})
    staff = await _socket(world, "manager", "staff")
    try:
        await socket.hear_type("hello", 3)
        await staff.hear_type("hello", 3)
        await socket.heard(0.3)                            # drop anything queued before this test

        marker = f"secret {uuid4().hex}"
        await world.desk.tickets.post_staff_message(
            PostMessageCommand(ticket_id=ticket.id, body=marker, internal=True), world.manager,
        )
        staff.say({"type": "typing", "ticket_id": str(ticket.id), "note": True})
        quiet = [item for item in await socket.heard(0.6) if item.get("type") != "pong"]
        assert all(str(ticket.id) not in json.dumps(item) for item in quiet), quiet
        assert marker not in json.dumps(quiet)

        await world.desk.tickets.post_staff_message(
            PostMessageCommand(ticket_id=ticket.id, body="A public reply", internal=False), world.manager,
        )
        heard = await socket.hear_type("event", 3)
        assert str(ticket.id) in json.dumps(heard) and marker not in json.dumps(heard)
    finally:
        await socket.stop()
        await staff.stop()


# =========================================================
# AUDIT AND LOGS
# =========================================================

class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record):
        text = record.getMessage()
        if record.exc_info:
            text += logging.Formatter().formatException(record.exc_info)
        self.lines.append(text)


@contextmanager
def _captured_logs():
    """Every record from every logger, also those that do not propagate to the root."""
    handler = _Capture()
    loggers = [logging.getLogger()] + [
        item for item in logging.Logger.manager.loggerDict.values() if isinstance(item, logging.Logger)
    ]
    for logger in loggers:
        logger.addHandler(handler)
    try:
        yield handler
    finally:
        for logger in loggers:
            logger.removeHandler(handler)


async def test_sensitive_actions_are_audited_and_logs_hold_no_phone_or_token(api, world):
    tech = "technical_support"
    ticket = await _fresh_ticket(world, assign_to=world.users[tech])
    async with world.desk.database.transaction() as session:
        mobile = await session.scalar(select(UserModel.mobile).where(UserModel.id == world.owner.id))
    token = _token(world.headers[tech])

    with _captured_logs() as logs:
        assert (await api.get(f"/support/tickets/{ticket.id}", headers=world.headers[tech])).status_code == 200
        started = await api.post(f"/support/tickets/{ticket.id}/calls", headers=world.headers[tech])
        assert started.status_code == 200 and started.json()["data"]["tel"].endswith(mobile[-10:])
        finished = await api.post(
            f"/support/calls/{started.json()['data']['call_id']}/finish", headers=world.headers[tech],
            data={"outcome": "CONNECTED", "minutes": "2", "note": "Explained the sync settings", "ticket_id": str(ticket.id)},
            follow_redirects=False,
        )
        assert finished.status_code in (302, 303)
        socket = await _socket(world, tech, "staff")
        await socket.hear_type("hello", 3)
        await socket.stop()
        bad = FakeSocket(world.app).start("staff")
        bad.say({"type": "auth", "token": token[:-4] + "abcd"})
        await asyncio.wait_for(bad.task, 3)

    text = "\n".join(logs.lines)
    assert mobile not in text and mobile[-10:] not in text
    assert token not in text and token[:40] not in text

    async with world.desk.database.transaction() as session:
        actions = set(await session.scalars(
            select(SupportAuditLogModel.action).where(SupportAuditLogModel.entity_id == str(ticket.id))
        ))
    assert {"ticket.assigned", "ticket.phone_viewed", "call.started", "call.logged"} <= actions, actions

    async with world.desk.database.transaction() as session:
        team_actions = set(await session.scalars(
            select(SupportAuditLogModel.action).where(SupportAuditLogModel.team_id == world.team.id)
        ))
    assert {"member.created", "role.created"} <= team_actions, team_actions
