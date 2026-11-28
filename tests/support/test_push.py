"""
Technical Support pushes (Plan 28.1, REQ-77): what support asks the shared notification module to send.

The delivery itself (devices, worker, FCM) is tested in `tests/notification`.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from app.modules.notification.application.handler import DeviceHandler
from app.modules.notification.application.service import NotificationService
from app.modules.support.application.push_messages import SOURCE
from app.modules.support.application.ticket_command import (
    AddAttachmentCommand,
    AssignTicketCommand,
    ChangeStatusCommand,
    PostMessageCommand,
)
from app.modules.support.application.ticket_handler import TicketHandler
from app.modules.support.domain.enums import TicketStatus
from tests.support.test_foundation import _make_member, support  # noqa: F401
from tests.support.test_tickets import _team_ticket, desk  # noqa: F401

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
async def push(desk):  # noqa: F811
    """The shared notification service switched on (it is off in tests: no Firebase credential)."""
    from app.main import app

    container = app.state.application.container
    service: NotificationService = container.resolve(NotificationService)
    was = service._enabled
    service._enabled = True
    team, manager, ticket, requester = await _team_ticket(desk)
    yield SimpleNamespace(
        desk=desk, team=team, manager=manager, ticket=ticket, requester=requester,
        devices=container.resolve(DeviceHandler),
        database=container.database,   # the manager the handlers use, so their transactions nest in ours
        handler=container.resolve(TicketHandler),
    )
    service._enabled = was


async def _outbox(push) -> list:
    return await push.devices.outbox_for(push.requester.id, source=SOURCE)


async def test_support_is_wired_to_the_shared_service(push):
    assert push.handler._outbox is not None


async def test_a_staff_reply_queues_one_short_push_and_a_note_queues_none(push):
    long_text = "Please update the app from the Play Store and then log in again with your mobile number " * 3
    await push.desk.tickets.post_staff_message(PostMessageCommand(ticket_id=push.ticket.id, body=long_text), push.manager)
    await push.desk.tickets.post_staff_message(
        PostMessageCommand(ticket_id=push.ticket.id, body="Internal: rude customer", internal=True), push.manager,
    )
    rows = await _outbox(push)
    assert [row.type for row in rows] == ["TICKET_REPLY"]
    row = rows[0]
    assert row.title == f"Reply on {push.ticket.ticket_no}" and len(row.body) <= 100 and row.body.endswith("…")
    assert (row.source, row.reference_id, row.skip_if_online) == ("support", str(push.ticket.id), True)
    assert row.payload == {
        "ticket_no": push.ticket.ticket_no, "source": "support", "type": "TICKET_REPLY", "reference_id": str(push.ticket.id),
    }
    assert all("rude" not in r.body for r in rows)


async def test_a_staff_file_says_a_file_was_sent(push):
    await push.desk.tickets.attach_for_staff(
        AddAttachmentCommand(ticket_id=push.ticket.id, file_name="guide.png", content_type="image/png", data=PNG), push.manager,
    )
    await push.desk.tickets.attach_for_staff(
        AddAttachmentCommand(ticket_id=push.ticket.id, file_name="internal.png", content_type="image/png", data=PNG, internal=True),
        push.manager,
    )
    assert [r.body for r in await _outbox(push)] == ["The support team sent you a file."]


async def test_a_staff_voice_message_says_a_voice_message_was_sent(push):
    ogg = b"OggS\x00\x02" + b"\x00" * 64
    await push.desk.tickets.attach_for_staff(
        AddAttachmentCommand(ticket_id=push.ticket.id, file_name="reply.ogg", content_type="audio/ogg", data=ogg), push.manager,
    )
    assert [r.body for r in await _outbox(push)] == ["The support team sent you a voice message."]


async def test_staff_status_moves_queue_pushes_the_requesters_own_moves_do_not(push):
    worker, _ = await _make_member(push.desk, push.manager, "Technical Support")
    await push.desk.tickets.assign(AssignTicketCommand(ticket_id=push.ticket.id, assignee_user_id=worker.user_id), push.manager)
    for status in (TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED):
        await push.desk.tickets.change_status(ChangeStatusCommand(ticket_id=push.ticket.id, status=status), push.manager)
    rows = await _outbox(push)
    assert [(r.type, r.title) for r in rows] == [
        ("TICKET_STATUS", f"{push.ticket.ticket_no}: In review"),
        ("TICKET_STATUS", f"{push.ticket.ticket_no}: In progress"),
        ("TICKET_RESOLVED", f"{push.ticket.ticket_no} is resolved"),
    ]
    assert rows[-1].skip_if_online is False                    # "resolved" is worth a push even with the app open
    await push.desk.tickets.requester_reopen(push.ticket.id, push.requester)
    await push.desk.tickets.post_requester_message(PostMessageCommand(ticket_id=push.ticket.id, body="Still broken"), push.requester)
    await push.desk.tickets.requester_close(push.ticket.id, push.requester)
    assert len(await _outbox(push)) == 3


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="SQLite: the app's pysqlite setup lets a released savepoint commit (pre-existing, see STATE concerns); "
           "verified on PostgreSQL",
)
async def test_the_push_rolls_back_with_the_ticket_change(push):
    with pytest.raises(RuntimeError):
        async with push.database.transaction():
            await push.desk.tickets.post_staff_message(PostMessageCommand(ticket_id=push.ticket.id, body="Never saved"), push.manager)
            raise RuntimeError("the request failed after the reply")
    assert await _outbox(push) == []
