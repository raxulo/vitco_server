"""
Technical Support mobile API (Plan 26.2, REQ-67, REQ-70, REQ-71, DECISION-031).

Requests go through the real app (middleware, envelopes, exception handlers).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.modules.administration.domain.enums import Role
from app.modules.support.application.ticket_command import (
    AddAttachmentCommand,
    AssignTicketCommand,
    CreateCategoryCommand,
    PostMessageCommand,
)
from app.modules.support.application.ticket_handler import TicketHandler
from tests.support.test_foundation import _actor, _make_member, _make_team, support  # noqa: F401

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"0" * 64
BASE = "/api/v1/support"


@pytest.fixture
async def app_env(api, support, user_factory, token_for):  # noqa: F811
    from app.main import app

    handler = app.state.application.container.resolve(TicketHandler)
    admin_id = await user_factory(Role.SUPER_ADMIN, name="Super Admin")
    admin = _actor(admin_id, Role.SUPER_ADMIN)
    team, manager = await _make_team(support)
    category = await handler.create_category(
        CreateCategoryCommand(name=f"API {uuid4().hex[:8]}", default_team_id=team.id), admin,
    )

    async def person(role: Role = Role.FARMER):
        user_id = await user_factory(role, name=f"Person {uuid4().hex[:5]}")
        return user_id, token_for(user_id, role)

    return type("Env", (), {
        "api": api,
        "handler": handler,
        "support": support,
        "admin": admin,
        "admin_headers": token_for(admin_id, Role.SUPER_ADMIN),
        "team": team,
        "manager": manager,
        "category": category,
        "person": staticmethod(person),
        "headers": staticmethod(token_for),
    })


def _payload(env, **overrides) -> dict:
    values = {
        "subject": "Sync is not working",
        "description": "The app shows sync failed since morning.",
        "category_id": str(env.category.id),
        "device_model": "Redmi 9",
        "os_version": "Android 13",
        "app_version": "2.4.1",
    }
    values.update(overrides)
    return values


async def _create(env, headers, **overrides) -> dict:
    response = await env.api.post(f"{BASE}/tickets", json=_payload(env, **overrides), headers=headers)
    assert response.status_code in (200, 201), response.text
    return response.json()["data"]


def _upload(env, headers, ticket_id, content: bytes, name="photo.png", mime="image/png"):
    return env.api.post(
        f"{BASE}/tickets/{ticket_id}/attachments", headers=headers, files={"file": (name, content, mime)},
    )


# =========================================================
# ACCESS
# =========================================================

async def test_anonymous_calls_are_refused(app_env):
    for path in ("/categories", "/tickets"):
        assert (await app_env.api.get(f"{BASE}{path}")).status_code == 401


@pytest.mark.parametrize("role", [Role.MCC, Role.VLCC, Role.FARMER, Role.VLCC_FARMER])
async def test_app_user_roles_are_allowed(app_env, role):
    _user_id, headers = await app_env.person(role)
    response = await app_env.api.get(f"{BASE}/categories", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] is True


@pytest.mark.parametrize("role", [Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN])
async def test_other_roles_get_403(app_env, user_factory, role):
    headers = app_env.headers(await user_factory(role), role)
    for method, path in (("get", "/categories"), ("get", "/tickets"), ("post", "/tickets")):
        response = await getattr(app_env.api, method)(
            f"{BASE}{path}", headers=headers, **({"json": _payload(app_env)} if method == "post" else {}),
        )
        assert response.status_code == 403, (role, path, response.text)


# =========================================================
# TICKETS
# =========================================================

async def test_create_returns_201_with_the_ticket_number_and_a_single_record_envelope(app_env):
    _user_id, headers = await app_env.person()
    response = await app_env.api.post(f"{BASE}/tickets", json=_payload(app_env), headers=headers)
    body = response.json()
    assert response.status_code == 201
    assert (body["status"], body["code"]) == (True, 201)
    data = body["data"]
    assert data["ticket_no"].startswith("TS-") and data["status"] == "NEW" and data["status_label"] == "Received"
    assert [m["body"] for m in data["messages"]] == ["The app shows sync failed since morning."]
    assert data["can_reply"] is True and data["can_close"] is True and data["can_reopen"] is False


async def test_a_repeated_client_request_id_returns_the_first_ticket(app_env):
    _user_id, headers = await app_env.person()
    first = await app_env.api.post(f"{BASE}/tickets", json=_payload(app_env, client_request_id="once-1"), headers=headers)
    again = await app_env.api.post(f"{BASE}/tickets", json=_payload(app_env, client_request_id="once-1"), headers=headers)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["data"]["id"] == again.json()["data"]["id"]
    listing = (await app_env.api.get(f"{BASE}/tickets", headers=headers)).json()
    assert listing["total"] == 1


async def test_invalid_input_is_a_422(app_env):
    _user_id, headers = await app_env.person()
    assert (await app_env.api.post(f"{BASE}/tickets", json=_payload(app_env, subject="ab"), headers=headers)).status_code == 422
    assert (await app_env.api.post(f"{BASE}/tickets", json=_payload(app_env, category_id="nope"), headers=headers)).status_code == 422
    # A category that does not exist is a clean 404, not a server error
    missing = await app_env.api.post(f"{BASE}/tickets", json=_payload(app_env, category_id=str(uuid4())), headers=headers)
    assert missing.status_code == 404


async def test_list_uses_the_standard_pagination_envelope(app_env):
    _user_id, headers = await app_env.person()
    for index in range(3):
        await _create(app_env, headers, subject=f"Problem number {index}")
    body = (await app_env.api.get(f"{BASE}/tickets?limit=2&offset=0", headers=headers)).json()
    assert len(body["items"]) == 2
    assert {key: body[key] for key in ("limit", "offset", "total", "pages", "next_page", "has_more")} == {
        "limit": 2, "offset": 0, "total": 3, "pages": 2, "next_page": 2, "has_more": True,
    }
    last = (await app_env.api.get(f"{BASE}/tickets?limit=2&offset=2", headers=headers)).json()
    assert len(last["items"]) == 1 and last["has_more"] is False
    assert (await app_env.api.get(f"{BASE}/tickets?status=RESOLVED", headers=headers)).json()["total"] == 0
    assert (await app_env.api.get(f"{BASE}/tickets?limit=1000", headers=headers)).status_code == 422


async def test_a_requester_gets_404_for_another_users_ticket_on_every_endpoint(app_env):
    _owner_id, owner = await app_env.person()
    _intruder_id, intruder = await app_env.person()
    ticket_id = (await _create(app_env, owner))["id"]

    calls = [
        ("get", f"/tickets/{ticket_id}", None),
        ("get", f"/tickets/{ticket_id}/messages", None),
        ("post", f"/tickets/{ticket_id}/messages", {"json": {"body": "Not mine"}}),
        ("post", f"/tickets/{ticket_id}/read", None),
        ("post", f"/tickets/{ticket_id}/close", None),
        ("post", f"/tickets/{ticket_id}/reopen", None),
    ]
    for method, path, extra in calls:
        response = await getattr(app_env.api, method)(f"{BASE}{path}", headers=intruder, **(extra or {}))
        assert response.status_code == 404, (path, response.status_code)
    response = await _upload(app_env, intruder, ticket_id, PNG)
    assert response.status_code == 404


async def test_the_app_never_sees_internal_notes_internal_events_or_staff_details(app_env):
    _user_id, headers = await app_env.person()
    ticket_id = UUID((await _create(app_env, headers))["id"])
    member, member_actor = await _make_member(app_env.support, app_env.manager, "Technical Support")
    await app_env.handler.assign(AssignTicketCommand(ticket_id=ticket_id, assignee_user_id=member.user_id), app_env.manager)
    await app_env.handler.post_staff_message(
        PostMessageCommand(ticket_id=ticket_id, body="Secret: user is on a very old phone", internal=True), member_actor,
    )
    await app_env.handler.post_staff_message(PostMessageCommand(ticket_id=ticket_id, body="Please update the app"), member_actor)

    text = (await app_env.api.get(f"{BASE}/tickets/{ticket_id}", headers=headers)).text
    assert "Please update the app" in text
    for secret in ("Secret", "NOTE_ADDED", member.name, str(member.user_id), "assignee", "assigned_to", "team_id", "mobile"):
        assert secret not in text, secret
    detail = (await app_env.api.get(f"{BASE}/tickets/{ticket_id}", headers=headers)).json()["data"]
    assert detail["status_label"] == "In review"
    assert [m["from_you"] for m in detail["messages"]] == [True, False]
    assert {event["type"] for event in detail["timeline"]} <= {"CREATED", "STATUS_CHANGED", "REPLIED"}
    # The status move to ASSIGNED reads "In review" in the app, never the staff wording
    assert all(event["to_status"] in (None, "Received", "In review") for event in detail["timeline"])


# =========================================================
# MESSAGES
# =========================================================

async def test_messages_follow_after_id_and_repeats_are_ignored(app_env):
    _user_id, headers = await app_env.person()
    ticket_id = (await _create(app_env, headers))["id"]
    first = await app_env.api.post(
        f"{BASE}/tickets/{ticket_id}/messages", json={"body": "Any update?", "client_request_id": "m-1"}, headers=headers,
    )
    repeat = await app_env.api.post(
        f"{BASE}/tickets/{ticket_id}/messages", json={"body": "Any update?", "client_request_id": "m-1"}, headers=headers,
    )
    assert first.status_code == 201 and first.json()["data"]["id"] == repeat.json()["data"]["id"]

    everything = (await app_env.api.get(f"{BASE}/tickets/{ticket_id}/messages", headers=headers)).json()
    assert [item["body"] for item in everything["items"]][-1] == "Any update?"
    assert len(everything["items"]) == 2
    first_id = everything["items"][0]["id"]
    newer = (await app_env.api.get(f"{BASE}/tickets/{ticket_id}/messages?after_id={first_id}", headers=headers)).json()
    assert [item["body"] for item in newer["items"]] == ["Any update?"]
    assert newer["next_after_id"] == newer["items"][-1]["id"]
    assert (await app_env.api.get(f"{BASE}/tickets/{ticket_id}/messages?limit=1", headers=headers)).json()["has_more"] is True
    assert (await app_env.api.post(f"{BASE}/tickets/{ticket_id}/messages", json={"body": ""}, headers=headers)).status_code == 422


async def test_close_reopen_and_read_flow(app_env):
    _user_id, headers = await app_env.person()
    ticket_id = (await _create(app_env, headers))["id"]

    closed = await app_env.api.post(f"{BASE}/tickets/{ticket_id}/close", headers=headers)
    assert closed.status_code == 200 and closed.json()["data"]["status"] == "CLOSED"
    assert (await app_env.api.post(f"{BASE}/tickets/{ticket_id}/close", headers=headers)).status_code == 409
    blocked = await app_env.api.post(f"{BASE}/tickets/{ticket_id}/messages", json={"body": "One more thing"}, headers=headers)
    assert blocked.status_code == 409

    reopened = await app_env.api.post(f"{BASE}/tickets/{ticket_id}/reopen", headers=headers)
    assert reopened.json()["data"]["status"] == "REOPENED"
    read = await app_env.api.post(f"{BASE}/tickets/{ticket_id}/read", headers=headers)
    assert read.status_code == 200 and read.json()["data"]["unread"] == 0


async def test_staff_replies_show_as_unread_until_marked_read(app_env):
    _user_id, headers = await app_env.person()
    ticket_id = UUID((await _create(app_env, headers))["id"])
    await app_env.handler.post_staff_message(PostMessageCommand(ticket_id=ticket_id, body="We are checking"), app_env.manager)
    assert (await app_env.api.get(f"{BASE}/tickets", headers=headers)).json()["items"][0]["unread"] == 1
    await app_env.api.post(f"{BASE}/tickets/{ticket_id}/read", headers=headers)
    assert (await app_env.api.get(f"{BASE}/tickets", headers=headers)).json()["items"][0]["unread"] == 0


# =========================================================
# ATTACHMENTS
# =========================================================

async def test_photo_and_pdf_attach_and_download(app_env):
    _user_id, headers = await app_env.person()
    ticket_id = (await _create(app_env, headers))["id"]

    response = await _upload(app_env, headers, ticket_id, PNG, name="../../screen shot.png")
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["message"]["kind"] == "ATTACHMENT"
    attachment = data["attachment"]
    assert attachment["file_name"] == "screen shot.png"       # path parts removed
    assert attachment["mime_type"] == "image/png" and attachment["size_bytes"] == len(PNG)

    pdf = await _upload(app_env, headers, ticket_id, PDF, name="bill.pdf", mime="application/pdf")
    assert pdf.status_code == 201

    download = await app_env.api.get(attachment["url"], headers=headers)
    assert download.status_code == 200
    assert download.content == PNG
    assert download.headers["content-type"] == "image/png"
    assert "no-store" in download.headers["cache-control"]

    detail = (await app_env.api.get(f"{BASE}/tickets/{ticket_id}", headers=headers)).json()["data"]
    assert [len(m["attachments"]) for m in detail["messages"]] == [0, 1, 1]


@pytest.mark.parametrize(
    ("content", "name", "mime"),
    [
        (b"hello world, not an image", "notes.txt", "text/plain"),           # type not allowed
        (b"MZ" + b"\x00" * 64, "photo.png", "image/png"),                     # declared png, real exe
        (b"", "empty.png", "image/png"),                                      # empty
        (None, "big.png", "image/png"),                                       # over 10 MB (built in the test)
    ],
    ids=["wrong-type", "wrong-signature", "empty", "over-10mb"],
)
async def test_bad_attachments_are_rejected_with_422(app_env, content, name, mime):
    if content is None:
        content = PNG + b"\x00" * (10 * 1024 * 1024)
    _user_id, headers = await app_env.person()
    ticket_id = (await _create(app_env, headers))["id"]
    response = await _upload(app_env, headers, ticket_id, content, name=name, mime=mime)
    assert response.status_code == 422, response.text
    detail = (await app_env.api.get(f"{BASE}/tickets/{ticket_id}", headers=headers)).json()["data"]
    assert len(detail["messages"]) == 1                                       # nothing was stored


async def test_attachment_downloads_are_private_to_the_ticket(app_env):
    owner_id, owner = await app_env.person()
    _other_id, other = await app_env.person()
    ticket_id = (await _create(app_env, owner))["id"]
    attachment = (await _upload(app_env, owner, ticket_id, PNG)).json()["data"]["attachment"]

    assert (await app_env.api.get(attachment["url"], headers=other)).status_code == 404
    assert (await app_env.api.get(attachment["url"])).status_code == 401
    assert (await app_env.api.get(f"{BASE}/attachments/{uuid4()}", headers=owner)).status_code == 404

    # Staff of the ticket's team may open it; another team's staff may not
    stored, path = await app_env.handler.open_attachment(UUID(attachment["id"]), app_env.manager)
    assert path.is_file() and stored.size_bytes == len(PNG)
    _team, other_manager = await _make_team(app_env.support)
    from app.modules.support.domain.exceptions import TicketNotFoundException

    with pytest.raises(TicketNotFoundException):
        await app_env.handler.open_attachment(UUID(attachment["id"]), other_manager)

    # The public media route cannot reach the support folder
    key = stored.storage_key
    response = await app_env.api.get(f"/api/v1/media/{key}")
    assert response.status_code != 200


async def test_an_attachment_on_an_internal_note_is_hidden_from_the_requester(app_env):
    _user_id, headers = await app_env.person()
    ticket_id = UUID((await _create(app_env, headers))["id"])
    _message, attachment = await app_env.handler.attach_for_staff(
        AddAttachmentCommand(
            ticket_id=ticket_id, file_name="logs.pdf", content_type="application/pdf", data=PDF, internal=True,
        ),
        app_env.manager,
    )
    assert (await app_env.api.get(f"{BASE}/attachments/{attachment.id}", headers=headers)).status_code == 404
    detail = (await app_env.api.get(f"{BASE}/tickets/{ticket_id}", headers=headers)).json()["data"]
    assert len(detail["messages"]) == 1

    # A public staff attachment is downloadable by the requester
    _message, shared = await app_env.handler.attach_for_staff(
        AddAttachmentCommand(ticket_id=ticket_id, file_name="guide.pdf", content_type="application/pdf", data=PDF),
        app_env.manager,
    )
    assert (await app_env.api.get(f"{BASE}/attachments/{shared.id}", headers=headers)).status_code == 200


async def test_openapi_documents_the_support_endpoints(app_env):
    schema = (await app_env.api.get("/openapi.json")).json()
    paths = [path for path in schema["paths"] if path.startswith("/api/v1/support")]
    assert "/api/v1/support/tickets" in paths and "/api/v1/support/tickets/{ticket_id}/attachments" in paths
    assert len(paths) >= 8
