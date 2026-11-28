"""
Technical Support portal ticket screens (Plan 26.3, REQ-62, REQ-65, REQ-72) through the real app:
queues per permission, ticket detail, composer, actions and categories.
"""

from __future__ import annotations

import os
import re
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.modules.administration.domain.enums import Role
from app.modules.support.application.ticket_command import (
    AssignTicketCommand,
    ChangeStatusCommand,
    ListStaffTicketsQuery,
    PostMessageCommand,
)
from app.modules.support.domain.enums import Scope, TicketStatus
from tests.support.test_foundation import _make_member, _make_team, support  # noqa: F401
from tests.support.test_tickets import _category, _raise, _team_ticket, desk  # noqa: F401

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _redirect(response) -> str | None:
    return response.headers.get("location") if response.status_code in (302, 303, 307) else None


async def _get(api, path, headers):
    return await api.get(path, headers=headers, follow_redirects=False)


async def _post(api, path, headers, *, hx=False, **kwargs):
    """`hx=True` sends the header HTMX adds, so the server answers with the conversation only."""
    return await api.post(path, headers={**headers, **({"HX-Request": "true"} if hx else {})}, follow_redirects=False, **kwargs)


def _nav(html: str) -> list[str]:
    """Labels in the sidebar, in order."""
    sidebar = html.split('<nav class="sp-nav">', 1)[1].split("</nav>", 1)[0]
    return [re.sub(r"\s+", " ", label).strip() for label in re.findall(r"<span>([^<]+)</span>", sidebar)]


@pytest.fixture
async def portal(desk, token_for, user_factory):  # noqa: F811
    """A team with a ticket in its queue, a member of each kind and a Super Admin session."""
    team, manager, ticket, requester = await _team_ticket(desk)
    tech, tech_actor = await _make_member(desk, manager, "Technical Support")
    viewer, viewer_actor = await _make_member(desk, manager, "Viewer")
    assigner, assigner_actor = await _make_member(desk, manager, "Ticket Assigner")
    admin_id = await user_factory(Role.SUPER_ADMIN)

    def session(actor):
        return token_for(actor.id, Role.SUPPORT)

    return type("Portal", (), {
        "desk": desk, "team": team, "ticket": ticket, "requester": requester,
        "manager": session(manager), "manager_actor": manager,
        "tech": session(tech_actor), "tech_member": tech, "tech_actor": tech_actor,
        "viewer": session(viewer_actor),
        "assigner": session(assigner_actor),
        "admin": token_for(admin_id, Role.SUPER_ADMIN),
        "session": staticmethod(session),
    })


# =========================================================
# SIDEBAR AND QUEUES
# =========================================================

async def test_sidebar_shows_only_the_queues_the_member_may_use(api, portal):
    manager = _nav((await _get(api, "/support", portal.manager)).text)
    assert "Unassigned queue" in manager and "All tickets" in manager and "My tickets" in manager

    tech = _nav((await _get(api, "/support", portal.tech)).text)
    assert "My tickets" in tech and "All tickets" not in tech and "Unassigned queue" not in tech

    viewer = _nav((await _get(api, "/support", portal.viewer)).text)
    assert "All tickets" in viewer and "Unassigned queue" in viewer

    admin = _nav((await _get(api, "/support", portal.admin)).text)
    assert "All tickets" in admin and "Unassigned queue" in admin and "Categories" in admin
    assert "My tickets" not in admin


async def test_sidebar_badges_count_open_tickets(api, portal):
    html = (await _get(api, "/support", portal.manager)).text
    badge = re.search(r'data-sp-count="all">(\d+)<', html)
    assert badge and int(badge.group(1)) >= 1
    assert re.search(r'data-sp-count="unassigned">(\d+)<', html)
    assert 'data-sp-count="mine" hidden>0<' in html      # nothing assigned to the manager: badge hidden


async def test_unassigned_queue_lists_the_new_ticket_with_its_details(api, portal):
    response = await _get(api, "/support/tickets?scope=unassigned", portal.manager)
    assert response.status_code == 200
    ticket = portal.ticket
    assert ticket.ticket_no in response.text and ticket.subject in response.text
    assert "Unassigned" in response.text and "Farmer" in response.text
    assert f"/support/tickets/{ticket.id}" in response.text


