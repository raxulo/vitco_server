"""
Technical Support realtime (Plan 27.1, REQ-73 to REQ-75, DECISION-032).

The audience rules are tested as pure functions; the bus and the socket endpoints run against the
real handlers, with a stand-in socket object (no network) and with Redis off, down and faked.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.v1.routers import support_ws
from app.infrastructure.redis_client import RedisClient
from app.modules.administration.domain.enums import Role
from app.modules.support.application.audience import Subscriber, can_receive
from app.modules.support.application.event_bus import EventBus
from app.modules.support.application.events import MESSAGE_CREATED, NOTE_CREATED, TICKET_CREATED, TICKET_UPDATED, TYPING, SupportEvent
from app.modules.support.application.hub import SocketHub
from app.modules.support.application.ticket_command import (
    AssignTicketCommand,
    ChangePriorityCommand,
    PostMessageCommand,
)
from app.modules.support.domain.enums import TicketPriority
from app.modules.support.domain.permissions import SupportPermission as P
from tests.support.test_foundation import _make_member, _make_team, support  # noqa: F401
from tests.support.test_tickets import _category, _raise, _team_ticket, desk  # noqa: F401


# =========================================================
# AUDIENCE (no database)
# =========================================================

TEAM, OTHER_TEAM = uuid4(), uuid4()
ME, REQ = uuid4(), uuid4()


def _event(**overrides) -> SupportEvent:
    values = dict(type=TICKET_UPDATED, ticket_id=str(uuid4()), team_id=str(TEAM), requester_id=str(REQ),
                  assigned_to=None, public=True)
    values.update(overrides)
    return SupportEvent(**values)


def _staff(*permissions, team=TEAM, user=ME, super_admin=False) -> Subscriber:
    return Subscriber(user_id=user, team_id=team, permissions=frozenset(permissions), is_super_admin=super_admin)


def test_requester_hears_only_public_events_of_own_tickets():
    me = Subscriber.requester(REQ)
    assert can_receive(me, _event())
    assert not can_receive(me, _event(public=False))
    assert not can_receive(me, _event(requester_id=str(uuid4())))


def test_super_admin_hears_everything_including_the_pool():
    admin = _staff(super_admin=True, team=None)
    assert can_receive(admin, _event()) and can_receive(admin, _event(team_id=None, public=False))


def test_team_staff_never_hear_other_teams_or_the_pool():
    manager_like = _staff(P.TICKET_VIEW_ALL)
    assert not can_receive(manager_like, _event(team_id=str(OTHER_TEAM)))
    assert not can_receive(manager_like, _event(team_id=None))


def test_view_all_hears_the_whole_team_and_staff_only_events():
    assert can_receive(_staff(P.TICKET_VIEW_ALL), _event(public=False, assigned_to=str(uuid4())))


def test_view_assigned_hears_only_tickets_assigned_to_them_or_just_taken_from_them():
    worker = _staff(P.TICKET_VIEW_ASSIGNED)
    assert not can_receive(worker, _event(assigned_to=str(uuid4())))
    assert not can_receive(worker, _event())
    assert can_receive(worker, _event(assigned_to=str(ME)))
    assert can_receive(worker, _event(assigned_to=str(uuid4()), previous_assignee=str(ME)))


def test_ticket_assigner_hears_unassigned_tickets_only():
    assigner = _staff(P.TICKET_ASSIGN)
    assert can_receive(assigner, _event(assigned_to=None))
    assert not can_receive(assigner, _event(assigned_to=str(uuid4())))


def test_a_member_with_no_ticket_permission_hears_nothing():
    assert not can_receive(_staff(P.CALL_MAKE), _event())
    assert not can_receive(_staff(P.TICKET_VIEW_ALL, team=None), _event())


def test_requester_payload_hides_staff_details():
    event = _event(assigned_to=str(uuid4()), data={"change": "status", "status": "RESOLVED", "secret": "x"})
    payload = event.for_requester()
    assert "assigned_to" not in payload and "team_id" not in payload and "secret" not in payload["data"]
    assert payload["data"] == {"change": "status", "status": "RESOLVED", "status_label": "Resolved"}
    # An internal status reaches the app with the app's own words, as in the REST API
    escalated = _event(data={"change": "status", "status": "ESCALATED"}).for_requester()
    assert escalated["data"]["status_label"] == "In progress"


# =========================================================
# BUS
# =========================================================

async def test_events_are_delivered_in_process_with_increasing_ids_when_redis_is_off():
    bus = EventBus(RedisClient(""))
    received: list[SupportEvent] = []
    bus.subscribe(received.append)
    first = await bus.publish(_event())
    second = await bus.publish(_event())
    assert [e.id for e in received] == [first.id, second.id] and second.id > first.id
    assert bus.latest_id == second.id


async def test_replay_returns_what_was_missed_or_asks_for_a_reload():
    bus = EventBus(RedisClient(""), buffer=10)
    ids = [(await bus.publish(_event())).id for _ in range(3)]
    events, complete = bus.replay(ids[0])
    assert complete and [e.id for e in events] == ids[1:]
    assert bus.replay(ids[-1]) == ([], True)
    # An id from before the buffer, or from a previous run, cannot be replayed
    for _ in range(30):
        await bus.publish(_event())
    assert bus.replay(ids[0])[1] is False
    assert EventBus(RedisClient("")).replay(5) == ([], False)


async def test_typing_is_never_stored_or_replayed():
    bus = EventBus(RedisClient(""))
    seen = []
    bus.subscribe(seen.append)
    typing = await bus.publish(_event(type=TYPING))
    assert typing.id == 0 and seen == [typing] and bus.replay(0) == ([], False)


async def test_events_wait_for_the_commit_and_vanish_on_rollback(desk):  # noqa: F811
    bus = EventBus(RedisClient(""))
    seen: list[SupportEvent] = []
    bus.subscribe(seen.append)

    async with desk.database.transaction() as session:
        bus.after_commit(session, _event(type=MESSAGE_CREATED))
        await asyncio.sleep(0.05)
        assert seen == []                                   # not before the commit
    await asyncio.sleep(0.05)
    assert [e.type for e in seen] == [MESSAGE_CREATED]

    seen.clear()
    with pytest.raises(RuntimeError):
        async with desk.database.transaction() as session:
            bus.after_commit(session, _event(type=NOTE_CREATED))
            raise RuntimeError("boom")
    await asyncio.sleep(0.05)
    assert seen == []                                       # rolled back: nothing was sent


async def test_a_redis_server_that_is_down_never_breaks_publishing():
    bus = EventBus(RedisClient("redis://127.0.0.1:1/0"))
    seen = []
    bus.subscribe(seen.append)
    await bus.start()
    try:
        await asyncio.sleep(0.2)
        event = await asyncio.wait_for(bus.publish(_event()), timeout=5)
        assert seen == [event] and event.id > 0
        assert bus.redis_active is False
    finally:
        await bus.stop()


class FakeRedis(RedisClient):
    """In-memory Redis: one shared channel and counter, like a single real server."""

    def __init__(self) -> None:
        super().__init__("redis://fake")
        self.counter = 0
        self.channels: list[asyncio.Queue] = []
        self.keys: dict[str, str] = {}

    @property
    def healthy(self) -> bool:
        return True

    async def publish(self, channel, message):
        for queue in self.channels:
            queue.put_nowait({"type": "message", "data": message})
        return True

    async def incr(self, key):
        await asyncio.sleep(0)                  # a network round trip: other publishers may run meanwhile
        self.counter += 1
        return self.counter

    async def incr_at_least(self, key, floor):
        await asyncio.sleep(0)
        self.counter = max(self.counter + 1, int(floor))
        return self.counter

    async def set(self, key, value, *, ex=None):
        self.keys[key] = value
        return True

    async def delete(self, key):
        self.keys.pop(key, None)

    async def exists(self, key):
        return key in self.keys

    def pubsub(self):
        fake = self

        class _PubSub:
            def __init__(self):
                self.queue = asyncio.Queue()

            async def subscribe(self, _channel):
                fake.channels.append(self.queue)

            async def listen(self):
                while True:
                    yield await self.queue.get()

            async def aclose(self):
                fake.channels.remove(self.queue)

        return _PubSub()


async def test_two_processes_sharing_redis_both_receive_every_event_once():
    redis = FakeRedis()
    first, second = EventBus(redis), EventBus(redis)
    got_first, got_second = [], []
    first.subscribe(got_first.append)
    second.subscribe(got_second.append)
    await first.start()
    await second.start()
    try:
        await asyncio.sleep(0.1)
        assert first.redis_active and second.redis_active
        sent = await first.publish(_event())
        await asyncio.sleep(0.1)
        assert [e.id for e in got_first] == [sent.id] == [e.id for e in got_second]
        again = await second.publish(_event())
        assert again.id > sent.id
    finally:
        await first.stop()
        await second.stop()


async def test_ids_stay_unique_and_rising_when_many_publish_at_once_through_redis():
    """Like a real Redis, the counter starts at 0, far below the time-based local ids."""
    redis = FakeRedis()
    first, second = EventBus(redis), EventBus(redis)
    await first.start()
    await second.start()
    try:
        await asyncio.sleep(0.1)
        start = max(first.latest_id, second.latest_id)
        sent = await asyncio.gather(*[(first if i % 2 else second).publish(_event()) for i in range(40)])
        ids = [event.id for event in sent]
        assert len(set(ids)) == 40, "two events shared an id"
        assert min(ids) > start
        assert redis.counter == max(ids)        # the shared counter moved with them
        later = await first.publish(_event())
        assert later.id > max(ids)
    finally:
        await first.stop()
        await second.stop()


async def test_a_real_redis_counter_is_lifted_above_the_local_ids():
    """The atomic script, against a Redis that has a small counter left from earlier runs."""
    import os

    url = os.environ.get("REDIS_URL", "")
    if not url:
        pytest.skip("needs TEST_REDIS_URL")
    client = RedisClient(url)
    key = f"support:test_counter:{uuid4().hex}"
    try:
        assert await client.set(key, "3")
        floor = 1_795_000_000_000
        assert await client.incr_at_least(key, floor) == floor
        assert await client.incr_at_least(key, floor) == floor + 1   # never repeats
        assert await client.incr_at_least(key, 10) == floor + 2      # a low floor still rises
    finally:
        await client.delete(key)
        await client.close()


async def test_presence_uses_sockets_here_and_redis_for_other_processes():
    redis = FakeRedis()
    hub = SocketHub(max_connections=5, redis=redis)
    user = uuid4()
    assert not await hub.is_online_anywhere(user)
    await hub.touch(user)
    assert await hub.is_online_anywhere(user) and not hub.is_online(user)
    await hub.drop_presence(user)
    assert not await hub.is_online_anywhere(user)


# =========================================================
# SOCKET ENDPOINTS (stand-in socket, real handlers)
# =========================================================

class FakeSocket:
    """What `_serve` needs from a WebSocket, driven from the test."""

    def __init__(self, app, *, headers=None, cookies=None):
        self.app = app
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.query_params: dict = {}
        self.incoming: asyncio.Queue = asyncio.Queue()
        self.outgoing: asyncio.Queue = asyncio.Queue()
        self.close_code: int | None = None
        self.accepted = False
        self.task: asyncio.Task | None = None

    async def accept(self):
        self.accepted = True

    async def receive_json(self):
        item = await self.incoming.get()
        if item is None:
            raise WebSocketDisconnect(1000)
        return item

    async def send_json(self, message):
        self.outgoing.put_nowait(message)

    async def close(self, code=1000):
        if self.close_code is None:
            self.close_code = code
        self.incoming.put_nowait(None)

    # --- test helpers
    def start(self, kind: str):
        self.task = asyncio.create_task(support_ws._serve(self, kind))
        return self

    def say(self, message: dict):
        self.incoming.put_nowait(message)

    async def hear(self, timeout: float = 2.0) -> dict:
        return await asyncio.wait_for(self.outgoing.get(), timeout)

    async def hear_type(self, kind: str, timeout: float = 2.0) -> dict:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            message = await self.hear(max(0.05, deadline - asyncio.get_running_loop().time()))
            if message["type"] == kind:
                return message

    async def heard(self, wait: float = 0.4) -> list[dict]:
        """Everything that arrives in the next moments."""
        await asyncio.sleep(wait)
        items = []
        while not self.outgoing.empty():
            items.append(self.outgoing.get_nowait())
        return items

    async def stop(self):
        self.incoming.put_nowait(None)
        if self.task:
            await asyncio.wait_for(self.task, 3)


def _token(headers: dict[str, str]) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


@pytest.fixture
async def live(desk, token_for):  # noqa: F811
    from app.main import app

    team, manager, ticket, requester = await _team_ticket(desk)
    tech, tech_actor = await _make_member(desk, manager, "Technical Support")
    viewer, viewer_actor = await _make_member(desk, manager, "Viewer")
    other_team, other_manager = await _make_team(desk)
    sockets: list[FakeSocket] = []

    async def open_socket(actor, kind="staff", role=Role.SUPPORT, *, last_event_id=0, **kwargs):
        socket = FakeSocket(app, **kwargs).start(kind)
        socket.say({"type": "auth", "token": _token(token_for(actor.id, role)), "last_event_id": last_event_id})
        sockets.append(socket)
        hello = await socket.hear_type("hello")
        return socket, hello

    yield SimpleNamespace(
        desk=desk, app=app, team=team, manager=manager, ticket=ticket, requester=requester,
        tech=tech, tech_actor=tech_actor, viewer_actor=viewer_actor, other_manager=other_manager,
        open=open_socket, token_for=token_for, sockets=sockets, hub=app.state.application.container.resolve(SocketHub),
    )
    for socket in sockets:
        try:
            await socket.stop()
        except Exception:
            pass


async def test_hello_carries_the_latest_event_id(live):
    socket, hello = await live.open(live.manager)
    assert hello["type"] == "hello" and hello["latest_id"] > 0 and hello["resync"] is False
    assert len(live.hub) >= 1


async def test_bad_or_missing_tokens_and_wrong_socket_kinds_are_closed(live, monkeypatch):
    from app.main import app

    bad = FakeSocket(app).start("staff")
    bad.say({"type": "auth", "token": "not-a-token"})
    await asyncio.wait_for(bad.task, 3)
    assert bad.close_code == support_ws.UNAUTHORIZED

    silent = FakeSocket(app)
    monkeypatch.setattr(support_ws, "connection_config", SimpleNamespace(authentication_timeout=0.2, max_connections=10))
    await asyncio.wait_for(silent.start("staff").task, 3)
    assert silent.close_code == support_ws.UNAUTHORIZED
    monkeypatch.undo()

    wrong_first = FakeSocket(app).start("staff")
    wrong_first.say({"type": "hello"})
    await asyncio.wait_for(wrong_first.task, 3)
    assert wrong_first.close_code == support_ws.UNAUTHORIZED

    # The requester endpoint refuses staff, the staff endpoint refuses requesters
    staff_on_app = FakeSocket(app).start("app")
    staff_on_app.say({"type": "auth", "token": _token(live.token_for(live.manager.id, Role.SUPPORT))})
    await asyncio.wait_for(staff_on_app.task, 3)
    assert staff_on_app.close_code == support_ws.FORBIDDEN

    requester_on_staff = FakeSocket(app).start("staff")
    requester_on_staff.say({"type": "auth", "token": _token(live.token_for(live.requester.id, Role.FARMER))})
    await asyncio.wait_for(requester_on_staff.task, 3)
    assert requester_on_staff.close_code == support_ws.FORBIDDEN


async def test_a_cookie_from_another_origin_is_not_accepted(live, monkeypatch):
    from app.main import app

    token = _token(live.token_for(live.manager.id, Role.SUPPORT))
    real = support_ws.connection_config
    monkeypatch.setattr(support_ws, "connection_config", SimpleNamespace(authentication_timeout=0.3, max_connections=real.max_connections))
    foreign = FakeSocket(app, cookies={"access_token": token}, headers={"origin": "http://evil.example", "host": "app.example"})
    foreign.start("staff")
    await asyncio.wait_for(foreign.task, 5)         # the cookie is ignored, so it waits for an auth message and times out
    assert foreign.close_code == support_ws.UNAUTHORIZED
    monkeypatch.undo()

    same = FakeSocket(app, cookies={"access_token": token}, headers={"origin": "http://app.example", "host": "app.example"})
    same.start("staff")
    assert (await same.hear_type("hello"))["type"] == "hello"
    live.sockets.append(same)


async def test_a_new_ticket_reaches_exactly_the_people_who_may_see_it(live):
    manager, _ = await live.open(live.manager)
    viewer, _ = await live.open(live.viewer_actor)
    tech, _ = await live.open(live.tech_actor)
    stranger, _ = await live.open(live.other_manager)
    app_socket, _ = await live.open(
        type("A", (), {"id": live.requester.id}), kind="app", role=Role.FARMER,
    )

    category = await _category(live.desk, team_id=live.team.id)
    ticket = await _raise(live.desk, live.requester, category, subject="Brand new problem")

    for socket in (manager, viewer):
        message = await socket.hear_type("event")
        assert message["event"]["type"] == TICKET_CREATED and message["event"]["ticket_id"] == str(ticket.id)
    # Technical Support sees only assigned tickets; another team hears nothing
    assert [m for m in await tech.heard() if m["type"] == "event"] == []
    assert [m for m in await stranger.heard(0.1) if m["type"] == "event"] == []
    # The requester's own socket hears its ticket, without any staff field
    own = await app_socket.hear_type("event")
    assert own["event"]["type"] == TICKET_CREATED and "team_id" not in own["event"] and "assigned_to" not in own["event"]


async def test_assignment_moves_the_ticket_between_audiences(live):
    tech, _ = await live.open(live.tech_actor)
    app_socket, _ = await live.open(type("A", (), {"id": live.requester.id}), kind="app", role=Role.FARMER)

    await live.desk.tickets.assign(
        AssignTicketCommand(ticket_id=live.ticket.id, assignee_user_id=live.tech.user_id), live.manager,
    )
    update = await tech.hear_type("event")
    assert update["event"]["data"]["change"] == "assigned" and update["event"]["assigned_to"] == str(live.tech.user_id)
    # ...and the status move that comes with it (it names the new assignee)
    moved = await tech.hear_type("event")
    assert moved["event"]["data"] == {"change": "status", "status": "ASSIGNED"}

    # The requester learns of the status change but not of who got the ticket
    heard = [m["event"] for m in await app_socket.heard() if m["type"] == "event"]
    assert [e["data"].get("change") for e in heard] == ["status"]
    assert heard[0]["data"]["status"] == "ASSIGNED"

    # Reassigning away from the member still tells them once, so their list drops the row
    other, other_actor = await _make_member(live.desk, live.manager, "Technical Support")
    await live.desk.tickets.assign(
        AssignTicketCommand(ticket_id=live.ticket.id, assignee_user_id=other.user_id), live.manager,
    )
    gone = await tech.hear_type("event")
    assert gone["event"]["previous_assignee"] == str(live.tech.user_id)


async def test_internal_notes_and_priority_changes_never_reach_the_requester(live):
    manager, _ = await live.open(live.manager)
    app_socket, _ = await live.open(type("A", (), {"id": live.requester.id}), kind="app", role=Role.FARMER)

    await live.desk.tickets.post_staff_message(
        PostMessageCommand(ticket_id=live.ticket.id, body="Secret note", internal=True), live.manager,
    )
    await live.desk.tickets.change_priority(
        ChangePriorityCommand(ticket_id=live.ticket.id, priority=TicketPriority.URGENT), live.manager,
    )
    await live.desk.tickets.post_staff_message(PostMessageCommand(ticket_id=live.ticket.id, body="Public reply"), live.manager)

    types_for_staff = [m["event"]["type"] for m in await manager.heard() if m["type"] == "event"]
    assert types_for_staff == [NOTE_CREATED, TICKET_UPDATED, MESSAGE_CREATED]
    types_for_app = [m["event"]["type"] for m in await app_socket.heard() if m["type"] == "event"]
    assert types_for_app == [MESSAGE_CREATED]


async def test_nothing_is_sent_for_work_that_failed(live):
    manager, _ = await live.open(live.manager)
    with pytest.raises(Exception):
        await live.desk.tickets.post_staff_message(PostMessageCommand(ticket_id=live.ticket.id, body="x"), live.viewer_actor)
    assert [m for m in await manager.heard() if m["type"] == "event"] == []


async def test_reconnecting_replays_what_was_missed_and_filters_it(live):
    socket, hello = await live.open(live.manager)
    seen = hello["latest_id"]
    await socket.stop()

    await live.desk.tickets.post_staff_message(PostMessageCommand(ticket_id=live.ticket.id, body="While away"), live.manager)
    await live.desk.tickets.post_staff_message(
        PostMessageCommand(ticket_id=live.ticket.id, body="Note while away", internal=True), live.manager,
    )
    await asyncio.sleep(0.1)

    again, hello = await live.open(live.manager, last_event_id=seen)
    assert hello["resync"] is False
    replayed = [await again.hear_type("event") for _ in range(2)]
    assert [m["event"]["type"] for m in replayed] == [MESSAGE_CREATED, NOTE_CREATED]

    # A requester replaying the same range gets only the public message
    app_socket, _ = await live.open(type("A", (), {"id": live.requester.id}), kind="app", role=Role.FARMER, last_event_id=seen)
    assert [m["event"]["type"] for m in await app_socket.heard() if m["type"] == "event"] == [MESSAGE_CREATED]

    # An id the server cannot replay asks for a reload
    _stale, hello = await live.open(live.manager, last_event_id=1)
    assert hello["resync"] is True


async def test_typing_reaches_the_other_side_but_not_the_sender_and_notes_stay_private(live):
    await live.desk.tickets.assign(
        AssignTicketCommand(ticket_id=live.ticket.id, assignee_user_id=live.tech.user_id), live.manager,
    )
    manager, _ = await live.open(live.manager)
    tech, _ = await live.open(live.tech_actor)
    app_socket, _ = await live.open(type("A", (), {"id": live.requester.id}), kind="app", role=Role.FARMER)
    await asyncio.sleep(0.3)
    for socket in (manager, tech, app_socket):
        await socket.heard(0.05)

    tech.say({"type": "typing", "ticket_id": str(live.ticket.id)})
    assert (await manager.hear_type("typing"))["event"]["data"]["typing"] is True
    assert (await app_socket.hear_type("typing"))["event"]["data"] == {"typing": True}
    assert [m for m in await tech.heard(0.2) if m["type"] == "typing"] == []

    tech.say({"type": "typing", "ticket_id": str(live.ticket.id), "note": True})
    assert (await manager.hear_type("typing"))["type"] == "typing"
    assert [m for m in await app_socket.heard(0.3) if m["type"] == "typing"] == []

    app_socket.say({"type": "typing", "ticket_id": str(uuid4())})
    assert (await app_socket.hear_type("error"))["error"] == "not_found"
    outsider, _ = await live.open(live.other_manager)
    outsider.say({"type": "typing", "ticket_id": str(live.ticket.id)})
    assert (await outsider.hear_type("error"))["error"] == "not_found"


async def test_read_clears_the_unread_mark_from_either_side(live):
    await live.desk.tickets.post_staff_message(PostMessageCommand(ticket_id=live.ticket.id, body="Please check"), live.manager)
    manager, _ = await live.open(live.manager)
    app_socket, _ = await live.open(type("A", (), {"id": live.requester.id}), kind="app", role=Role.FARMER)

    app_socket.say({"type": "read", "ticket_id": str(live.ticket.id)})
    manager.say({"type": "read", "ticket_id": str(live.ticket.id)})
    await asyncio.sleep(0.4)
    ticket = await live.desk.tickets.get_for_requester(live.ticket.id, live.requester)
    assert ticket.ticket.requester_unread == 0
    assert (await live.desk.tickets.get_for_staff(live.ticket.id, live.manager)).ticket.staff_unread == 0


async def test_live_chat_between_two_staff_and_a_requester(live):
    manager, _ = await live.open(live.manager)
    viewer, _ = await live.open(live.viewer_actor)
    app_socket, _ = await live.open(type("A", (), {"id": live.requester.id}), kind="app", role=Role.FARMER)

    await live.desk.tickets.post_requester_message(PostMessageCommand(ticket_id=live.ticket.id, body="Hello?"), live.requester)
    for socket in (manager, viewer):
        assert (await socket.hear_type("event"))["event"]["type"] == MESSAGE_CREATED
    await live.desk.tickets.post_staff_message(PostMessageCommand(ticket_id=live.ticket.id, body="Hi, how can we help?"), live.manager)
    assert (await app_socket.hear_type("event"))["event"]["type"] == MESSAGE_CREATED
    assert (await viewer.hear_type("event"))["event"]["type"] == MESSAGE_CREATED


async def test_the_connection_limit_closes_with_try_again_later(live, monkeypatch):
    from app.main import app

    monkeypatch.setattr(live.hub, "_max", len(live.hub))
    full = FakeSocket(app).start("staff")
    full.say({"type": "auth", "token": _token(live.token_for(live.manager.id, Role.SUPPORT))})
    await asyncio.wait_for(full.task, 3)
    assert full.close_code == support_ws.BUSY


async def test_a_disabled_member_cannot_open_a_socket(live):
    from app.modules.support.application.command import SetMemberActiveCommand
    from app.modules.support.application.handler import SupportMemberHandler

    members = live.app.state.application.container.resolve(SupportMemberHandler)
    await members.set_active(SetMemberActiveCommand(member_id=live.tech.id, is_active=False), live.manager)
    socket = FakeSocket(live.app).start("staff")
    socket.say({"type": "auth", "token": _token(live.token_for(live.tech.user_id, Role.SUPPORT))})
    await asyncio.wait_for(socket.task, 3)
    assert socket.close_code in (support_ws.UNAUTHORIZED, support_ws.FORBIDDEN)


async def test_an_open_socket_is_closed_once_its_member_is_disabled(live, monkeypatch):
    from app.modules.support.application.command import SetMemberActiveCommand
    from app.modules.support.application.handler import SupportMemberHandler

    monkeypatch.setattr(support_ws, "ACCESS_RECHECK_S", 0.1)
    socket, _hello = await live.open(live.tech_actor)
    members = live.app.state.application.container.resolve(SupportMemberHandler)
    await members.set_active(SetMemberActiveCommand(member_id=live.tech.id, is_active=False), live.manager)
    await asyncio.wait_for(socket.task, 3)
    assert socket.close_code == support_ws.FORBIDDEN


async def test_an_open_socket_follows_a_role_change(live, monkeypatch):
    """A Viewer (view_all) moved to Technical Support (assigned only) stops hearing new team tickets."""
    from app.modules.support.application.command import UpdateMemberCommand
    from app.modules.support.application.handler import SupportMemberHandler
    from tests.support.test_foundation import _role_id

    monkeypatch.setattr(support_ws, "ACCESS_RECHECK_S", 0.1)
    viewer, viewer_actor = await _make_member(live.desk, live.manager, "Viewer")
    socket, _hello = await live.open(viewer_actor)
    category = await _category(live.desk, team_id=live.team.id)
    before = await _raise(live.desk, live.requester, category)
    assert any(item.get("event", {}).get("ticket_id") == str(before.id) for item in await socket.heard(0.4))

    members = live.app.state.application.container.resolve(SupportMemberHandler)
    await members.update_member(
        UpdateMemberCommand(member_id=viewer.id, role_id=await _role_id(live.desk, live.manager, "Technical Support")),
        live.manager,
    )
    await asyncio.sleep(0.4)                                  # the next access check picks it up
    after = await _raise(live.desk, live.requester, category)
    heard = await socket.heard(0.5)
    assert not any(item.get("event", {}).get("ticket_id") == str(after.id) for item in heard)
    assert socket.close_code is None                          # still signed in, only hears less


async def test_the_new_assignee_hears_the_status_move_that_comes_with_the_assignment(live):
    from app.modules.support.application.ticket_command import AssignTicketCommand

    category = await _category(live.desk, team_id=live.team.id)
    ticket = await _raise(live.desk, live.requester, category)
    socket, _hello = await live.open(live.tech_actor)               # view_assigned only
    await live.desk.tickets.assign(
        AssignTicketCommand(ticket_id=ticket.id, assignee_user_id=live.tech.user_id), live.manager,
    )
    changes = [
        item["event"]["data"] for item in await socket.heard(0.5)
        if item["type"] == "event" and item["event"]["ticket_id"] == str(ticket.id)
    ]
    assert {"change": "assigned"} in changes
    assert {"change": "status", "status": "ASSIGNED"} in changes


async def test_a_socket_signed_in_by_header_resumes_from_its_last_event(live):
    category = await _category(live.desk, team_id=live.team.id)
    first = await _raise(live.desk, live.requester, category)
    await asyncio.sleep(0.2)
    bus = live.app.state.application.container.resolve(EventBus)
    seen_id = bus.latest_id
    missed = await _raise(live.desk, live.requester, category)
    await asyncio.sleep(0.2)

    socket = FakeSocket(live.app, headers={"authorization": f"Bearer {_token(live.token_for(live.manager.id, Role.SUPPORT))}"})
    socket.query_params = {"last_event_id": str(seen_id)}
    socket.start("staff")
    live.sockets.append(socket)
    hello = await socket.hear_type("hello")
    replayed = [item for item in await socket.heard(0.4) if item["type"] == "event"]
    assert hello["resync"] is False
    ticket_ids = {item["event"]["ticket_id"] for item in replayed}
    assert str(missed.id) in ticket_ids and str(first.id) not in ticket_ids


async def test_events_of_a_failed_handler_are_dropped_even_when_the_outer_transaction_commits(desk):  # noqa: F811
    """A web form catches a handler error and the request still commits: the failed work sends nothing."""
    bus = EventBus(RedisClient(""))
    seen: list[SupportEvent] = []
    bus.subscribe(seen.append)
    async with desk.database.transaction() as session:
        bus.after_commit(session, _event(type=MESSAGE_CREATED))
        try:
            async with desk.database.transaction() as inner:
                bus.after_commit(inner, _event(type=NOTE_CREATED))
                raise RuntimeError("handler failed")
        except RuntimeError:
            pass
    await asyncio.sleep(0.05)
    assert [e.type for e in seen] == [MESSAGE_CREATED]
