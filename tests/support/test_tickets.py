"""
Technical Support tickets (Plan 26.1, REQ-66 to REQ-71, DECISION-031).

The ticket engine through the real handlers against the session database: creation and
idempotency, routing, assignment, status flow, internal notes and visibility.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.support.application.command import SetTeamActiveCommand
from app.modules.support.application.handler import (
    SupportMemberHandler,
    SupportRoleHandler,
    SupportTeamHandler,
)
from app.modules.support.application.ticket_command import (
    AssignTicketCommand,
    ChangeCategoryCommand,
    ChangePriorityCommand,
    ChangeStatusCommand,
    CreateCategoryCommand,
    CreateTicketCommand,
    ListMessagesQuery,
    ListRequesterTicketsQuery,
    ListStaffTicketsQuery,
    PostMessageCommand,
    RouteTicketCommand,
    UpdateCategoryCommand,
)
from app.modules.support.application.ticket_handler import TicketHandler
from app.modules.support.domain import ticket_rules
from app.modules.support.domain.enums import EventType, Scope, TicketPriority, TicketStatus
from app.modules.support.domain.exceptions import (
    CategoryNameAlreadyExistsException,
    CategoryNotFoundException,
    InvalidAssigneeException,
    InvalidTicketTransitionException,
    SupportAccessDeniedException,
    SupportPermissionDeniedException,
    TicketClosedException,
    TicketNotFoundException,
    TicketNotRoutedException,
)
from app.modules.support.infrastructure.models import SupportAuditLogModel, SupportTicketEventModel
from tests.support.test_foundation import _actor, _make_member, _make_team

S = TicketStatus


# =========================================================
# HELPERS
# =========================================================

@pytest.fixture
async def desk(api, database, user_factory):
    from app.main import app

    container = app.state.application.container

    async def requester(role: Role = Role.FARMER) -> CurrentUser:
        return _actor(await user_factory(role, name=f"Requester {uuid4().hex[:6]}"), role)

    admin = _actor(await user_factory(Role.SUPER_ADMIN, name="Super Admin"), Role.SUPER_ADMIN)

    return SimpleNamespace(
        admin=admin,
        database=database,
        tickets=container.resolve(TicketHandler),
        teams=container.resolve(SupportTeamHandler),
        members=container.resolve(SupportMemberHandler),
        roles=container.resolve(SupportRoleHandler),
        requester=requester,
    )


async def _category(desk, *, team_id: UUID | None = None, priority=TicketPriority.MEDIUM):
    return await desk.tickets.create_category(
        CreateCategoryCommand(name=f"Category {uuid4().hex[:8]}", default_team_id=team_id, default_priority=priority),
        desk.admin,
    )


async def _raise(desk, requester: CurrentUser, category, **overrides):
    values = dict(
        subject="Sync is not working",
        description="The app does not sync since morning.",
        category_id=category.id,
        device_model="Redmi 9",
        os_version="Android 13",
        app_version="2.4.1",
    )
    values.update(overrides)
    ticket, _created = await desk.tickets.create(CreateTicketCommand(**values), requester)
    return ticket


async def _team_ticket(desk, role: Role = Role.FARMER):
    """A ticket routed to a fresh team; returns (team, manager, ticket, requester)."""
    team, manager = await _make_team(desk)
    category = await _category(desk, team_id=team.id)
    requester = await desk.requester(role)
    ticket = await _raise(desk, requester, category)
    return team, manager, ticket, requester


async def _events(desk, ticket_id: UUID) -> list[str]:
    async with desk.database.transaction() as session:
        rows = await session.scalars(
            select(SupportTicketEventModel.event_type)
            .where(SupportTicketEventModel.ticket_id == ticket_id)
            .order_by(SupportTicketEventModel.id)
        )
        return [row.value for row in rows]


async def _audit_count(desk, action: str, entity_id: UUID) -> int:
    async with desk.database.transaction() as session:
        return int(
            await session.scalar(
                select(func.count(SupportAuditLogModel.id)).where(
                    SupportAuditLogModel.action == action,
                    SupportAuditLogModel.entity_id == str(entity_id),
                )
            ) or 0
        )


# =========================================================
# RULES (no database)
# =========================================================

LEGAL = [
    (S.NEW, S.ASSIGNED), (S.NEW, S.ESCALATED),
    (S.ASSIGNED, S.IN_PROGRESS), (S.ASSIGNED, S.ESCALATED),
    (S.IN_PROGRESS, S.WAITING_ON_USER), (S.IN_PROGRESS, S.RESOLVED), (S.IN_PROGRESS, S.ESCALATED),
    (S.WAITING_ON_USER, S.IN_PROGRESS), (S.WAITING_ON_USER, S.RESOLVED),
    (S.ESCALATED, S.IN_PROGRESS), (S.ESCALATED, S.RESOLVED),
    (S.RESOLVED, S.CLOSED), (S.RESOLVED, S.REOPENED), (S.CLOSED, S.REOPENED),
    (S.REOPENED, S.ASSIGNED), (S.REOPENED, S.IN_PROGRESS),
]


@pytest.mark.parametrize(("current", "target"), LEGAL)
def test_every_legal_staff_move_passes(current, target):
    ticket_rules.ensure_staff_transition(current, target)


def test_every_other_staff_move_is_refused():
    legal = set(LEGAL)
    for current in S:
        for target in S:
            if (current, target) in legal or current is target:
                continue
            if target in ticket_rules.STAFF_TRANSITIONS[current]:
                continue
            with pytest.raises(InvalidTicketTransitionException):
                ticket_rules.ensure_staff_transition(current, target)
    with pytest.raises(InvalidTicketTransitionException):
        ticket_rules.ensure_staff_transition(S.NEW, S.RESOLVED)
    with pytest.raises(InvalidTicketTransitionException):
        ticket_rules.ensure_staff_transition(S.CLOSED, S.IN_PROGRESS)


def test_requester_can_only_close_or_reopen():
    ticket_rules.ensure_requester_transition(S.RESOLVED, S.REOPENED)
    ticket_rules.ensure_requester_transition(S.RESOLVED, S.CLOSED)
    ticket_rules.ensure_requester_transition(S.NEW, S.CLOSED)
    ticket_rules.ensure_requester_transition(S.CLOSED, S.REOPENED)
    for current, target in [(S.NEW, S.RESOLVED), (S.NEW, S.IN_PROGRESS), (S.IN_PROGRESS, S.REOPENED)]:
        with pytest.raises(InvalidTicketTransitionException):
            ticket_rules.ensure_requester_transition(current, target)


def test_a_reply_on_waiting_or_resolved_moves_the_ticket():
    assert ticket_rules.requester_reply_target(S.WAITING_ON_USER) is S.IN_PROGRESS
    assert ticket_rules.requester_reply_target(S.RESOLVED) is S.REOPENED
    assert ticket_rules.requester_reply_target(S.NEW) is None


# =========================================================
# CATEGORIES
# =========================================================

async def test_only_super_admin_manages_categories(desk):
    team, manager = await _make_team(desk)
    with pytest.raises(SupportPermissionDeniedException):
        await desk.tickets.create_category(CreateCategoryCommand(name="Manager made"), manager)

    category = await _category(desk, team_id=team.id, priority=TicketPriority.HIGH)
    assert category.default_team_id == team.id
    assert category.default_priority is TicketPriority.HIGH

    with pytest.raises(CategoryNameAlreadyExistsException):
        await desk.tickets.create_category(CreateCategoryCommand(name=category.name.upper()), desk.admin)

    renamed = await desk.tickets.update_category(
        UpdateCategoryCommand(category_id=category.id, set_team=True, default_team_id=None, is_active=False),
        desk.admin,
    )
    assert renamed.default_team_id is None
    assert renamed.is_active is False


async def test_inactive_categories_are_hidden_from_requesters(desk):
    category = await _category(desk)
    farmer = await desk.requester(Role.FARMER)
    assert category.id in {item.id for item in await desk.tickets.list_categories(farmer)}

    await desk.tickets.update_category(UpdateCategoryCommand(category_id=category.id, is_active=False), desk.admin)
    assert category.id not in {item.id for item in await desk.tickets.list_categories(farmer)}
    with pytest.raises(CategoryNotFoundException):
        await _raise(desk, farmer, category)


# =========================================================
# CREATING TICKETS
# =========================================================

@pytest.mark.parametrize("role", [Role.MCC, Role.VLCC, Role.FARMER, Role.VLCC_FARMER])
async def test_app_user_roles_can_raise_tickets(desk, role):
    category = await _category(desk)
    ticket = await _raise(desk, await desk.requester(role), category)
    assert ticket.status is S.NEW
    assert ticket.requester_name


@pytest.mark.parametrize("role", [Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN, Role.SUPPORT])
async def test_other_roles_cannot_raise_tickets(desk, role):
    category = await _category(desk)
    stranger = _actor(uuid4(), role)
    with pytest.raises(SupportAccessDeniedException):
        await _raise(desk, stranger, category)


async def test_ticket_numbers_are_unique_and_follow_the_pattern(desk):
    category = await _category(desk)
    farmer = await desk.requester()
    numbers = [(await _raise(desk, farmer, category)).ticket_no for _ in range(3)]
    assert len(set(numbers)) == 3
    for number in numbers:
        prefix, year, serial = number.split("-")
        assert prefix == "TS" and len(year) == 4 and len(serial) == 6
    assert numbers == sorted(numbers)


async def test_same_client_request_id_returns_the_same_ticket(desk):
    category = await _category(desk)
    farmer = await desk.requester()
    command = CreateTicketCommand(
        subject="Printer problem", description="Printer prints blank pages.",
        category_id=category.id, client_request_id="offline-001",
    )
    first, created_first = await desk.tickets.create(command, farmer)
    second, created_second = await desk.tickets.create(command, farmer)
    assert (created_first, created_second) == (True, False)
    assert first.id == second.id

    # Another requester using the same id raises their own ticket
    other, created = await desk.tickets.create(command, await desk.requester())
    assert created and other.id != first.id

    tickets, total = await desk.tickets.list_for_requester(ListRequesterTicketsQuery(), farmer)
    assert total == 1 and tickets[0].id == first.id


def _blind_first_lookup(monkeypatch, repository, name: str) -> None:
    """The retry's duplicate check runs before the original commits: its first lookup finds nothing."""
    real = getattr(repository, name)
    calls = {"count": 0}

    async def lookup(*args, **kwargs):
        calls["count"] += 1
        return None if calls["count"] == 1 else await real(*args, **kwargs)

    monkeypatch.setattr(repository, name, lookup)


