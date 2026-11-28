"""
Technical Support foundation (Plan 25.1, REQ-58 to REQ-61, REQ-63, REQ-64, DECISION-031).

Teams, members, roles and permissions through the real handlers against the session database.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.support.application.command import (
    CreateMemberCommand,
    CreateRoleCommand,
    CreateTeamCommand,
    ListMembersQuery,
    ListTeamsQuery,
    SetMemberActiveCommand,
    SetTeamActiveCommand,
    UpdateMemberCommand,
    UpdateRoleCommand,
)
from app.modules.support.domain.exceptions import (
    ManagerNotEditableException,
    MemberNotFoundException,
    RoleNotFoundException,
    SupportAccessDeniedException,
    SupportPermissionDeniedException,
    SupportValidationException,
    TeamCodeAlreadyExistsException,
)
from app.modules.support.domain.permissions import (
    ALL_PERMISSIONS,
    ROLE_TEMPLATES,
    SUPER_ADMIN_ONLY,
    SupportPermission,
    has_permission,
    valid_permissions,
)
from app.modules.support.infrastructure.models import (
    SupportAuditLogModel,
    SupportMemberModel,
    SupportRoleModel,
    SupportTeamModel,
)


# =========================================================
# HELPERS
# =========================================================

def _digits() -> str:
    return f"9{str(uuid4().int)[-9:]}"


def _actor(user_id: UUID, role: Role) -> CurrentUser:
    return CurrentUser(id=user_id, role=str(int(role)))


SUPER_ADMIN = _actor(uuid4(), Role.SUPER_ADMIN)


@pytest.fixture
async def support(api, database):
    from app.main import app
    from app.modules.support.application.handler import (
        SupportMemberHandler,
        SupportRoleHandler,
        SupportTeamHandler,
    )

    container = app.state.application.container
    return SimpleNamespace(
        database=database,
        teams=container.resolve(SupportTeamHandler),
        members=container.resolve(SupportMemberHandler),
        roles=container.resolve(SupportRoleHandler),
    )


def _team_command(**overrides) -> CreateTeamCommand:
    token = uuid4().hex[:8]
    values = dict(
        name=f"Team {token}",
        code=f"T{token}".upper(),
        manager_name="Team Manager",
        manager_email=f"mgr{token}@quickyee-tests.com",
        manager_mobile=_digits(),
        manager_password="Passw0rd!x",
    )
    values.update(overrides)
    return CreateTeamCommand(**values)


async def _make_team(support, **overrides):
    team = await support.teams.create_team(_team_command(**overrides), SUPER_ADMIN)
    return team, _actor(team.manager_user_id, Role.SUPPORT)


async def _role_id(support, manager: CurrentUser, name: str) -> UUID:
    roles = await support.roles.list_roles(None, manager)
    return next(role.id for role in roles if role.name == name)


async def _make_member(support, manager: CurrentUser, role_name: str = "Technical Support"):
    token = uuid4().hex[:8]
    member = await support.members.create_member(
        CreateMemberCommand(
            role_id=await _role_id(support, manager, role_name),
            name=f"Member {token}",
            email=f"m{token}@quickyee-tests.com",
            mobile=_digits(),
            password="Passw0rd!x",
        ),
        manager,
    )
    return member, _actor(member.user_id, Role.SUPPORT)


# =========================================================
# ROLE AND PERMISSION RULES (no database)
# =========================================================

def test_support_role_is_added_without_touching_the_others():
    assert [(role.name, int(role)) for role in Role][:7] == [
        ("SUPER_ADMIN", 1), ("ADMIN", 2), ("SUB_ADMIN", 3), ("MCC", 4),
        ("VLCC", 5), ("FARMER", 6), ("VLCC_FARMER", 7),
    ]
    assert Role.SUPPORT == 8


def test_five_templates_and_none_carries_a_super_admin_permission():
    assert list(ROLE_TEMPLATES) == ["Technical Support", "Ticket Assigner", "Chat Agent", "Caller", "Viewer"]
    for permissions in ROLE_TEMPLATES.values():
        assert not permissions & SUPER_ADMIN_ONLY
    assert ROLE_TEMPLATES["Viewer"] == {SupportPermission.TICKET_VIEW_ALL}
    assert SupportPermission.TICKET_ASSIGN in ROLE_TEMPLATES["Ticket Assigner"]
    assert SupportPermission.TICKET_ASSIGN not in ROLE_TEMPLATES["Technical Support"]


def test_permission_rule_manager_and_super_admin():
    empty = frozenset()
    assert has_permission(empty, SupportPermission.TICKET_REPLY, is_manager=True)
    assert not has_permission(empty, SupportPermission.TEAM_MANAGE, is_manager=True)
    assert has_permission(empty, SupportPermission.TEAM_MANAGE, is_super_admin=True)
    assert not has_permission(empty, SupportPermission.TICKET_REPLY)
    assert has_permission(frozenset({SupportPermission.TICKET_REPLY}), SupportPermission.TICKET_REPLY)


def test_unknown_stored_permissions_are_dropped():
    assert valid_permissions(["support.ticket.reply", "nope", "support.call.make"]) == {
        SupportPermission.TICKET_REPLY, SupportPermission.CALL_MAKE,
    }
    assert ALL_PERMISSIONS == set(SupportPermission)


# =========================================================
# TEAMS
# =========================================================

async def test_super_admin_creates_a_team_with_manager_roles_and_audit(support):
    team, manager = await _make_team(support)

    assert team.is_active and team.member_count == 1 and team.manager_name == "Team Manager"
    async with support.database.transaction() as session:
        user = await session.get(UserModel, team.manager_user_id)
        assert user.role == Role.SUPPORT and user.is_active
        roles = (await session.scalars(select(SupportRoleModel).where(SupportRoleModel.team_id == team.id))).all()
        assert sorted(role.name for role in roles) == sorted(ROLE_TEMPLATES)
        assert all(role.is_system for role in roles)
        member = await session.scalar(select(SupportMemberModel).where(SupportMemberModel.team_id == team.id))
        assert member.is_manager and member.role_id is None and member.user_id == team.manager_user_id
        audit = await session.scalar(
            select(SupportAuditLogModel).where(
                SupportAuditLogModel.team_id == team.id, SupportAuditLogModel.action == "team.created",
            )
        )
        assert audit is not None and audit.actor_id == SUPER_ADMIN.id


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUB_ADMIN, Role.MCC, Role.VLCC, Role.FARMER])
async def test_only_super_admin_can_create_a_team(support, role):
    with pytest.raises(SupportAccessDeniedException):
        await support.teams.create_team(_team_command(), _actor(uuid4(), role))


async def test_a_manager_cannot_create_or_list_teams(support):
    _, manager = await _make_team(support)
    with pytest.raises(SupportPermissionDeniedException):
        await support.teams.create_team(_team_command(), manager)
    with pytest.raises(SupportPermissionDeniedException):
        await support.teams.list_teams(ListTeamsQuery(), manager)


async def test_duplicate_code_is_rejected_and_a_failed_create_leaves_nothing_behind(support):
    first, _ = await _make_team(support)
    with pytest.raises(TeamCodeAlreadyExistsException):
        await support.teams.create_team(_team_command(code=first.code.lower()), SUPER_ADMIN)

    clash = _digits()
    await _make_team(support, manager_mobile=clash)
    code = f"X{uuid4().hex[:6]}".upper()
    email = f"lost{uuid4().hex[:6]}@quickyee-tests.com"
    with pytest.raises(Exception):
        await support.teams.create_team(_team_command(code=code, manager_email=email, manager_mobile=clash), SUPER_ADMIN)
    async with support.database.transaction() as session:
        assert await session.scalar(select(func.count(SupportTeamModel.id)).where(SupportTeamModel.code == code)) == 0
        assert await session.scalar(select(func.count(UserModel.id)).where(UserModel.email == email)) == 0


async def test_invalid_team_input_is_refused(support):
    with pytest.raises(SupportValidationException):
        await support.teams.create_team(_team_command(code="a b"), SUPER_ADMIN)
    with pytest.raises(SupportValidationException):
        await support.teams.create_team(_team_command(name=" "), SUPER_ADMIN)


async def test_disabled_team_loses_portal_access(support):
    team, manager = await _make_team(support)
    member, member_actor = await _make_member(support, manager)

    await support.teams.set_active(SetTeamActiveCommand(team_id=team.id, is_active=False), SUPER_ADMIN)
    for actor in (manager, member_actor):
        with pytest.raises(SupportAccessDeniedException):
            await support.members.list_members(ListMembersQuery(), actor)

    await support.teams.set_active(SetTeamActiveCommand(team_id=team.id, is_active=True), SUPER_ADMIN)
    members, total = await support.members.list_members(ListMembersQuery(), manager)
    assert total == 2 and members[0].is_manager


# =========================================================
# MEMBERS
# =========================================================

async def test_manager_creates_members_in_its_own_team_only(support):
    team, manager = await _make_team(support)
    other_team, other_manager = await _make_team(support)

    member, _ = await _make_member(support, manager, "Ticket Assigner")
    assert member.team_id == team.id and member.role_name == "Ticket Assigner" and not member.is_manager
    assert SupportPermission.TICKET_ASSIGN in member.permissions

    # A role of another team is refused, and naming another team is ignored for a manager
    foreign_role = await _role_id(support, other_manager, "Viewer")
    with pytest.raises(RoleNotFoundException):
        await support.members.create_member(
            CreateMemberCommand(
                role_id=foreign_role, name="Wrong Team", email=f"w{uuid4().hex[:6]}@quickyee-tests.com",
                mobile=_digits(), password="Passw0rd!x",
            ),
            manager,
        )
    with pytest.raises(Exception) as caught:
        await support.members.create_member(
            CreateMemberCommand(
                role_id=await _role_id(support, manager, "Viewer"), name="Wrong Team", team_id=other_team.id,
                email=f"w{uuid4().hex[:6]}@quickyee-tests.com", mobile=_digits(), password="Passw0rd!x",
            ),
            manager,
        )
    assert caught.value.status_code == 404

    # Another team's manager cannot see or change this member
    with pytest.raises(MemberNotFoundException):
        await support.members.get_member(member.id, other_manager)
    with pytest.raises(MemberNotFoundException):
        await support.members.update_member(UpdateMemberCommand(member_id=member.id, name="Hijacked"), other_manager)


async def test_member_without_the_permission_cannot_manage_members_or_roles(support):
    _, manager = await _make_team(support)
    _, tech = await _make_member(support, manager, "Technical Support")
    with pytest.raises(SupportPermissionDeniedException):
        await support.members.list_members(ListMembersQuery(), tech)
    with pytest.raises(SupportPermissionDeniedException):
        await support.roles.list_roles(None, tech)
    with pytest.raises(SupportPermissionDeniedException):
        await support.roles.create_role(CreateRoleCommand(name="Sneaky", permissions=[]), tech)


async def test_non_support_users_are_refused_everywhere(support):
    for role in (Role.ADMIN, Role.MCC, Role.FARMER):
        with pytest.raises(SupportAccessDeniedException):
            await support.members.list_members(ListMembersQuery(), _actor(uuid4(), role))
    with pytest.raises(SupportAccessDeniedException):
        await support.members.list_members(ListMembersQuery(), None)


async def test_a_support_user_without_a_member_row_is_refused(support, user_factory):
    user_id = await user_factory(Role.SUPPORT)
    with pytest.raises(SupportAccessDeniedException):
        await support.members.list_members(ListMembersQuery(), _actor(user_id, Role.SUPPORT))


async def test_disabling_a_member_switches_the_login_off_and_back_on(support):
    _, manager = await _make_team(support)
    member, member_actor = await _make_member(support, manager)

    await support.members.set_active(SetMemberActiveCommand(member_id=member.id, is_active=False), manager)
    async with support.database.transaction() as session:
        assert (await session.get(UserModel, member.user_id)).is_active is False
    with pytest.raises(SupportAccessDeniedException):
        await support.roles.list_roles(None, member_actor)

    restored = await support.members.set_active(SetMemberActiveCommand(member_id=member.id, is_active=True), manager)
    assert restored.is_active
    async with support.database.transaction() as session:
        assert (await session.get(UserModel, member.user_id)).is_active is True


async def test_the_manager_and_oneself_cannot_be_disabled_or_re_roled(support):
    team, manager = await _make_team(support)
    members, _ = await support.members.list_members(ListMembersQuery(), manager)
    manager_member = members[0]
    assert manager_member.is_manager

    with pytest.raises(ManagerNotEditableException):
        await support.members.set_active(SetMemberActiveCommand(member_id=manager_member.id, is_active=False), manager)
    with pytest.raises(ManagerNotEditableException):
        await support.members.update_member(
            UpdateMemberCommand(member_id=manager_member.id, role_id=await _role_id(support, manager, "Viewer")),
            manager,
        )

    # A member holding member.manage cannot change their own role
    admin_role = await support.roles.create_role(
        CreateRoleCommand(name="People Admin", permissions=[SupportPermission.MEMBER_MANAGE.value]), manager,
    )
    token = uuid4().hex[:8]
    people = await support.members.create_member(
        CreateMemberCommand(
            role_id=admin_role.id, name="People Admin", email=f"p{token}@quickyee-tests.com",
            mobile=_digits(), password="Passw0rd!x",
        ),
        manager,
    )
    people_actor = _actor(people.user_id, Role.SUPPORT)
    with pytest.raises(SupportPermissionDeniedException):
        await support.members.update_member(
            UpdateMemberCommand(member_id=people.id, role_id=await _role_id(support, manager, "Viewer")), people_actor,
        )
    with pytest.raises(SupportValidationException):
        await support.members.set_active(SetMemberActiveCommand(member_id=people.id, is_active=False), people_actor)


async def test_member_update_changes_name_mobile_and_role_with_audit(support):
    team, manager = await _make_team(support)
    member, _ = await _make_member(support, manager, "Technical Support")
    new_mobile = _digits()

    updated = await support.members.update_member(
        UpdateMemberCommand(
            member_id=member.id, name="Renamed Member", mobile=new_mobile,
            role_id=await _role_id(support, manager, "Caller"),
        ),
        manager,
    )
    assert updated.name == "Renamed Member" and updated.mobile == new_mobile and updated.role_name == "Caller"
    async with support.database.transaction() as session:
        actions = set(
            (await session.scalars(select(SupportAuditLogModel.action).where(SupportAuditLogModel.team_id == team.id))).all()
        )
    assert {"member.created", "member.updated", "member.role_changed"} <= actions

    # A mobile that belongs to someone else is refused
    other, _ = await _make_member(support, manager)
    with pytest.raises(SupportValidationException):
        await support.members.update_member(UpdateMemberCommand(member_id=other.id, mobile=new_mobile), manager)


# =========================================================
# ROLES AND PERMISSIONS
# =========================================================

async def test_manager_edits_role_permissions_and_the_guard_follows(support):
    _, manager = await _make_team(support)
    viewer, viewer_actor = await _make_member(support, manager, "Viewer")
    with pytest.raises(SupportPermissionDeniedException):
        await support.members.list_members(ListMembersQuery(), viewer_actor)

    await support.roles.update_role(
        UpdateRoleCommand(role_id=viewer.role_id, permissions=[SupportPermission.MEMBER_MANAGE.value]), manager,
    )
    members, total = await support.members.list_members(ListMembersQuery(), viewer_actor)
    assert total == 2


async def test_a_member_who_manages_roles_cannot_raise_their_own_access(support):
    """`support.role.manage` without being the Manager: no editing one's own role, no granting more than held."""
    _, manager = await _make_team(support)
    lead_permissions = [SupportPermission.ROLE_MANAGE.value, SupportPermission.TICKET_VIEW_ALL.value]
    await support.roles.create_role(CreateRoleCommand(name="Lead", permissions=lead_permissions), manager)
    lead, lead_actor = await _make_member(support, manager, "Lead")

    with pytest.raises(SupportPermissionDeniedException):
        await support.roles.update_role(
            UpdateRoleCommand(role_id=lead.role_id, permissions=[*lead_permissions, SupportPermission.MEMBER_MANAGE.value]),
            lead_actor,
        )
    with pytest.raises(SupportPermissionDeniedException):
        await support.roles.update_role(UpdateRoleCommand(role_id=lead.role_id, name="Renamed"), lead_actor)
    with pytest.raises(SupportPermissionDeniedException):
        await support.roles.create_role(
            CreateRoleCommand(name="Backdoor", permissions=[SupportPermission.MEMBER_MANAGE.value]), lead_actor,
        )

    # Within what the Lead holds, managing roles still works
    helper = await support.roles.create_role(
        CreateRoleCommand(name="Helper", permissions=[SupportPermission.TICKET_VIEW_ALL.value]), lead_actor,
    )
    await support.roles.update_role(UpdateRoleCommand(role_id=helper.id, name="Helper 2"), lead_actor)
    roles = {role.name: role for role in await support.roles.list_roles(None, manager)}
    assert roles["Lead"].permissions == frozenset(SupportPermission(value) for value in lead_permissions)
    assert "Helper 2" in roles and "Backdoor" not in roles


