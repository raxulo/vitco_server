"""
Technical Support WebSockets (Phase 27, REQ-73 to REQ-75)

/ws/support       staff (the portal; cookie sign-in, or a token)
/ws/support/app   requesters (the mobile app; token)

Sign-in: a browser sends its `access_token` cookie with the handshake (only accepted from the same
origin); anything else sends `{"type": "auth", "token": "...", "last_event_id": N}` as its first
message within `authentication_timeout` seconds. The server then answers `hello`
(`latest_id`, `resync`) and replays what the client missed, or says `resync` when it missed too much.

Client messages: `ping`, `typing` (`ticket_id`, `note`), `read` (`ticket_id`).
Server messages: `hello`, `event`, `typing`, `pong`, `error`.
What a socket hears is decided on the server by `audience.can_receive`.

Python 3.13+
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config.settings import settings
from app.config.websocket import connection_config
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.auth.infrastructure.jwt import JWTService
from app.modules.support.application.audience import Subscriber, can_receive
from app.modules.support.application.event_bus import EventBus
from app.modules.support.application.events import TYPING, SupportEvent
from app.modules.support.application.hub import Connection, SocketHub
from app.modules.support.application.ticket_handler import REQUESTER_ROLES, TicketHandler
from app.modules.support.domain.exceptions import SupportAccessDeniedException

logger = logging.getLogger(__name__)

router = APIRouter()

# Close codes (4000 range is for applications)
UNAUTHORIZED = 4401
FORBIDDEN = 4403
BUSY = 1013

# How often an open socket checks that its user still has access (disabled member, new role, team off)
ACCESS_RECHECK_S = 30.0


async def _is_active(websocket: WebSocket, user_id: UUID) -> bool:
    database = websocket.app.state.application.container.database
    async with database.transaction() as session:
        row = (
            await session.execute(select(UserModel.is_active, UserModel.is_deleted).where(UserModel.id == user_id))
        ).first()
    return row is not None and bool(row.is_active) and not row.is_deleted


async def _decode(websocket: WebSocket, token: str) -> CurrentUser | None:
    raw = urllib.parse.unquote(token or "").strip("\"' \t\r\n")
    if raw.lower().startswith("bearer"):
        raw = raw[6:].strip()
    if not raw:
        return None
    try:
        payload = JWTService(secret_key=settings.SECRET_KEY).decode(raw)
        subject = UUID(str(payload["sub"]))
    except Exception:
        return None
    if not await _is_active(websocket, subject):
        return None
    return CurrentUser(id=subject, role=str(payload.get("role", "")), name=payload.get("name"))


async def _subscriber(user: CurrentUser, kind: str, handler: TicketHandler) -> Subscriber | None:
    """Who this socket listens as right now, or None when the user may not use it."""
    if kind == "app":
        return Subscriber.requester(user.id) if user.role_type in REQUESTER_ROLES else None
    if user.role_type not in (Role.SUPPORT, Role.SUPER_ADMIN):
        return None
    try:
        return Subscriber.staff(await handler.context(user))
    except SupportAccessDeniedException:
        return None


def _same_origin(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    return origin is None or urllib.parse.urlparse(origin).netloc == websocket.headers.get("host")


async def _authenticate(websocket: WebSocket) -> tuple[CurrentUser | None, int]:
    """(user, last_event_id). The cookie or Authorization header counts at once, else the first message.

    With a header or cookie there is no first message, so the last id comes from `?last_event_id=`.
    """
    last_id = 0
    token = websocket.headers.get("authorization") or ""
    if not token and websocket.cookies.get("access_token") and _same_origin(websocket):
        token = websocket.cookies["access_token"]
    if token:
        try:
            last_id = max(0, int(websocket.query_params.get("last_event_id") or 0))
        except (TypeError, ValueError):
            last_id = 0
    if not token:
        try:
            first = await asyncio.wait_for(websocket.receive_json(), timeout=connection_config.authentication_timeout)
        except Exception:
            return None, 0
        if not isinstance(first, dict) or first.get("type") != "auth":
            return None, 0
        token = str(first.get("token") or "")
        try:
            last_id = int(first.get("last_event_id") or 0)
        except (TypeError, ValueError):
            last_id = 0
    return await _decode(websocket, token), last_id


async def _serve(websocket: WebSocket, kind: str) -> None:
    await websocket.accept()
    container = websocket.app.state.application.container
    handler: TicketHandler = container.resolve(TicketHandler)
    hub: SocketHub = container.resolve(SocketHub)
    bus: EventBus = container.resolve(EventBus)

    user, last_id = await _authenticate(websocket)
    if user is None:
        await websocket.close(code=UNAUTHORIZED)
        return

    subscriber = await _subscriber(user, kind, handler)
    if subscriber is None:
        await websocket.close(code=FORBIDDEN)
        return

    connection = Connection(subscriber=subscriber, kind=kind)
    if not hub.add(connection):
        await websocket.close(code=BUSY)
        return

    try:
        replay, complete = bus.replay(last_id) if last_id else ([], True)
        await websocket.send_json({"type": "hello", "latest_id": bus.latest_id, "resync": not complete})
        for event in replay:
            if can_receive(subscriber, event):
                await websocket.send_json(connection.payload_for(event))
        await hub.touch(user.id)

        sender = asyncio.create_task(_send_loop(websocket, connection))
        receiver = asyncio.create_task(_receive_loop(websocket, connection, user, handler, hub, bus))
        watcher = asyncio.create_task(_watch_access(websocket, connection, user, handler))
        done, pending = await asyncio.wait({sender, receiver, watcher}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            task.exception()   # already handled inside; reading it stops "never retrieved" warnings
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Support socket failed")
    finally:
        hub.remove(connection)
        await hub.drop_presence(user.id)
        try:
            await websocket.close()
        except Exception:
            pass


async def _watch_access(websocket: WebSocket, connection: Connection, user: CurrentUser, handler: TicketHandler) -> None:
    """Keeps the audience in step with the user's current access; closes the socket once it is gone.

    The audience is decided per event from `connection.subscriber`, so a member who is disabled, moved
    to another team or loses `view_all` stops hearing the team within `ACCESS_RECHECK_S`.
    """
    while True:
        await asyncio.sleep(ACCESS_RECHECK_S)
        try:
            subscriber = await _subscriber(user, connection.kind, handler) if await _is_active(websocket, user.id) else None
        except Exception:
            logger.warning("Support socket access check failed; trying again later")
            continue                     # a database hiccup is not a reason to drop the user
        if subscriber is None:
            await websocket.close(code=FORBIDDEN)
            return
        connection.subscriber = subscriber


async def _send_loop(websocket: WebSocket, connection: Connection) -> None:
    try:
        while True:
            message = await connection.queue.get()
            await websocket.send_json(message)
            if connection.overflowed and connection.queue.empty():
                await websocket.close(code=BUSY)
                return
    except (WebSocketDisconnect, RuntimeError):
        return


async def _receive_loop(
    websocket: WebSocket, connection: Connection, user: CurrentUser, handler: TicketHandler,
    hub: SocketHub, bus: EventBus,
) -> None:
    last_touch = 0.0
    loop = asyncio.get_running_loop()
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            kind = message.get("type")
            now = loop.time()
            if now - last_touch > 20:
                last_touch = now
                await hub.touch(user.id)
            if kind == "ping":
                connection.send({"type": "pong"})
                continue
            try:
                ticket_id = UUID(str(message.get("ticket_id")))
            except (TypeError, ValueError):
                continue
            ticket = await handler.socket_ticket(user, ticket_id)
            if ticket is None:
                connection.send({"type": "error", "error": "not_found", "ticket_id": str(ticket_id)})
                continue
            if kind == "typing":
                note = bool(message.get("note")) and not connection.subscriber.is_requester
                await bus.publish(SupportEvent(
                    type=TYPING, ticket_id=str(ticket.id), ticket_no=ticket.ticket_no,
                    team_id=str(ticket.team_id) if ticket.team_id else None,
                    requester_id=str(ticket.requester_user_id),
                    assigned_to=str(ticket.assigned_to) if ticket.assigned_to else None,
                    public=not note,
                    data={"user_id": str(user.id), "typing": True, "staff": not connection.subscriber.is_requester},
                ))
            elif kind == "read":
                if connection.subscriber.is_requester:
                    await handler.mark_read_for_requester(ticket.id, user)
                else:
                    await handler.mark_read_for_staff(ticket.id, user)
    except (WebSocketDisconnect, RuntimeError):
        return
    except Exception:
        logger.exception("Support socket receive failed")


@router.websocket("/ws/support")
async def staff_socket(websocket: WebSocket) -> None:
    await _serve(websocket, "staff")


@router.websocket("/ws/support/app")
async def app_socket(websocket: WebSocket) -> None:
    await _serve(websocket, "app")