async def test_a_retry_racing_the_original_ticket_gets_it_instead_of_an_error(desk, monkeypatch):
    category = await _category(desk)
    farmer = await desk.requester()
    command = CreateTicketCommand(
        subject="Printer problem", description="Printer prints blank pages.",
        category_id=category.id, client_request_id=f"race-{uuid4().hex[:8]}",
    )
    first, _created = await desk.tickets.create(command, farmer)
    _blind_first_lookup(monkeypatch, desk.tickets._repository, "find_by_client_request")
    second, created = await desk.tickets.create(command, farmer)
    assert created is False and second.id == first.id
    _tickets, total = await desk.tickets.list_for_requester(ListRequesterTicketsQuery(), farmer)
    assert total == 1


async def test_a_retry_racing_the_original_message_gets_it_instead_of_an_error(desk, monkeypatch):
    _team, _manager, ticket, requester = await _team_ticket(desk)
    command = PostMessageCommand(ticket_id=ticket.id, body="Any update?", client_request_id=f"race-{uuid4().hex[:8]}")
    first = await desk.tickets.post_requester_message(command, requester)
    _blind_first_lookup(monkeypatch, desk.tickets._repository, "find_message_by_client_request")
    again = await desk.tickets.post_requester_message(command, requester)
    assert again.id == first.id
    messages = await desk.tickets.list_messages_for_requester(ListMessagesQuery(ticket_id=ticket.id), requester)
    assert [m.body for m in messages].count("Any update?") == 1