async def test_a_member_who_manages_members_cannot_hand_out_a_stronger_role(support):
    """`support.member.manage` without being the Manager: a new or moved member gets at most the actor's access."""
    _, manager = await _make_team(support)
    onboarder = [SupportPermission.MEMBER_MANAGE.value, SupportPermission.TICKET_VIEW_ASSIGNED.value]
    await support.roles.create_role(CreateRoleCommand(name="Onboarder", permissions=onboarder), manager)
    await support.roles.create_role(
        CreateRoleCommand(name="Basic", permissions=[SupportPermission.TICKET_VIEW_ASSIGNED.value]), manager,
    )
    _lead, lead_actor = await _make_member(support, manager, "Onboarder")

    with pytest.raises(SupportPermissionDeniedException):      # Viewer carries view_all, which the actor lacks
        await _make_member(support, lead_actor, "Viewer")
    basic, _basic_actor = await _make_member(support, lead_actor, "Basic")   # within the actor's own access
    with pytest.raises(SupportPermissionDeniedException):
        await support.members.update_member(
            UpdateMemberCommand(member_id=basic.id, role_id=await _role_id(support, manager, "Viewer")), lead_actor,
        )
    # The Manager is not limited
    await support.members.update_member(
        UpdateMemberCommand(member_id=basic.id, role_id=await _role_id(support, manager, "Viewer")), manager,
    )


