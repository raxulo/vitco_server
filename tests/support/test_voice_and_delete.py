"""
Technical Support: voice messages and deleting a message, through the real app.

- An audio recording sent as an attachment becomes a message of kind AUDIO; the type is checked
  against the content, and a client that only says `application/octet-stream` is understood.
- A sender deletes their own message: it stays as a placeholder without text or files, the other
  side hears `message.deleted`, and the rules match what the sender could still send.
"""

from __future__ import annotations

import asyncio
import re
from uuid import UUID

import pytest
from sqlalchemy import select

from app.modules.support.application.events import MESSAGE_DELETED, SupportEvent
from app.modules.support.infrastructure.models import SupportAuditLogModel
from app.modules.support.application.ticket_command import (
    AddAttachmentCommand,
    AssignTicketCommand,
    PostMessageCommand,
)
from app.modules.support.domain.enums import MessageKind
from app.modules.support.domain.exceptions import (
    MessageNotDeletableException,
    MessageNotFoundException,
    TicketClosedException,
)
from tests.support.test_foundation import _make_member, support  # noqa: F401
from tests.support.test_support_api import BASE, PNG, _create, _upload, app_env  # noqa: F401

# Smallest real-looking heads of each format (the server checks the leading bytes)
M4A = b"\x00\x00\x00\x1cftypM4A \x00\x00\x00\x00" + b"\x00" * 64
MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 64
MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 64
OGG = b"OggS\x00\x02" + b"\x00" * 64
WEBM = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81" + b"\x00" * 64
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 64
AAC = b"\xff\xf1\x50\x80" + b"\x00" * 64


# =========================================================
# VOICE MESSAGES
# =========================================================

async def test_a_voice_message_is_an_audio_message_that_plays_and_seeks(app_env):
    _user_id, headers = await app_env.person()
    ticket_id = (await _create(app_env, headers))["id"]

    response = await _upload(app_env, headers, ticket_id, M4A, name="voice.m4a", mime="audio/x-m4a")
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["message"]["kind"] == "AUDIO"
    attachment = data["attachment"]
    assert attachment["mime_type"] == "audio/mp4" and attachment["file_name"] == "voice.m4a"

    download = await app_env.api.get(attachment["url"], headers=headers)
    assert download.status_code == 200 and download.content == M4A
    assert download.headers["content-type"] == "audio/mp4"
    # Players ask for ranges to seek
    part = await app_env.api.get(attachment["url"], headers={**headers, "Range": "bytes=0-9"})
    assert part.status_code == 206 and part.content == M4A[:10]

    detail = (await app_env.api.get(f"{BASE}/tickets/{ticket_id}", headers=headers)).json()["data"]
    assert [m["kind"] for m in detail["messages"]] == ["TEXT", "AUDIO"]


@pytest.mark.parametrize(
    ("content", "mime", "stored"),
    [
        (M4A, "audio/mp4", "audio/mp4"),
        (M4A, "audio/m4a", "audio/mp4"),
        (MP3, "audio/mpeg", "audio/mpeg"),
        (MP3_FRAME, "audio/mp3", "audio/mpeg"),
        (OGG, "audio/ogg", "audio/ogg"),
        (WEBM, "audio/webm", "audio/webm"),
        (WEBM, "video/webm", "audio/webm"),
        (WAV, "audio/wav", "audio/wav"),
        (AAC, "audio/aac", "audio/aac"),
        # A client that does not know the type: worked out from the content
        (M4A, "application/octet-stream", "audio/mp4"),
        (OGG, "application/octet-stream", "audio/ogg"),
        (PNG, "application/octet-stream", "image/png"),
    ],
    ids=["m4a", "m4a-alias", "mp3-id3", "mp3-frame", "ogg", "webm", "webm-video-label", "wav", "aac",
         "sniff-m4a", "sniff-ogg", "sniff-png"],
)
async def test_recordings_in_the_usual_formats_are_accepted(app_env, content, mime, stored):
    _user_id, headers = await app_env.person()
    ticket_id = (await _create(app_env, headers))["id"]
    response = await _upload(app_env, headers, ticket_id, content, name="recording", mime=mime)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["attachment"]["mime_type"] == stored
    assert data["message"]["kind"] == ("AUDIO" if stored.startswith("audio/") else "ATTACHMENT")