async def test_new_ticket_starts_with_the_description_as_first_message_and_a_created_event(desk):
    category = await _category(desk)
    farmer = await desk.requester()
    ticket = await _raise(desk, farmer, category, description="Rate chart is missing.")
    view = await desk.tickets.get_for_requester(ticket.id, farmer)
    assert [message.body for message in view.messages] == ["Rate chart is missing."]
    assert [event.event_type for event in view.events] == [EventType.CREATED]
    assert (ticket.device_model, ticket.os_version, ticket.app_version) == ("Redmi 9", "Android 13", "2.4.1")


async def test_overlong_device_details_are_clipped_not_rejected(desk):
    category = await _category(desk)
    ticket = await _raise(desk, await desk.requester(), category, device_model="X" * 500)
    assert len(ticket.device_model) == 100


# =========================================================
# ROUTING (REQ-68)
# =========================================================

async def test_category_with_a_team_routes_there_and_takes_its_priority(desk):
    team, _manager = await _make_team(desk)
    category = await _category(desk, team_id=team.id, priority=TicketPriority.URGENT)
    ticket = await _raise(desk, await desk.requester(), category)
    assert ticket.team_id == team.id
    assert ticket.priority is TicketPriority.URGENT


async def test_category_without_a_team_waits_in_the_unassigned_pool(desk):
    ticket = await _raise(desk, await desk.requester(), await _category(desk))
    assert ticket.team_id is None
    tickets, _total = await desk.tickets.list_for_staff(ListStaffTicketsQuery(scope=Scope.UNASSIGNED), desk.admin)
    assert ticket.id in {item.id for item in tickets}

    # No team staff can see it
    _team, manager = await _make_team(desk)
    with pytest.raises(TicketNotFoundException):
        await desk.tickets.get_for_staff(ticket.id, manager)
    tickets, _total = await desk.tickets.list_for_staff(ListStaffTicketsQuery(scope=Scope.ALL), manager)
    assert ticket.id not in {item.id for item in tickets}