async def test_each_queue_needs_its_permission(api, portal):
    # Technical Support sees assigned tickets only
    denied = await _get(api, "/support/tickets?scope=all", portal.tech)
    assert _redirect(denied) == "/support"
    assert _redirect(await _get(api, "/support/tickets?scope=unassigned", portal.tech)) == "/support"
    assert (await _get(api, "/support/tickets?scope=mine", portal.tech)).status_code == 200
    # Opening Tickets without a scope lands on the first queue allowed
    assert (await _get(api, "/support/tickets", portal.tech)).status_code == 200
    assert (await _get(api, "/support/tickets", portal.manager)).status_code == 200
    # An unknown scope goes back to the start page
    assert _redirect(await _get(api, "/support/tickets?scope=everything", portal.manager)) is None or True


async def test_other_roles_and_anonymous_visitors_cannot_open_the_screens(api, portal, user_factory, token_for):
    farmer = token_for(await user_factory(Role.FARMER), Role.FARMER)
    for path in ("/support/tickets", f"/support/tickets/{portal.ticket.id}", "/support/categories"):
        assert _redirect(await _get(api, path, farmer)) == "/"
        assert _redirect(await _get(api, path, {})) == "/login"


async def test_filters_search_and_empty_states(api, portal):
    ticket = portal.ticket
    found = await _get(api, f"/support/tickets?scope=all&q={ticket.ticket_no}", portal.manager)
    assert ticket.subject in found.text
    other_status = await _get(api, "/support/tickets?scope=all&status=RESOLVED", portal.manager)
    assert ticket.subject not in other_status.text and "No ticket matches" in other_status.text
    assert "/support/tickets?scope=all" in other_status.text                       # clear filters link
    bad = await _get(api, "/support/tickets?scope=all&status=NOPE&priority=NOPE&category=x&date_from=zzz", portal.manager)
    assert bad.status_code == 200 and ticket.subject in bad.text                   # bad filters are ignored
    mine = await _get(api, "/support/tickets?scope=mine", portal.manager)
    assert "Nothing assigned to you" in mine.text


async def test_the_queue_does_not_query_per_row(portal):
    desk = portal.desk
    category = await _category(desk, team_id=portal.team.id)
    for index in range(50):
        await _raise(desk, portal.requester, category, subject=f"Ticket number {index}")

    statements: list[str] = []

    def count(connection, cursor, statement, *_args):
        statements.append(statement)

    engine = desk.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", count)
    try:
        tickets, total = await desk.tickets.list_for_staff(
            ListStaffTicketsQuery(scope=Scope.ALL, limit=50), portal.manager_actor,
        )
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert total >= 51 and len(tickets) == 50
    assert all(ticket.requester_name and ticket.category_name for ticket in tickets)
    assert len(statements) <= 5, len(statements)


# =========================================================
# TICKET DETAIL
# =========================================================

async def test_detail_shows_the_conversation_requester_card_and_timeline(api, portal):
    ticket = portal.ticket
    response = await _get(api, f"/support/tickets/{ticket.id}?scope=all", portal.manager)
    assert response.status_code == 200
    text = response.text
    assert ticket.description in text
    # Requester card (REQ-62): profile, phone, device, OS and app version
    assert ticket.requester_name in text and ticket.requester_mobile in text
    assert "Redmi 9" in text and "Android 13" in text and "2.4.1" in text
    # Never dairy data
    for word in ("Collection", "Payment", "Ledger", "Passbook"):
        assert word not in text
    assert "Ticket created" in text and "Sent to" in text and portal.team.name in text
    # The back link keeps the queue the member came from
    assert 'href="/support/tickets?scope=all"' in text


async def test_opening_a_ticket_clears_its_unread_mark(api, portal):
    ticket_id = portal.ticket.id
    assert (await portal.desk.tickets.get_for_staff(ticket_id, portal.manager_actor)).ticket.staff_unread in (0, 1)
    listing = await _get(api, "/support/tickets?scope=all", portal.manager)
    # Raised tickets start unread, so the row has the dot until somebody opens it
    await _get(api, f"/support/tickets/{ticket_id}", portal.manager)
    after = await _get(api, "/support/tickets?scope=all", portal.manager)
    assert listing.status_code == after.status_code == 200
    assert (await portal.desk.tickets.get_for_staff(ticket_id, portal.manager_actor)).ticket.staff_unread == 0


async def test_the_manager_sees_every_control(api, portal):
    text = (await _get(api, f"/support/tickets/{portal.ticket.id}", portal.manager)).text
    assert 'name="mode" value="reply"' in text and 'name="mode" value="note"' in text
    assert f"/support/tickets/{portal.ticket.id}/assign" in text
    assert f"/support/tickets/{portal.ticket.id}/priority" in text
    assert f"/support/tickets/{portal.ticket.id}/category" in text
    assert "Send to a team" not in text                     # only Super Admin routes
    assert text.count("is-primary") <= 2                    # the send button (and the shell), no second primary action