@pytest.mark.parametrize(
    ("content", "mime"),
    [
        (PNG, "audio/mpeg"),                                   # says audio, is an image
        (b"MZ" + b"\x00" * 64, "audio/mp4"),                    # says audio, is a program
        (b"plain text that is no file", "application/octet-stream"),
        (b"MZ" + b"\x00" * 64, "application/octet-stream"),
        (M4A, "audio/flac"),                                    # a type we do not take
    ],
    ids=["png-as-audio", "exe-as-audio", "unknown-text", "unknown-exe", "flac"],
)
async def test_files_that_are_not_what_they_say_are_refused(app_env, content, mime):
    _user_id, headers = await app_env.person()
    ticket_id = (await _create(app_env, headers))["id"]
    response = await _upload(app_env, headers, ticket_id, content, name="voice.m4a", mime=mime)
    assert response.status_code == 422, response.text
    detail = (await app_env.api.get(f"{BASE}/tickets/{ticket_id}", headers=headers)).json()["data"]
    assert len(detail["messages"]) == 1


async def test_staff_can_send_a_voice_message_the_requester_plays(app_env):
    _user_id, headers = await app_env.person()
    ticket_id = UUID((await _create(app_env, headers))["id"])
    message, attachment = await app_env.handler.attach_for_staff(
        AddAttachmentCommand(ticket_id=ticket_id, file_name="reply.webm", content_type="audio/webm;codecs=opus", data=WEBM),
        app_env.manager,
    )
    assert message.kind is MessageKind.AUDIO and attachment.mime_type == "audio/webm"
    download = await app_env.api.get(f"{BASE}/attachments/{attachment.id}", headers=headers)
    assert download.status_code == 200 and download.content == WEBM


# =========================================================
# DELETING A MESSAGE (requester)
# =========================================================