async def test_a_disabled_team_sends_new_tickets_to_the_pool(desk):
    team, _manager = await _make_team(desk)
    category = await _category(desk, team_id=team.id)
    await desk.teams.set_active(SetTeamActiveCommand(team_id=team.id, is_active=False), desk.admin)
    assert (await _raise(desk, await desk.requester(), category)).team_id is None


async def test_super_admin_routes_a_pool_ticket_to_a_team(desk):
    ticket = await _raise(desk, await desk.requester(), await _category(desk))
    team, manager = await _make_team(desk)

    with pytest.raises(SupportPermissionDeniedException):
        await desk.tickets.route_to_team(RouteTicketCommand(ticket_id=ticket.id, team_id=team.id), manager)
    routed = await desk.tickets.route_to_team(RouteTicketCommand(ticket_id=ticket.id, team_id=team.id), desk.admin)
    assert routed.team_id == team.id
    assert (await desk.tickets.get_for_staff(ticket.id, manager)).ticket.id == ticket.id
    assert EventType.ROUTED.value in await _events(desk, ticket.id)


async def test_a_pool_ticket_cannot_be_assigned_before_it_is_routed(desk):
    ticket = await _raise(desk, await desk.requester(), await _category(desk))
    with pytest.raises(TicketNotRoutedException):
        await desk.tickets.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=uuid4()), desk.admin)


# =========================================================
# ASSIGNMENT (REQ-68)
# =========================================================

async def test_manager_assigns_to_a_member_and_status_becomes_assigned(desk):
    team, manager, ticket, _requester = await _team_ticket(desk)
    member, member_actor = await _make_member(desk, manager)

    assigned = await desk.tickets.assign(
        AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=member.user_id), manager,
    )
    assert assigned.assigned_to == member.user_id
    assert assigned.status is S.ASSIGNED
    assert assigned.assignee_name == member.name
    assert await _events(desk, ticket.id) == ["CREATED", "ROUTED", "ASSIGNED", "STATUS_CHANGED"]
    assert await _audit_count(desk, "ticket.assigned", ticket.id) == 1

    mine, total = await desk.tickets.list_for_staff(ListStaffTicketsQuery(scope=Scope.MINE), member_actor)
    assert total == 1 and mine[0].id == ticket.id


async def test_ticket_assigner_can_assign_but_a_technical_member_cannot(desk):
    _team, manager, ticket, _requester = await _team_ticket(desk)
    _assigner, assigner_actor = await _make_member(desk, manager, "Ticket Assigner")
    worker, worker_actor = await _make_member(desk, manager, "Technical Support")

    # Permission is checked before the ticket is looked up
    with pytest.raises(SupportPermissionDeniedException):
        await desk.tickets.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=worker.user_id), worker_actor)

    await desk.tickets.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=worker.user_id), assigner_actor)
    # Now visible to the assignee, but still without the assign permission
    with pytest.raises(SupportPermissionDeniedException):
        await desk.tickets.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=worker.user_id), worker_actor)