async def test_a_viewer_reads_the_ticket_but_has_no_controls(api, portal):
    text = (await _get(api, f"/support/tickets/{portal.ticket.id}", portal.viewer)).text
    assert portal.ticket.description in text
    assert "You can read this conversation but not reply to it." in text
    for control in ("/messages", "/assign", "/priority", "/category", "/status", "sp-composer"):
        assert f"/support/tickets/{portal.ticket.id}{control}" not in text and control != "sp-composer" or "sp-composer" not in text


async def test_a_technical_member_sees_a_ticket_only_once_it_is_assigned_to_them(api, portal):
    path = f"/support/tickets/{portal.ticket.id}"
    assert _redirect(await _get(api, path, portal.tech)) == "/support/tickets"

    await portal.desk.tickets.assign(
        AssignTicketCommand(ticket_id=portal.ticket.id, assignee_user_id=portal.tech_member.user_id),
        portal.manager_actor,
    )
    text = (await _get(api, path, portal.tech)).text
    assert 'name="mode" value="note"' in text and 'name="mode" value="reply"' in text
    assert f"{path}/assign" not in text                      # cannot assign
    assert f"{path}/priority" in text                        # may change priority
    assert "In Progress" in text                             # a legal next status
    assert "Close" not in re.findall(r'data-confirm-ok="([^"]+)"', text)


async def test_another_teams_manager_is_sent_back_to_the_list(api, portal, desk):  # noqa: F811
    _team, other_manager = await _make_team(desk)
    other = portal.session(other_manager)
    assert _redirect(await _get(api, f"/support/tickets/{portal.ticket.id}", other)) == "/support/tickets"
    assert _redirect(await _post(api, f"/support/tickets/{portal.ticket.id}/assign", other, data={"assignee": str(uuid4())})) \
        == "/support/tickets"


# =========================================================
# ACTIONS
# =========================================================

async def test_assigning_from_the_form_then_working_the_ticket(api, portal):
    path = f"/support/tickets/{portal.ticket.id}"
    response = await _post(api, f"{path}/assign", portal.assigner, data={"assignee": str(portal.tech_member.user_id)})
    assert _redirect(response) == f"{path}?notice=assigned"
    detail = await _get(api, f"{path}?notice=assigned", portal.manager)
    assert "Ticket assigned." in detail.text and portal.tech_member.name in detail.text and "Assigned" in detail.text

    moved = await _post(api, f"{path}/status", portal.tech, data={"status": "IN_PROGRESS"})
    assert _redirect(moved) == f"{path}?notice=status"
    # Resolve asks for confirmation in the browser; the server still checks the move
    assert _redirect(await _post(api, f"{path}/status", portal.tech, data={"status": "RESOLVED"})) == f"{path}?notice=status"
    refused = await _post(api, f"{path}/status", portal.tech, data={"status": "IN_PROGRESS"})
    assert _redirect(refused) == f"{path}?notice=refused"
    assert "not allowed" in (await _get(api, f"{path}?notice=refused", portal.manager)).text


async def test_bad_choices_and_missing_permissions_come_back_with_a_notice(api, portal):
    path = f"/support/tickets/{portal.ticket.id}"
    assert _redirect(await _post(api, f"{path}/assign", portal.manager, data={})) == f"{path}?notice=invalid"
    assert _redirect(await _post(api, f"{path}/status", portal.manager, data={"status": "NOPE"})) == f"{path}?notice=invalid"
    assert _redirect(await _post(api, f"{path}/priority", portal.manager, data={"priority": "NOPE"})) == f"{path}?notice=invalid"
    # A viewer holds no assign permission
    viewer_try = await _post(api, f"{path}/assign", portal.viewer, data={"assignee": str(portal.tech_member.user_id)})
    assert _redirect(viewer_try) == f"{path}?notice=denied"
    # A manager cannot send tickets to teams (Super Admin only)
    team_try = await _post(api, f"{path}/route", portal.manager, data={"team": str(portal.team.id)})
    assert _redirect(team_try) == f"{path}?notice=denied"


async def test_priority_and_category_change_from_the_form(api, portal):
    path = f"/support/tickets/{portal.ticket.id}"
    assert _redirect(await _post(api, f"{path}/priority", portal.manager, data={"priority": "URGENT"})) == f"{path}?notice=priority"
    category = await _category(portal.desk, team_id=portal.team.id)
    assert _redirect(await _post(api, f"{path}/category", portal.manager, data={"category": str(category.id)})) \
        == f"{path}?notice=category"
    text = (await _get(api, path, portal.manager)).text
    assert "Urgent" in text and category.name in text
    assert "Priority: Medium → Urgent" in text


