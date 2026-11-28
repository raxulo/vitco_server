"""
Technical Support calls (Plan 29.1, REQ-78, REQ-64, D-5, D-6): click-to-call with a record, through the
real handlers and the real portal.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.modules.administration.domain.enums import Role
from app.modules.support.application.call_handler import CallHandler
from app.modules.support.application.ticket_command import AssignTicketCommand
from app.modules.support.domain.enums import EventType
from app.modules.support.domain.exceptions import (
    CallAlreadyOpenException,
    CallNotFoundException,
    SupportPermissionDeniedException,
    SupportValidationException,
    TicketNotFoundException,
)
from app.modules.support.infrastructure.models import SupportAuditLogModel, SupportTicketEventModel
from tests.support.test_foundation import _make_member, _make_team, support  # noqa: F401
from tests.support.test_tickets import _category, _raise, _team_ticket, desk  # noqa: F401


@pytest.fixture
async def phone(desk, token_for):  # noqa: F811
    from app.main import app

    team, manager, ticket, requester = await _team_ticket(desk)
    tech, tech_actor = await _make_member(desk, manager, "Technical Support")
    viewer, viewer_actor = await _make_member(desk, manager, "Viewer")
    chat, chat_actor = await _make_member(desk, manager, "Chat Agent")
    await desk.tickets.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=tech.user_id), manager)
    return SimpleNamespace(
        desk=desk, team=team, manager=manager, ticket=ticket, requester=requester,
        tech=tech, tech_actor=tech_actor, viewer_actor=viewer_actor, chat_actor=chat_actor,
        calls=app.state.application.container.resolve(CallHandler),
        session=lambda actor: token_for(actor.id, Role.SUPPORT),
    )


async def _count(desk, model, *where) -> int:
    async with desk.database.transaction() as session:
        return int(await session.scalar(select(func.count()).select_from(model).where(*where)) or 0)


# =========================================================
# HANDLER
# =========================================================

async def test_a_member_with_call_permission_starts_and_finishes_a_call(phone):
    call, number = await phone.calls.start_call(phone.ticket.id, phone.tech_actor)
    assert number == phone.ticket.requester_mobile and call.is_open and call.ticket_no == phone.ticket.ticket_no

    done = await phone.calls.finish_call(call.id, outcome="connected", duration_s=95, note=" Asked to update ", actor=phone.tech_actor)
    assert (done.outcome, done.duration_s, done.note) == ("CONNECTED", 95, "Asked to update") and not done.is_open

    events = await _count(phone.desk, SupportTicketEventModel, SupportTicketEventModel.ticket_id == phone.ticket.id,
                          SupportTicketEventModel.event_type.in_([EventType.CALL_STARTED, EventType.CALL_LOGGED]))
    assert events == 2
    for action in ("call.started", "call.logged"):
        assert await _count(phone.desk, SupportAuditLogModel, SupportAuditLogModel.action == action,
                            SupportAuditLogModel.entity_id == str(phone.ticket.id)) == 1
    history = await phone.calls.calls_for_ticket(phone.ticket.id, phone.manager)
    assert [c.outcome for c in history] == ["CONNECTED"] and history[0].member_name == phone.tech.name


@pytest.mark.parametrize("who", ["viewer_actor", "chat_actor"])
async def test_viewers_and_chat_agents_cannot_call(phone, who):
    with pytest.raises(SupportPermissionDeniedException):
        await phone.calls.start_call(phone.ticket.id, getattr(phone, who))


async def test_a_member_cannot_call_about_a_ticket_they_cannot_see(phone):
    _team, other_manager = await _make_team(phone.desk)
    with pytest.raises(TicketNotFoundException):
        await phone.calls.start_call(phone.ticket.id, other_manager)


async def test_one_open_call_per_member(phone):
    first, _ = await phone.calls.start_call(phone.ticket.id, phone.tech_actor)
    again, _ = await phone.calls.start_call(phone.ticket.id, phone.tech_actor)
    assert again.id == first.id                                   # pressing Call twice keeps one record

    category = await _category(phone.desk, team_id=phone.team.id)
    other = await _raise(phone.desk, phone.requester, category, subject="Second problem")
    await phone.desk.tickets.assign(AssignTicketCommand(ticket_id=other.id, assignee_user_id=phone.tech.user_id), phone.manager)
    with pytest.raises(CallAlreadyOpenException) as raised:
        await phone.calls.start_call(other.id, phone.tech_actor)
    assert phone.ticket.ticket_no in raised.value.message

    await phone.calls.finish_call(first.id, outcome="BUSY", duration_s=None, note=None, actor=phone.tech_actor)
    second, _ = await phone.calls.start_call(other.id, phone.tech_actor)
    assert second.ticket_id == other.id


async def test_only_the_caller_records_the_outcome_once_and_it_is_checked(phone):
    call, _ = await phone.calls.start_call(phone.ticket.id, phone.tech_actor)
    with pytest.raises(CallNotFoundException):
        await phone.calls.finish_call(call.id, outcome="CONNECTED", duration_s=None, note=None, actor=phone.manager)
    with pytest.raises(SupportValidationException):
        await phone.calls.finish_call(call.id, outcome="HAPPY", duration_s=None, note=None, actor=phone.tech_actor)
    with pytest.raises(SupportValidationException):
        await phone.calls.finish_call(call.id, outcome="CONNECTED", duration_s=-5, note=None, actor=phone.tech_actor)
    with pytest.raises(SupportValidationException):
        await phone.calls.finish_call(call.id, outcome="CONNECTED", duration_s=None, note="x" * 1001, actor=phone.tech_actor)
    with pytest.raises(CallNotFoundException):
        await phone.calls.finish_call(uuid4(), outcome="CONNECTED", duration_s=None, note=None, actor=phone.tech_actor)
    await phone.calls.finish_call(call.id, outcome="NOT_REACHABLE", duration_s=0, note=None, actor=phone.tech_actor)
    with pytest.raises(SupportValidationException):
        await phone.calls.finish_call(call.id, outcome="CONNECTED", duration_s=None, note=None, actor=phone.tech_actor)


async def test_calls_never_reach_the_requester(phone):
    call, _ = await phone.calls.start_call(phone.ticket.id, phone.tech_actor)
    await phone.calls.finish_call(call.id, outcome="CALLBACK_REQUESTED", duration_s=None, note="Call at 5", actor=phone.tech_actor)
    view = await phone.desk.tickets.get_for_requester(phone.ticket.id, phone.requester)
    assert not {EventType.CALL_STARTED, EventType.CALL_LOGGED} & {e.event_type for e in view.events}


# =========================================================
# PORTAL
# =========================================================

async def test_everyone_sees_the_number_only_callers_get_the_call_button(api, phone):
    path = f"/support/tickets/{phone.ticket.id}"
    for actor, can_call in ((phone.tech_actor, True), (phone.manager, True), (phone.viewer_actor, False)):
        text = (await api.get(path, headers=phone.session(actor))).text
        assert phone.ticket.requester_mobile in text
        assert ("data-sp-call=" in text) is can_call, actor


async def test_call_then_outcome_through_the_portal(api, phone):
    headers = phone.session(phone.tech_actor)
    started = await api.post(f"/support/tickets/{phone.ticket.id}/calls", headers=headers)
    assert started.status_code == 200
    data = started.json()["data"]
    assert data["tel"] == f"tel:{phone.ticket.requester_mobile}"

    page = (await api.get(f"/support/tickets/{phone.ticket.id}", headers=headers)).text
    assert "How did the call go?" in page and f"/support/calls/{data['call_id']}/finish" in page

    saved = await api.post(
        f"/support/calls/{data['call_id']}/finish", headers=headers, follow_redirects=False,
        data={"ticket_id": str(phone.ticket.id), "outcome": "CONNECTED", "minutes": "2.5", "note": "Fixed by update"},
    )
    assert saved.headers["location"] == f"/support/tickets/{phone.ticket.id}?notice=call_logged"
    page = (await api.get(f"/support/tickets/{phone.ticket.id}?notice=call_logged", headers=headers)).text
    assert "Call outcome saved." in page and "How did the call go?" not in page
    assert "Fixed by update" in page and "Connected" in page and "2.5 min" in page
    assert "Call outcome: Connected" in page                      # in the timeline


async def test_portal_refusals_come_back_as_json_or_a_notice(api, phone):
    refused = await api.post(f"/support/tickets/{phone.ticket.id}/calls", headers=phone.session(phone.viewer_actor))
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "SUPPORT_PERMISSION_DENIED"
    call = (await api.post(f"/support/tickets/{phone.ticket.id}/calls", headers=phone.session(phone.tech_actor))).json()["data"]
    bad = await api.post(f"/support/calls/{call['call_id']}/finish", headers=phone.session(phone.tech_actor),
                         follow_redirects=False, data={"ticket_id": str(phone.ticket.id), "outcome": "NOPE"})
    assert bad.headers["location"].endswith("?notice=invalid")


async def test_an_open_call_elsewhere_is_shown_as_a_reminder(api, phone):
    await phone.calls.start_call(phone.ticket.id, phone.tech_actor)
    category = await _category(phone.desk, team_id=phone.team.id)
    other = await _raise(phone.desk, phone.requester, category, subject="Another one")
    await phone.desk.tickets.assign(AssignTicketCommand(ticket_id=other.id, assignee_user_id=phone.tech.user_id), phone.manager)
    page = (await api.get(f"/support/tickets/{other.id}", headers=phone.session(phone.tech_actor))).text
    assert f"Your call on {phone.ticket.ticket_no} has no outcome yet." in page
    conflict = await api.post(f"/support/tickets/{other.id}/calls", headers=phone.session(phone.tech_actor))
    assert conflict.status_code == 409 and phone.ticket.ticket_no in conflict.json()["error"]["message"]


async def test_seeing_the_number_is_audited_once_a_day_per_member(api, phone):
    where = (SupportAuditLogModel.action == "ticket.phone_viewed", SupportAuditLogModel.entity_id == str(phone.ticket.id))
    before = await _count(phone.desk, SupportAuditLogModel, *where)
    for _ in range(3):
        await api.get(f"/support/tickets/{phone.ticket.id}", headers=phone.session(phone.viewer_actor))
    await api.get(f"/support/tickets/{phone.ticket.id}", headers=phone.session(phone.manager))
    assert await _count(phone.desk, SupportAuditLogModel, *where) == before + 2
    # The number is never written to the audit meta
    async with phone.desk.database.transaction() as session:
        metas = (await session.scalars(select(SupportAuditLogModel.meta).where(*where))).all()
    assert all(phone.ticket.requester_mobile not in str(meta) for meta in metas)
    assert re.match(r"^\d{10}$", phone.ticket.requester_mobile)