async def test_assigning_to_someone_outside_the_team_is_rejected(desk):
    _team, manager, ticket, _requester = await _team_ticket(desk)
    _other_team, other_manager = await _make_team(desk)
    other_member, _actor_ = await _make_member(desk, other_manager)

    with pytest.raises(InvalidAssigneeException):
        await desk.tickets.assign(
            AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=other_member.user_id), manager,
        )
    with pytest.raises(InvalidAssigneeException):
        await desk.tickets.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=uuid4()), manager)


async def test_another_teams_manager_cannot_see_or_touch_the_ticket(desk):
    _team, _manager, ticket, _requester = await _team_ticket(desk)
    _other_team, other_manager = await _make_team(desk)

    with pytest.raises(TicketNotFoundException):
        await desk.tickets.get_for_staff(ticket.id, other_manager)
    with pytest.raises(TicketNotFoundException):
        await desk.tickets.post_staff_message(PostMessageCommand(ticket_id=ticket.id, body="Hello there"), other_manager)
    with pytest.raises(TicketNotFoundException):
        await desk.tickets.change_status(ChangeStatusCommand(ticket_id=ticket.id, status=S.ESCALATED), other_manager)


async def test_view_assigned_members_only_see_their_own_tickets(desk):
    _team, manager, ticket, _requester = await _team_ticket(desk)
    worker, worker_actor = await _make_member(desk, manager, "Technical Support")

    with pytest.raises(TicketNotFoundException):
        await desk.tickets.get_for_staff(ticket.id, worker_actor)
    tickets, total = await desk.tickets.list_for_staff(ListStaffTicketsQuery(scope=Scope.ALL), worker_actor)
    assert total == 0 and tickets == []

    await desk.tickets.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=worker.user_id), manager)
    assert (await desk.tickets.get_for_staff(ticket.id, worker_actor)).ticket.id == ticket.id
    _tickets, total = await desk.tickets.list_for_staff(ListStaffTicketsQuery(scope=Scope.ALL), worker_actor)
    assert total == 1


async def test_queue_scopes_need_the_right_permission(desk):
    _team, manager, _ticket, _requester = await _team_ticket(desk)
    _caller, caller_actor = await _make_member(desk, manager, "Caller")      # view_assigned only
    _viewer, viewer_actor = await _make_member(desk, manager, "Viewer")      # view_all only

    with pytest.raises(SupportPermissionDeniedException):
        await desk.tickets.list_for_staff(ListStaffTicketsQuery(scope=Scope.UNASSIGNED), caller_actor)
    # A viewer reads the queue (view_all) but holds no assign permission; unassigned needs one of them
    _tickets, total = await desk.tickets.list_for_staff(ListStaffTicketsQuery(scope=Scope.UNASSIGNED), viewer_actor)
    assert total == 1
    _tickets, total = await desk.tickets.list_for_staff(ListStaffTicketsQuery(scope=Scope.ALL), viewer_actor)
    assert total == 1


async def test_staff_list_filters_and_search(desk):
    team, manager, ticket, requester = await _team_ticket(desk)
    other_category = await _category(desk, team_id=team.id)
    second = await _raise(desk, requester, other_category, subject="Printer jammed badly")

    _tickets, total = await desk.tickets.list_for_staff(
        ListStaffTicketsQuery(scope=Scope.ALL, search="printer"), manager,
    )
    assert total == 1
    tickets, _total = await desk.tickets.list_for_staff(
        ListStaffTicketsQuery(scope=Scope.ALL, search=ticket.ticket_no), manager,
    )
    assert [item.id for item in tickets] == [ticket.id]
    _tickets, total = await desk.tickets.list_for_staff(
        ListStaffTicketsQuery(scope=Scope.ALL, category_id=other_category.id), manager,
    )
    assert total == 1
    _tickets, total = await desk.tickets.list_for_staff(
        ListStaffTicketsQuery(scope=Scope.ALL, status=[S.RESOLVED]), manager,
    )
    assert total == 0
    tickets, total = await desk.tickets.list_for_staff(ListStaffTicketsQuery(scope=Scope.ALL), manager)
    assert total == 2 and {item.id for item in tickets} == {ticket.id, second.id}
    # The list carries requester, category and team names without extra lookups
    assert all(item.requester_name and item.category_name and item.team_name for item in tickets)