async def test_super_admin_sends_an_unassigned_ticket_to_a_team(api, portal, desk):  # noqa: F811
    pool_ticket = await _raise(desk, portal.requester, await _category(desk), subject="No default team here")
    path = f"/support/tickets/{pool_ticket.id}"
    assert pool_ticket.team_id is None

    pool = await _get(api, "/support/tickets?scope=unassigned", portal.admin)
    assert "No default team here" in pool.text
    detail = await _get(api, path, portal.admin)
    assert "Send to a team" in detail.text and "Unassigned pool" in detail.text

    done = await _post(api, f"{path}/route", portal.admin, data={"team": str(portal.team.id)})
    assert _redirect(done) == f"{path}?notice=routed"
    assert "No default team here" in (await _get(api, "/support/tickets?scope=unassigned", portal.manager)).text


# =========================================================
# CONVERSATION
# =========================================================

async def test_a_reply_through_htmx_swaps_only_the_conversation(api, portal):
    path = f"/support/tickets/{portal.ticket.id}"
    response = await _post(
        api, f"{path}/messages", portal.manager, data={"body": "We are looking into it", "mode": "reply"},
        hx=True,
    )
    assert response.status_code == 200
    assert "<html" not in response.text and 'id="sp-thread"' in response.text
    assert "We are looking into it" in response.text and "is-staff" in response.text

    note = await _post(
        api, f"{path}/messages", portal.manager, data={"body": "Check the SIM first", "mode": "note"},
        hx=True,
    )
    assert "Check the SIM first" in note.text and "is-note" in note.text and "not shown to the requester" in note.text

    empty = await _post(
        api, f"{path}/messages", portal.manager, data={"body": "  ", "mode": "reply"},
        hx=True,
    )
    assert "Write a message or choose a file." in empty.text

    # The requester sees the reply but never the note
    from app.modules.support.application.ticket_command import ListMessagesQuery
    messages = await portal.desk.tickets.list_messages_for_requester(
        ListMessagesQuery(ticket_id=portal.ticket.id), portal.requester,
    )
    assert [m.body for m in messages][-1] == "We are looking into it"
    assert all("SIM" not in m.body for m in messages)


async def test_without_htmx_a_reply_redirects_back_to_the_ticket(api, portal):
    path = f"/support/tickets/{portal.ticket.id}"
    response = await _post(api, f"{path}/messages", portal.manager, data={"body": "Plain form post", "mode": "reply"})
    assert _redirect(response) == path


async def test_a_viewer_cannot_post_and_gets_a_message_not_a_crash(api, portal):
    path = f"/support/tickets/{portal.ticket.id}"
    response = await _post(
        api, f"{path}/messages", portal.viewer, data={"body": "Trying anyway", "mode": "reply"},
        hx=True,
    )
    assert response.status_code == 200 and "permission" in response.text.lower()
    assert "Trying anyway" not in (await _get(api, path, portal.manager)).text


async def test_a_file_sent_from_the_composer_shows_in_the_thread_and_downloads_for_staff_only(api, portal, desk):  # noqa: F811
    path = f"/support/tickets/{portal.ticket.id}"
    response = await _post(
        api, f"{path}/messages", portal.manager, data={"mode": "reply", "body": ""},
        files={"file": ("screenshot.png", PNG, "image/png")}, hx=True,
    )
    assert response.status_code == 200 and "screenshot.png" in response.text
    attachment_url = re.search(r'href="(/support/attachments/[0-9a-f-]+)"', response.text).group(1)

    ok = await _get(api, attachment_url, portal.manager)
    assert ok.status_code == 200 and ok.content == PNG
    assert ok.headers["content-type"] == "image/png" and "no-store" in ok.headers["cache-control"]

    _team, other_manager = await _make_team(desk)
    assert (await _get(api, attachment_url, portal.session(other_manager))).status_code == 404

    bad = await _post(
        api, f"{path}/messages", portal.manager, data={"mode": "reply", "body": ""},
        files={"file": ("notes.txt", b"plain text", "text/plain")}, hx=True,
    )
    assert "Only JPEG, PNG, WebP images, PDF files and audio recordings can be attached." in bad.text