async def test_the_requester_deletes_their_own_message_and_its_file(app_env):
    _user_id, headers = await app_env.person()
    ticket_id = (await _create(app_env, headers))["id"]
    sent = (await app_env.api.post(f"{BASE}/tickets/{ticket_id}/messages", json={"body": "Wrong number, sorry"},
                                   headers=headers)).json()["data"]
    voice = (await _upload(app_env, headers, ticket_id, M4A, name="v.m4a", mime="audio/mp4")).json()["data"]
    stored, path = await app_env.handler.open_attachment(UUID(voice["attachment"]["id"]), app_env.manager)
    assert path.is_file()

    for message_id in (sent["id"], voice["message"]["id"]):
        response = await app_env.api.delete(f"{BASE}/tickets/{ticket_id}/messages/{message_id}", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["is_deleted"] is True and data["body"] == "" and data["attachments"] == []
        assert data["deleted_at"] is not None

    # The text and the file are gone; the places stay
    detail = (await app_env.api.get(f"{BASE}/tickets/{ticket_id}", headers=headers)).json()["data"]
    assert [(m["is_deleted"], m["body"]) for m in detail["messages"]] == [
        (False, "The app shows sync failed since morning."), (True, ""), (True, ""),
    ]
    assert "Wrong number" not in (await app_env.api.get(f"{BASE}/tickets/{ticket_id}/messages", headers=headers)).text
    assert not path.is_file()
    assert (await app_env.api.get(voice["attachment"]["url"], headers=headers)).status_code == 404
    assert {"MESSAGE_DELETED"} <= {event["type"] for event in detail["timeline"]}

    # Again: the same answer, nothing changes
    again = await app_env.api.delete(f"{BASE}/tickets/{ticket_id}/messages/{sent['id']}", headers=headers)
    assert again.status_code == 200 and again.json()["data"]["is_deleted"] is True


async def test_the_requester_cannot_delete_what_is_not_theirs_to_delete(app_env):
    _user_id, headers = await app_env.person()
    _other_id, other = await app_env.person()
    ticket = await _create(app_env, headers)
    ticket_id, first_id = ticket["id"], ticket["messages"][0]["id"]
    other_ticket = await _create(app_env, other)
    reply = await app_env.handler.post_staff_message(
        PostMessageCommand(ticket_id=UUID(ticket_id), body="We are checking"), app_env.manager,
    )
    note = await app_env.handler.post_staff_message(
        PostMessageCommand(ticket_id=UUID(ticket_id), body="Old phone", internal=True), app_env.manager,
    )

    def delete(path_ticket, message_id, who=headers):
        return app_env.api.delete(f"{BASE}/tickets/{path_ticket}/messages/{message_id}", headers=who)

    first = await delete(ticket_id, first_id)                       # the description
    assert first.status_code == 409 and first.json()["error"]["code"] == "SUPPORT_MESSAGE_NOT_DELETABLE"
    staff = await delete(ticket_id, reply.id)                       # support's reply
    assert staff.status_code == 409 and staff.json()["error"]["code"] == "SUPPORT_MESSAGE_NOT_DELETABLE"
    hidden = await delete(ticket_id, note.id)                       # an internal note looks like nothing
    assert hidden.status_code == 404 and hidden.json()["error"]["code"] == "SUPPORT_MESSAGE_NOT_FOUND"
    elsewhere = await delete(ticket_id, other_ticket["messages"][0]["id"])   # a message of another ticket
    assert elsewhere.status_code == 404
    assert (await delete(other_ticket["id"], first_id)).status_code == 404   # someone else's ticket
    assert (await delete(ticket_id, 999_999_999)).status_code == 404
    assert (await app_env.api.delete(f"{BASE}/tickets/{ticket_id}/messages/{first_id}")).status_code == 401

    texts = [m["body"] for m in (await app_env.api.get(f"{BASE}/tickets/{ticket_id}", headers=headers)).json()["data"]["messages"]]
    assert "We are checking" in texts


async def test_nothing_is_deleted_on_a_closed_ticket(app_env):
    _user_id, headers = await app_env.person()
    ticket_id = (await _create(app_env, headers))["id"]
    sent = (await app_env.api.post(f"{BASE}/tickets/{ticket_id}/messages", json={"body": "One more"},
                                   headers=headers)).json()["data"]
    await app_env.api.post(f"{BASE}/tickets/{ticket_id}/close", headers=headers)
    response = await app_env.api.delete(f"{BASE}/tickets/{ticket_id}/messages/{sent['id']}", headers=headers)
    assert response.status_code == 409 and response.json()["error"]["code"] == "SUPPORT_TICKET_CLOSED"


# =========================================================
# DELETING A MESSAGE (staff)
# =========================================================

async def test_staff_delete_their_own_reply_and_the_requester_sees_it_deleted(app_env):
    _user_id, headers = await app_env.person()
    ticket_id = UUID((await _create(app_env, headers))["id"])
    reply = await app_env.handler.post_staff_message(
        PostMessageCommand(ticket_id=ticket_id, body="Sent to the wrong ticket"), app_env.manager,
    )
    heard: list[SupportEvent] = []
    app_env.handler._events.subscribe(heard.append)

    deleted = await app_env.handler.delete_staff_message(ticket_id, reply.id, app_env.manager)
    assert deleted.is_deleted and deleted.body == ""
    await asyncio.sleep(0.05)
    event = next(e for e in heard if e.type == MESSAGE_DELETED and e.ticket_id == str(ticket_id))
    assert event.public is True and event.data == {"message_id": reply.id}
    assert event.for_requester()["data"] == {"message_id": reply.id}

    messages = (await app_env.api.get(f"{BASE}/tickets/{ticket_id}", headers=headers)).json()["data"]["messages"]
    assert messages[-1]["is_deleted"] is True and messages[-1]["from_you"] is False
    assert "wrong ticket" not in str(messages)

    # The audit log says who deleted what
    async with app_env.handler._database.transaction() as session:
        rows = (await session.scalars(select(SupportAuditLogModel).where(
            SupportAuditLogModel.action == "ticket.message_deleted", SupportAuditLogModel.entity_id == str(ticket_id),
        ))).all()
    assert [(row.actor_id, row.meta["message_id"], row.meta["internal"]) for row in rows] == [
        (app_env.manager.id, reply.id, False),
    ]


async def test_staff_rules_follow_what_they_could_still_send(app_env):
    _user_id, headers = await app_env.person()
    ticket_id = UUID((await _create(app_env, headers))["id"])
    member, member_actor = await _make_member(app_env.support, app_env.manager, "Technical Support")
    await app_env.handler.assign(AssignTicketCommand(ticket_id=ticket_id, assignee_user_id=member.user_id), app_env.manager)
    manager_reply = await app_env.handler.post_staff_message(
        PostMessageCommand(ticket_id=ticket_id, body="Manager here"), app_env.manager,
    )
    reply = await app_env.handler.post_staff_message(PostMessageCommand(ticket_id=ticket_id, body="Reply"), member_actor)
    note = await app_env.handler.post_staff_message(
        PostMessageCommand(ticket_id=ticket_id, body="Note", internal=True), member_actor,
    )
    first = (await app_env.handler.get_for_staff(ticket_id, app_env.manager)).messages[0]

    with pytest.raises(MessageNotDeletableException):               # a colleague's reply
        await app_env.handler.delete_staff_message(ticket_id, manager_reply.id, member_actor)
    with pytest.raises(MessageNotDeletableException):               # the requester's message
        await app_env.handler.delete_staff_message(ticket_id, first.id, app_env.manager)
    with pytest.raises(MessageNotFoundException):
        await app_env.handler.delete_staff_message(ticket_id, 999_999_999, app_env.manager)

    # Closed: a reply stays, a note can still go
    assert (await app_env.api.post(f"{BASE}/tickets/{ticket_id}/close", headers=headers)).status_code == 200
    with pytest.raises(TicketClosedException):
        await app_env.handler.delete_staff_message(ticket_id, reply.id, member_actor)
    deleted_note = await app_env.handler.delete_staff_message(ticket_id, note.id, member_actor)
    assert deleted_note.is_deleted


# =========================================================
# PORTAL
# =========================================================

async def test_the_portal_plays_voice_messages_and_deletes_own_messages(app_env, token_for):
    from app.modules.administration.domain.enums import Role

    _user_id, headers = await app_env.person()
    ticket_id = UUID((await _create(app_env, headers))["id"])
    await _upload(app_env, headers, str(ticket_id), M4A, name="voice.m4a", mime="audio/mp4")
    own = await app_env.handler.post_staff_message(PostMessageCommand(ticket_id=ticket_id, body="Typo reply"), app_env.manager)
    staff = token_for(app_env.manager.id, Role.SUPPORT)

    page = (await app_env.api.get(f"/support/tickets/{ticket_id}", headers=staff)).text
    audio = re.search(r'<audio controls preload="metadata" src="(/support/attachments/[0-9a-f-]+)"', page)
    assert audio, "the voice message has a player"
    played = await app_env.api.get(audio.group(1), headers=staff)
    assert played.status_code == 200 and played.headers["content-type"] == "audio/mp4"
    # Delete shows on the member's own reply only
    assert page.count('class="sp-bubble-delete"') == 1 and f"/messages/{own.id}/delete" in page
    assert 'data-record hidden' in page                              # the Record button (shown by the browser script)

    response = await app_env.api.post(
        f"/support/tickets/{ticket_id}/messages/{own.id}/delete",
        headers={**staff, "HX-Request": "true"}, follow_redirects=False,
    )
    assert response.status_code == 200
    assert "This message was deleted" in response.text and "Typo reply" not in response.text
    assert f"/messages/{own.id}/delete" not in response.text

    # Without HTMX it goes back to the ticket
    plain = await app_env.api.post(
        f"/support/tickets/{ticket_id}/messages/{own.id}/delete", headers=staff, follow_redirects=False,
    )
    assert plain.status_code in (302, 303) and plain.headers["location"] == f"/support/tickets/{ticket_id}"