async def test_team_manage_and_unknown_permissions_can_never_be_given_to_a_role(support):
    _, manager = await _make_team(support)
    with pytest.raises(SupportValidationException):
        await support.roles.create_role(
            CreateRoleCommand(name="Too Much", permissions=[SupportPermission.TEAM_MANAGE.value]), manager,
        )
    with pytest.raises(SupportValidationException):
        await support.roles.create_role(CreateRoleCommand(name="Odd", permissions=["support.nope"]), manager)


async def test_role_names_are_unique_per_team_and_roles_stay_in_their_team(support):
    _, manager = await _make_team(support)
    _, other_manager = await _make_team(support)

    await support.roles.create_role(CreateRoleCommand(name="Senior", permissions=[]), manager)
    await support.roles.create_role(CreateRoleCommand(name="Senior", permissions=[]), other_manager)  # other team: fine
    with pytest.raises(Exception) as caught:
        await support.roles.create_role(CreateRoleCommand(name="senior", permissions=[]), manager)
    assert caught.value.status_code == 409

    foreign = await _role_id(support, other_manager, "Viewer")
    with pytest.raises(RoleNotFoundException):
        await support.roles.update_role(UpdateRoleCommand(role_id=foreign, name="Taken Over"), manager)


async def test_super_admin_can_act_inside_any_team_by_naming_it(support):
    team, _ = await _make_team(support)
    roles = await support.roles.list_roles(team.id, SUPER_ADMIN)
    assert len(roles) == 5
    member = await support.members.create_member(
        CreateMemberCommand(
            role_id=roles[0].id, name="By Super Admin", team_id=team.id,
            email=f"s{uuid4().hex[:6]}@quickyee-tests.com", mobile=_digits(), password="Passw0rd!x",
        ),
        SUPER_ADMIN,
    )
    assert member.team_id == team.id
    with pytest.raises(Exception) as caught:
        await support.roles.list_roles(None, SUPER_ADMIN)      # no team named: nothing to act on
    assert caught.value.status_code == 404


async def test_team_list_search_and_counts(support):
    team, manager = await _make_team(support, name="Zebra Searchable Team")
    await _make_member(support, manager)
    teams, total = await support.teams.list_teams(ListTeamsQuery(search="zebra searchable"), SUPER_ADMIN)
    assert total == 1 and teams[0].id == team.id and teams[0].member_count == 2