# =========================================================
# MESSAGES AND INTERNAL NOTES (REQ-70, REQ-71)
# =========================================================

async def test_internal_notes_never_reach_the_requester(desk):
    _team, manager, ticket, requester = await _team_ticket(desk)
    await desk.tickets.post_staff_message(PostMessageCommand(ticket_id=ticket.id, body="Looks like a bad SIM"), manager)
    await desk.tickets.post_staff_message(
        PostMessageCommand(ticket_id=ticket.id, body="Do not tell the farmer: customer is rude", internal=True), manager,
    )

    staff_view = await desk.tickets.get_for_staff(ticket.id, manager)
    assert [m.is_internal for m in staff_view.messages] == [False, False, True]
    assert EventType.NOTE_ADDED in {event.event_type for event in staff_view.events}

    view = await desk.tickets.get_for_requester(ticket.id, requester)
    assert [m.body for m in view.messages] == ["The app does not sync since morning.", "Looks like a bad SIM"]
    assert EventType.NOTE_ADDED not in {event.event_type for event in view.events}
    assert EventType.ROUTED not in {event.event_type for event in view.events}
    messages = await desk.tickets.list_messages_for_requester(ListMessagesQuery(ticket_id=ticket.id), requester)
    assert all(not message.is_internal for message in messages)


async def test_a_viewer_cannot_reply_or_note_and_a_caller_can_note_only(desk):
    _team, manager, ticket, _requester = await _team_ticket(desk)
    _viewer, viewer_actor = await _make_member(desk, manager, "Viewer")
    with pytest.raises(SupportPermissionDeniedException):
        await desk.tickets.post_staff_message(PostMessageCommand(ticket_id=ticket.id, body="Hello there"), viewer_actor)
    with pytest.raises(SupportPermissionDeniedException):
        await desk.tickets.post_staff_message(
            PostMessageCommand(ticket_id=ticket.id, body="Note to self", internal=True), viewer_actor,
        )

    caller, caller_actor = await _make_member(desk, manager, "Caller")
    await desk.tickets.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=caller.user_id), manager)
    await desk.tickets.post_staff_message(
        PostMessageCommand(ticket_id=ticket.id, body="Called, no answer", internal=True), caller_actor,
    )
    with pytest.raises(SupportPermissionDeniedException):
        await desk.tickets.post_staff_message(PostMessageCommand(ticket_id=ticket.id, body="Hello there"), caller_actor)


async def test_a_requester_reaches_only_their_own_tickets(desk):
    category = await _category(desk)
    owner = await desk.requester()
    intruder = await desk.requester()
    ticket = await _raise(desk, owner, category)

    for call in (
        desk.tickets.get_for_requester(ticket.id, intruder),
        desk.tickets.list_messages_for_requester(ListMessagesQuery(ticket_id=ticket.id), intruder),
        desk.tickets.post_requester_message(PostMessageCommand(ticket_id=ticket.id, body="Not mine"), intruder),
        desk.tickets.requester_close(ticket.id, intruder),
        desk.tickets.mark_read_for_requester(ticket.id, intruder),
    ):
        with pytest.raises(TicketNotFoundException):
            await call
    tickets, total = await desk.tickets.list_for_requester(ListRequesterTicketsQuery(), intruder)
    assert (tickets, total) == ([], 0)


async def test_messages_page_by_id_and_repeat_request_ids_are_ignored(desk):
    _team, manager, ticket, requester = await _team_ticket(desk)
    first = await desk.tickets.post_requester_message(
        PostMessageCommand(ticket_id=ticket.id, body="Any update?", client_request_id="m-1"), requester,
    )
    again = await desk.tickets.post_requester_message(
        PostMessageCommand(ticket_id=ticket.id, body="Any update?", client_request_id="m-1"), requester,
    )
    assert first.id == again.id
    reply = await desk.tickets.post_staff_message(PostMessageCommand(ticket_id=ticket.id, body="Checking now"), manager)

    messages = await desk.tickets.list_messages_for_requester(ListMessagesQuery(ticket_id=ticket.id), requester)
    assert [m.body for m in messages] == ["The app does not sync since morning.", "Any update?", "Checking now"]
    later = await desk.tickets.list_messages_for_requester(
        ListMessagesQuery(ticket_id=ticket.id, after_id=first.id), requester,
    )
    assert [m.id for m in later] == [reply.id]
    assert [m.id for m in messages] == sorted(m.id for m in messages)


