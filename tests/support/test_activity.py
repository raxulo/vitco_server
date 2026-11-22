"""
My Activity, team activity and the audit screen (Plan 29.2, REQ-79, REQ-80, D-10), with seeded work
through the real handlers so every number has a known answer.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import event as sa_event

from app.modules.administration.domain.enums import Role
from app.modules.support.application.activity_query import ActivityQuery, period
from app.modules.support.application.call_handler import CallHandler
from app.modules.support.application.ticket_command import (
    AssignTicketCommand,
    ChangeStatusCommand,
    PostMessageCommand,
)
from app.modules.support.domain.enums import TicketStatus
from app.modules.support.domain.exceptions import (
    MemberNotFoundException,
    SupportPermissionDeniedException,
    SupportValidationException,
)
from app.modules.support.infrastructure.activity_repository import ActivityRepository
from tests.support.test_foundation import _make_member, _make_team, support  # noqa: F401
from tests.support.test_tickets import _category, _raise, _team_ticket, desk  # noqa: F401


@pytest.fixture
async def work(desk, token_for, user_factory):  # noqa: F811
    """One team and a known day of work:
    assigner hands 2 tickets to tech and moves 1 of them to caller; tech replies 3 times (first reply on
    both tickets), writes 1 note, resolves 1 ticket and makes 1 connected call; caller makes 1 busy call;
    the manager closes the resolved ticket.
    """
    from app.main import app

    container = app.state.application.container
    team, manager, first, requester = await _team_ticket(desk)
    category = await _category(desk, team_id=team.id)
    second = await _raise(desk, requester, category, subject="Second problem")
    tech, tech_actor = await _make_member(desk, manager, "Technical Support")
    assigner, assigner_actor = await _make_member(desk, manager, "Ticket Assigner")
    caller, caller_actor = await _make_member(desk, manager, "Caller")
    viewer, viewer_actor = await _make_member(desk, manager, "Viewer")
    t = desk.tickets
    calls = container.resolve(CallHandler)

    for ticket in (first, second):
        await t.assign(AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=tech.user_id), assigner_actor)
    await t.post_staff_message(PostMessageCommand(ticket_id=first.id, body="Looking"), tech_actor)
    await t.post_staff_message(PostMessageCommand(ticket_id=first.id, body="Update the app"), tech_actor)
    await t.post_staff_message(PostMessageCommand(ticket_id=second.id, body="Checking"), tech_actor)
    await t.post_staff_message(PostMessageCommand(ticket_id=first.id, body="Old build", internal=True), tech_actor)
    for status in (TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED):
        await t.change_status(ChangeStatusCommand(ticket_id=first.id, status=status), tech_actor)
    await t.change_status(ChangeStatusCommand(ticket_id=first.id, status=TicketStatus.CLOSED), manager)
    call, _ = await calls.start_call(second.id, tech_actor)
    await calls.finish_call(call.id, outcome="CONNECTED", duration_s=60, note=None, actor=tech_actor)
    await t.assign(AssignTicketCommand(ticket_id=second.id, assignee_user_id=caller.user_id), assigner_actor)
    call, _ = await calls.start_call(second.id, caller_actor)
    await calls.finish_call(call.id, outcome="BUSY", duration_s=None, note=None, actor=caller_actor)

    admin_id = await user_factory(Role.SUPER_ADMIN)
    from tests.support.test_foundation import _actor
    return SimpleNamespace(
        desk=desk, team=team, manager=manager, first=first, second=second,
        tech=tech, tech_actor=tech_actor, assigner=assigner, assigner_actor=assigner_actor,
        caller=caller, caller_actor=caller_actor, viewer=viewer, viewer_actor=viewer_actor,
        admin=_actor(admin_id, Role.SUPER_ADMIN), admin_session=token_for(admin_id, Role.SUPER_ADMIN),
        query=container.resolve(ActivityQuery), repository=container.resolve(ActivityRepository),
        session=lambda actor: token_for(actor.id, Role.SUPPORT),
    )


TODAY = period("today")


# =========================================================
# NUMBERS
# =========================================================

async def test_every_metric_matches_the_seeded_work(work):
    view = await work.query.member_activity(work.tech_actor, member_id=None, when=TODAY)
    n = view.numbers
    assert (n["assigned_to_me"], n["replies"], n["notes"], n["resolved"], n["closed"]) == (2, 3, 1, 1, 0)
    assert (n["calls"], n["calls_by_outcome"]) == (1, {"CONNECTED": 1})
    assert n["avg_first_reply_s"] is not None and n["avg_first_reply_s"] >= 0
    assert view.open_by_status == {}                      # first is closed, second went to the caller
    assert [e["ticket_no"] for e in view.recent][:1] == [work.second.ticket_no]

    assigner = (await work.query.member_activity(work.manager, member_id=work.assigner.id, when=TODAY)).numbers
    assert (assigner["assignments_made"], assigner["reassigned"]) == (3, 1)
    caller = (await work.query.member_activity(work.manager, member_id=work.caller.id, when=TODAY)).numbers
    assert (caller["assigned_to_me"], caller["calls_by_outcome"]) == (1, {"BUSY": 1})
    manager = (await work.query.member_activity(work.manager, member_id=None, when=TODAY)).numbers
    assert manager["closed"] == 1


async def test_the_day_wise_trend_adds_up_and_other_periods_include_today(work):
    view = await work.query.member_activity(work.tech_actor, member_id=None, when=TODAY)
    # 4 messages + 2 status moves + 1 call, all today
    assert view.trend == [(TODAY.start.date(), 7)]
    week = await work.query.member_activity(work.tech_actor, member_id=None, when=period("week"))
    assert len(week.trend) == 7 and sum(v for _, v in week.trend) == 7 and week.numbers["replies"] == 3


async def test_periods_and_their_validation():
    assert (period("month").end - period("month").start).days == 30
    assert period("nonsense").key == "week"
    custom = period("custom", "2026-01-01", "2026-01-31")
    assert len(custom.days) == 31
    for bad in (("", ""), ("2026-02-01", "2026-01-01"), ("2024-01-01", "2026-01-01")):
        with pytest.raises(SupportValidationException):
            period("custom", *bad)


async def test_cards_follow_the_role(work):
    def keys(view):
        return [card["key"] for card in view.cards]

    tech = await work.query.member_activity(work.tech_actor, member_id=None, when=TODAY)
    assert keys(tech) == ["assigned_to_me", "replies", "resolved", "notes", "calls"]
    assigner = await work.query.member_activity(work.assigner_actor, member_id=None, when=TODAY)
    assert keys(assigner) == ["notes", "assignments_made", "reassigned"]
    viewer = await work.query.member_activity(work.viewer_actor, member_id=None, when=TODAY)
    assert keys(viewer) == []
    manager = await work.query.member_activity(work.manager, member_id=None, when=TODAY)
    assert len(keys(manager)) == 8


async def test_scope_own_page_for_members_team_for_managers_all_for_super_admin(work):
    with pytest.raises(SupportPermissionDeniedException):
        await work.query.member_activity(work.tech_actor, member_id=work.caller.id, when=TODAY)
    _team, other_manager = await _make_team(work.desk)
    with pytest.raises(MemberNotFoundException):
        await work.query.member_activity(other_manager, member_id=work.tech.id, when=TODAY)
    seen = await work.query.member_activity(work.manager, member_id=work.tech.id, when=TODAY)
    assert seen.member.id == work.tech.id and seen.can_switch and len(seen.members) == 5
    assert (await work.query.member_activity(work.admin, member_id=work.tech.id, when=TODAY)).numbers["replies"] == 3

    with pytest.raises(SupportPermissionDeniedException):
        await work.query.team_activity(work.tech_actor, team_id=None, when=TODAY)
    table = await work.query.team_activity(work.manager, team_id=None, when=TODAY)
    assert table.totals["replies"] == 3 and table.totals["calls"] == 2 and table.totals["assignments_made"] == 3
    assert {row["member"].name for row in table.rows} == {
        work.tech.name, work.assigner.name, work.caller.name, work.viewer.name,
    } | {row["member"].name for row in table.rows if row["member"].is_manager}
    assert (await work.query.team_activity(work.admin, team_id=work.team.id, when=TODAY)).totals == table.totals


async def test_counting_costs_the_same_for_one_member_or_many(work):
    from app.main import app

    engine = app.state.application.container.database.engine.sync_engine
    members = [work.tech.user_id, work.assigner.user_id, work.caller.user_id, work.viewer.user_id, work.manager.id]

    async def statements(ids) -> int:
        seen: list[str] = []
        listener = lambda *args: seen.append(args[2])  # noqa: E731
        sa_event.listen(engine, "before_cursor_execute", listener)
        try:
            async with app.state.application.container.database.transaction():
                await work.repository.counts(ids, TODAY.start, TODAY.end)
        finally:
            sa_event.remove(engine, "before_cursor_execute", listener)
        return len(seen)

    assert await statements(members[:1]) == await statements(members) <= 10


# =========================================================
# SCREENS
# =========================================================

async def test_my_activity_page_shows_the_cards_chart_and_recent_actions(api, work):
    text = (await api.get("/support/activity?period=today", headers=work.session(work.tech_actor))).text
    for expected in ("My activity", "Replies sent", "Average first reply", "Actions per day", work.second.ticket_no,
                     "Resolved", "Calls by outcome", "Connected"):
        assert expected in text, expected
    assert "<svg class=\"sp-chart\"" in text and "<caption>Actions per day</caption>" in text
    assert "sp-member" not in text                            # no member picker for a regular member


async def test_a_viewer_gets_an_honest_empty_state(api, work):
    text = (await api.get("/support/activity", headers=work.session(work.viewer_actor))).text
    assert "Nothing to count for this role" in text


async def test_members_cannot_open_others_pages_or_the_team_table(api, work):
    other = await api.get(f"/support/activity?member={work.caller.id}", headers=work.session(work.tech_actor), follow_redirects=False)
    assert other.headers.get("location") == "/support/activity"
    team = await api.get("/support/activity/team", headers=work.session(work.tech_actor), follow_redirects=False)
    assert team.headers.get("location") == "/"


async def test_the_manager_compares_the_team_and_opens_a_member(api, work):
    text = (await api.get("/support/activity/team?period=today&sort=calls", headers=work.session(work.manager))).text
    assert "Team activity" in text and "Team total" in text
    for name in (work.tech.name, work.assigner.name, work.caller.name):
        assert name in text
    assert text.index(work.tech.name) < text.index(work.viewer.name)       # sorted by calls, most first
    member = await api.get(f"/support/activity?member={work.tech.id}&period=today", headers=work.session(work.manager))
    assert f"Activity of {work.tech.name}" in member.text and "sp-member" in member.text


async def test_the_sidebar_shows_insights_by_role(api, work):
    import re

    def nav(text):
        sidebar = text.split('<nav class="sp-nav">', 1)[1].split("</nav>", 1)[0]
        return set(re.findall(r"<span>([^<]+)</span>", sidebar))

    tech = nav((await api.get("/support", headers=work.session(work.tech_actor))).text)
    assert "My activity" in tech and "Team activity" not in tech and "Audit log" not in tech
    manager = nav((await api.get("/support", headers=work.session(work.manager))).text)
    assert {"My activity", "Team activity", "Audit log"} <= manager
    admin = nav((await api.get("/support", headers=work.admin_session)).text)
    assert {"Team activity", "Audit log"} <= admin and "My activity" not in admin


async def test_home_shows_todays_numbers(api, work):
    text = (await api.get("/support", headers=work.session(work.tech_actor))).text
    assert "Today" in text and "Replies sent" in text and "My open tickets" in text
    admin = (await api.get("/support", headers=work.admin_session)).text
    assert "Open tickets" in admin and "Tickets arrive in the next phase" not in admin


async def test_audit_log_reads_like_sentences_and_is_scoped(api, work):
    page = (await api.get("/support/audit", headers=work.session(work.manager))).text
    assert f"assigned {work.first.ticket_no} to {work.tech.name}" in page
    assert f"moved {work.first.ticket_no} from Resolved to Closed" in page
    assert f"recorded a call on {work.second.ticket_no}: Busy" in page
    assert "Read-only" in page

    only_calls = (await api.get("/support/audit?action=call.logged", headers=work.session(work.manager))).text
    assert "recorded a call" in only_calls and f"assigned {work.first.ticket_no}" not in only_calls
    one_ticket = (await api.get(f"/support/audit?ticket={work.first.id}", headers=work.session(work.manager))).text
    assert work.first.ticket_no in one_ticket and f"on {work.second.ticket_no}" not in one_ticket

    # Members cannot open it; another team's manager does not see this team's rows
    assert (await api.get("/support/audit", headers=work.session(work.tech_actor), follow_redirects=False)).headers["location"] == "/"
    _team, other_manager = await _make_team(work.desk)
    other = (await api.get("/support/audit", headers=work.session(other_manager))).text
    assert work.first.ticket_no not in other
    # Super Admin sees every team
    assert work.first.ticket_no in (await api.get("/support/audit", headers=work.admin_session)).text