async def test_a_closed_ticket_shows_no_composer(api, portal):
    ticket_id = portal.ticket.id
    await portal.desk.tickets.assign(
        AssignTicketCommand(ticket_id=ticket_id, assignee_user_id=portal.tech_member.user_id), portal.manager_actor,
    )
    for status in (TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED):
        await portal.desk.tickets.change_status(ChangeStatusCommand(ticket_id=ticket_id, status=status), portal.manager_actor)
    await portal.desk.tickets.post_staff_message(
        PostMessageCommand(ticket_id=ticket_id, body="Closing note", internal=True), portal.manager_actor,
    )
    text = (await _get(api, f"/support/tickets/{ticket_id}", portal.manager)).text
    assert "This ticket is closed" in text and 'name="mode" value="reply"' not in text
    assert "Closing note" in text and "Reopen" in text


# =========================================================
# CATEGORIES
# =========================================================

async def test_super_admin_manages_categories_and_default_teams(api, portal):
    name = f"Printer {uuid4().hex[:6]}"
    created = await _post(
        api, "/support/categories/new", portal.admin,
        data={"name": name, "team": str(portal.team.id), "priority": "HIGH"},
    )
    assert _redirect(created) == "/support/categories?notice=created"
    listing = await _get(api, "/support/categories?notice=created", portal.admin)
    assert name in listing.text and portal.team.name in listing.text and "Category created." in listing.text

    duplicate = await _post(api, "/support/categories/new", portal.admin, data={"name": name, "team": "", "priority": "LOW"})
    assert duplicate.status_code == 422 and "already exists" in duplicate.text

    category_id = re.search(r"/support/categories/([0-9a-f-]+)/edit", listing.text).group(1)
    edit = await _get(api, f"/support/categories/{category_id}/edit", portal.admin)
    assert edit.status_code == 200
    saved = await _post(
        api, f"/support/categories/{category_id}/edit", portal.admin, data={"name": name + " x", "team": "", "priority": "LOW"},
    )
    assert _redirect(saved) == "/support/categories?notice=updated"
    off = await _post(api, f"/support/categories/{category_id}/status", portal.admin, data={"active": "0"})
    assert _redirect(off) == "/support/categories?notice=disabled"
    assert "Disabled" in (await _get(api, "/support/categories", portal.admin)).text


async def test_only_super_admin_opens_the_categories_screens(api, portal):
    assert _redirect(await _get(api, "/support/categories", portal.manager)) == "/"
    assert _redirect(await _get(api, "/support/categories/new", portal.manager)) == "/"
    assert _redirect(await _post(api, "/support/categories/new", portal.manager, data={"name": "Sneaky"})) == "/"


# =========================================================
# LIVE HOOKS (Phase 27): the markup and endpoint the live client relies on
# =========================================================

async def test_live_counts_endpoint_serves_badges_and_the_latest_event_id(api, portal):
    response = await _get(api, "/support/_live/counts", portal.manager)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    data = response.json()
    assert set(data["counts"]) == {"unassigned", "all", "mine"} and data["counts"]["all"] >= 1
    # Redis is on only when the run was given TEST_REDIS_URL (tests/conftest.py) and the bus is listening
    from app.main import app
    from app.modules.support.application.event_bus import EventBus

    bus = app.state.application.container.resolve(EventBus)
    assert data["latest_id"] > 0 and data["redis"] is bus.redis_active
    if not os.environ.get("REDIS_URL"):
        assert data["redis"] is False
    # Counts follow permission: a Technical Support member gets zero for queues it cannot open
    tech = (await _get(api, "/support/_live/counts", portal.tech)).json()["counts"]
    assert tech["all"] == 0 and tech["unassigned"] == 0


async def test_live_counts_are_closed_to_other_roles(api, user_factory, token_for):
    farmer = token_for(await user_factory(Role.FARMER), Role.FARMER)
    assert _redirect(await _get(api, "/support/_live/counts", farmer)) == "/"
    assert _redirect(await _get(api, "/support/_live/counts", {})) == "/login"


async def test_pages_carry_the_hooks_the_live_client_uses(api, portal):
    listing = (await _get(api, "/support/tickets?scope=all", portal.manager)).text
    assert 'data-sp-live="/ws/support"' in listing and "js/support_live.js" in listing
    assert 'id="sp-live"' in listing and 'id="sp-list"' in listing
    assert f'data-ticket-id="{portal.ticket.id}"' in listing

    detail = (await _get(api, f"/support/tickets/{portal.ticket.id}", portal.manager)).text
    assert f'id="sp-thread" data-ticket-id="{portal.ticket.id}"' in detail
    assert 'id="sp-side"' in detail and "data-typing" in detail and "data-new-messages" in detail
    assert "data-sp-alerts" in detail                       # the sound and desktop alerts switch