async def test_unread_counters_follow_who_wrote_last(desk):
    _team, manager, ticket, requester = await _team_ticket(desk)
    assert ticket.staff_unread == 1

    await desk.tickets.post_staff_message(PostMessageCommand(ticket_id=ticket.id, body="We are on it"), manager)
    await desk.tickets.post_staff_message(
        PostMessageCommand(ticket_id=ticket.id, body="Internal only", internal=True), manager,
    )
    seen_by_requester = (await desk.tickets.list_for_requester(ListRequesterTicketsQuery(), requester))[0][0]
    assert seen_by_requester.requester_unread == 1       # the internal note did not count
    assert seen_by_requester.first_response_at is not None

    await desk.tickets.mark_read_for_requester(ticket.id, requester)
    assert (await desk.tickets.list_for_requester(ListRequesterTicketsQuery(), requester))[0][0].requester_unread == 0

    await desk.tickets.get_for_staff(ticket.id, manager)     # opening clears the staff mark
    assert (await desk.tickets.get_for_staff(ticket.id, manager)).ticket.staff_unread == 0


# =========================================================
# STATUS FLOW (REQ-69)
# =========================================================

async def test_status_flow_from_assigned_to_closed_writes_every_step(desk):
    _team, manager, ticket, requester = await _team_ticket(desk)
    worker, worker_actor = await _make_member(desk, manager, "Technical Support")
    await desk.tickets.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=worker.user_id), manager)

    for target in (S.IN_PROGRESS, S.WAITING_ON_USER, S.IN_PROGRESS, S.RESOLVED):
        moved = await desk.tickets.change_status(ChangeStatusCommand(ticket_id=ticket.id, status=target), worker_actor)
        assert moved.status is target
    assert moved.resolved_at is not None

    closed = await desk.tickets.change_status(ChangeStatusCommand(ticket_id=ticket.id, status=S.CLOSED), manager)
    assert closed.closed_at is not None
    events = await _events(desk, ticket.id)
    assert events.count("STATUS_CHANGED") == 6          # ASSIGNED, 4 moves by the worker, CLOSED
    assert await _audit_count(desk, "ticket.status_changed", ticket.id) == 5


async def test_illegal_and_unpermitted_moves_are_refused(desk):
    _team, manager, ticket, _requester = await _team_ticket(desk)
    worker, worker_actor = await _make_member(desk, manager, "Technical Support")
    await desk.tickets.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=worker.user_id), manager)

    with pytest.raises(InvalidTicketTransitionException):
        await desk.tickets.change_status(ChangeStatusCommand(ticket_id=ticket.id, status=S.RESOLVED), worker_actor)
    with pytest.raises(InvalidTicketTransitionException):
        await desk.tickets.change_status(ChangeStatusCommand(ticket_id=ticket.id, status=S.CLOSED), manager)

    await desk.tickets.change_status(ChangeStatusCommand(ticket_id=ticket.id, status=S.IN_PROGRESS), worker_actor)
    await desk.tickets.change_status(ChangeStatusCommand(ticket_id=ticket.id, status=S.RESOLVED), worker_actor)
    # The Technical Support template cannot close
    with pytest.raises(SupportPermissionDeniedException):
        await desk.tickets.change_status(ChangeStatusCommand(ticket_id=ticket.id, status=S.CLOSED), worker_actor)


async def test_new_ticket_can_only_be_assigned_through_assign(desk):
    _team, manager, ticket, _requester = await _team_ticket(desk)
    with pytest.raises(InvalidTicketTransitionException):
        await desk.tickets.change_status(ChangeStatusCommand(ticket_id=ticket.id, status=S.ASSIGNED), manager)


async def test_requester_reply_on_waiting_ticket_resumes_it_and_on_resolved_reopens_it(desk):
    _team, manager, ticket, requester = await _team_ticket(desk)
    worker, worker_actor = await _make_member(desk, manager, "Technical Support")
    await desk.tickets.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=worker.user_id), manager)
    for target in (S.IN_PROGRESS, S.WAITING_ON_USER):
        await desk.tickets.change_status(ChangeStatusCommand(ticket_id=ticket.id, status=target), worker_actor)

    await desk.tickets.post_requester_message(PostMessageCommand(ticket_id=ticket.id, body="Here is the info"), requester)
    assert (await desk.tickets.get_for_requester(ticket.id, requester)).ticket.status is S.IN_PROGRESS

    await desk.tickets.change_status(ChangeStatusCommand(ticket_id=ticket.id, status=S.RESOLVED), worker_actor)
    await desk.tickets.post_requester_message(PostMessageCommand(ticket_id=ticket.id, body="Still broken"), requester)
    reopened = (await desk.tickets.get_for_requester(ticket.id, requester)).ticket
    assert reopened.status is S.REOPENED and reopened.resolved_at is None


async def test_requester_closes_and_reopens_and_a_closed_ticket_takes_no_replies(desk):
    _team, manager, ticket, requester = await _team_ticket(desk)
    closed = await desk.tickets.requester_close(ticket.id, requester)
    assert closed.status is S.CLOSED and closed.closed_at is not None

    with pytest.raises(TicketClosedException):
        await desk.tickets.post_requester_message(PostMessageCommand(ticket_id=ticket.id, body="One more thing"), requester)
    with pytest.raises(TicketClosedException):
        await desk.tickets.post_staff_message(PostMessageCommand(ticket_id=ticket.id, body="Anyone there?"), manager)
    # An internal note is still allowed on a closed ticket
    await desk.tickets.post_staff_message(PostMessageCommand(ticket_id=ticket.id, body="Closed by user", internal=True), manager)

    reopened = await desk.tickets.requester_reopen(ticket.id, requester)
    assert reopened.status is S.REOPENED and reopened.closed_at is None
    with pytest.raises(InvalidTicketTransitionException):
        await desk.tickets.requester_reopen(ticket.id, requester)


async def test_priority_and_category_changes_are_internal_events(desk):
    team, manager, ticket, requester = await _team_ticket(desk)
    _viewer, viewer_actor = await _make_member(desk, manager, "Viewer")
    with pytest.raises(SupportPermissionDeniedException):
        await desk.tickets.change_priority(
            ChangePriorityCommand(ticket_id=ticket.id, priority=TicketPriority.HIGH), viewer_actor,
        )

    changed = await desk.tickets.change_priority(
        ChangePriorityCommand(ticket_id=ticket.id, priority=TicketPriority.HIGH), manager,
    )
    assert changed.priority is TicketPriority.HIGH
    other = await _category(desk, team_id=team.id)
    recategorised = await desk.tickets.change_category(
        ChangeCategoryCommand(ticket_id=ticket.id, category_id=other.id), manager,
    )
    assert recategorised.category_id == other.id

    public = {event.event_type for event in (await desk.tickets.get_for_requester(ticket.id, requester)).events}
    assert public == {EventType.CREATED}
    assert {"PRIORITY_CHANGED", "CATEGORY_CHANGED"} <= set(await _events(desk, ticket.id))


async def test_super_admin_works_on_any_teams_ticket(desk):
    _team, _manager, ticket, _requester = await _team_ticket(desk)
    view = await desk.tickets.get_for_staff(ticket.id, desk.admin)
    assert view.ticket.id == ticket.id
    await desk.tickets.post_staff_message(PostMessageCommand(ticket_id=ticket.id, body="Super Admin here"), desk.admin)
    tickets, total = await desk.tickets.list_for_staff(ListStaffTicketsQuery(scope=Scope.ALL), desk.admin)
    assert total >= 1 and ticket.id in {item.id for item in tickets}


async def test_a_disabled_member_loses_ticket_access(desk):
    from app.modules.support.application.command import SetMemberActiveCommand

    _team, manager, ticket, _requester = await _team_ticket(desk)
    member, member_actor = await _make_member(desk, manager, "Ticket Assigner")
    assert (await desk.tickets.get_for_staff(ticket.id, member_actor)).ticket.id == ticket.id
    await desk.members.set_active(SetMemberActiveCommand(member_id=member.id, is_active=False), manager)
    with pytest.raises(SupportAccessDeniedException):
        await desk.tickets.get_for_staff(ticket.id, member_actor)
