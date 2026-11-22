"""
Technical Support API for the mobile app (Phase 26, REQ-67, REQ-70, REQ-71, DECISION-031).

MCC, VLCC, Farmer and VLCC_FARMER logins raise tickets, follow them and chat with the support
team here. Every call is limited to the caller's own tickets; internal notes and internal
timeline events are filtered in the handler, never here. Support staff use the web portal.

Python 3.13+
"""

from __future__ import annotations

import math
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.api.v1.schemas.support import (
    CategoryOut,
    CreateTicketRequest,
    MessageOut,
    PostMessageRequest,
    TicketCardOut,
    TicketDetailOut,
    AttachmentOut,
    dump,
)
from app.middleware.authentication import CurrentUser
from app.modules.dependencies import GetHandler
from app.modules.support.application.attachment_service import MAX_ATTACHMENT_BYTES
from app.modules.support.application.ticket_command import (
    AddAttachmentCommand,
    CreateTicketCommand,
    ListMessagesQuery,
    ListRequesterTicketsQuery,
    PostMessageCommand,
)
from app.modules.support.domain.enums import TicketStatus
from app.modules.support.domain.exceptions import SupportValidationException

router = APIRouter(prefix="/support", tags=["Technical Support"])


# =========================================================
# ENVELOPES
# =========================================================


def _compute_pagination(total: int, limit: int, offset: int) -> dict[str, Any]:
    """Compute pagination metadata (pages, next_page, has_more)."""
    limit_val = max(1, limit)
    offset_val = max(0, offset)
    pages = math.ceil(total / limit_val) if total > 0 else 1
    current_page = (offset_val // limit_val) + 1
    has_more = (offset_val + limit_val) < total
    return {
        "limit": limit_val,
        "offset": offset_val,
        "total": total,
        "pages": pages,
        "next_page": (current_page + 1) if has_more else None,
        "has_more": has_more,
    }


def _record(data: Any, message: str, code: int = 200) -> JSONResponse:
    payload = dump(data) if hasattr(data, "model_dump") else data
    return JSONResponse(status_code=code, content={"status": True, "code": code, "message": message, "data": payload})


def _user(request: Request) -> CurrentUser:
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


# =========================================================
# CATEGORIES
# =========================================================


@router.get("/categories", summary="Ticket categories to choose from")
async def categories(request: Request) -> JSONResponse:
    user = _user(request)
    rows = await GetHandler.ticket_handler(request).list_categories(
        user, active_only=True, requester_only=True,
    )
    items = [dump(CategoryOut.of(row)) for row in rows]
    return JSONResponse(content={
        "status": True, "code": 200, "message": "Categories fetched successfully",
        "items": items, **_compute_pagination(len(items), max(len(items), 1), 0),
    })


# =========================================================
# TICKETS
# =========================================================


@router.post("/tickets", summary="Raise a ticket", status_code=201)
async def create_ticket(request: Request, body: CreateTicketRequest) -> JSONResponse:
    """Returns 201 for a new ticket. A repeated `client_request_id` returns the first ticket with 200."""
    user = _user(request)
    handler = GetHandler.ticket_handler(request)
    ticket, created = await handler.create(
        CreateTicketCommand(
            subject=body.subject,
            description=body.description,
            category_id=body.category_id,
            device_model=body.device_model,
            os_version=body.os_version,
            app_version=body.app_version,
            client_request_id=body.client_request_id,
        ),
        user,
    )
    view = await handler.get_for_requester(ticket.id, user)
    return _record(
        TicketDetailOut.build(view.ticket, view.messages, view.events),
        "Ticket raised successfully" if created else "Ticket already raised",
        code=201 if created else 200,
    )


@router.get("/tickets", summary="My tickets")
async def my_tickets(
    request: Request,
    status: TicketStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JSONResponse:
    rows, total = await GetHandler.ticket_handler(request).list_for_requester(
        ListRequesterTicketsQuery(status=status, limit=limit, offset=offset), _user(request),
    )
    return JSONResponse(content={
        "status": True, "code": 200, "message": "Tickets fetched successfully",
        "items": [dump(TicketCardOut.of(row)) for row in rows],
        **_compute_pagination(total, limit, offset),
    })


@router.get("/tickets/{ticket_id}", summary="One of my tickets with its conversation and timeline")
async def ticket_detail(request: Request, ticket_id: UUID) -> JSONResponse:
    view = await GetHandler.ticket_handler(request).get_for_requester(ticket_id, _user(request))
    return _record(TicketDetailOut.build(view.ticket, view.messages, view.events), "Ticket fetched successfully")


@router.post("/tickets/{ticket_id}/read", summary="Mark the support replies as read")
async def mark_read(request: Request, ticket_id: UUID) -> JSONResponse:
    await GetHandler.ticket_handler(request).mark_read_for_requester(ticket_id, _user(request))
    return _record({"ticket_id": str(ticket_id), "unread": 0}, "Ticket marked as read")


@router.post("/tickets/{ticket_id}/reopen", summary="Reopen a resolved or closed ticket")
async def reopen(request: Request, ticket_id: UUID) -> JSONResponse:
    ticket = await GetHandler.ticket_handler(request).requester_reopen(ticket_id, _user(request))
    return _record(TicketCardOut.of(ticket), "Ticket reopened")


@router.post("/tickets/{ticket_id}/close", summary="Close a ticket I no longer need")
async def close(request: Request, ticket_id: UUID) -> JSONResponse:
    ticket = await GetHandler.ticket_handler(request).requester_close(ticket_id, _user(request))
    return _record(TicketCardOut.of(ticket), "Ticket closed")


# =========================================================
# MESSAGES AND ATTACHMENTS
# =========================================================


@router.get("/tickets/{ticket_id}/messages", summary="Messages after an id, oldest first")
async def messages(
    request: Request,
    ticket_id: UUID,
    after_id: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> JSONResponse:
    """Ask with the last id you have to get only newer messages; `next_after_id` is the id to ask with next."""
    user = _user(request)
    rows = await GetHandler.ticket_handler(request).list_messages_for_requester(
        ListMessagesQuery(ticket_id=ticket_id, after_id=after_id, limit=limit), user,
    )
    items = [dump(MessageOut.of(row, user.id)) for row in rows]
    return JSONResponse(content={
        "status": True, "code": 200, "message": "Messages fetched successfully",
        "items": items,
        **_compute_pagination(len(items), limit, 0),
        "has_more": len(items) == limit,
        "next_after_id": rows[-1].id if rows else after_id,
    })


@router.post("/tickets/{ticket_id}/messages", summary="Send a message", status_code=201)
async def post_message(request: Request, ticket_id: UUID, body: PostMessageRequest) -> JSONResponse:
    user = _user(request)
    message = await GetHandler.ticket_handler(request).post_requester_message(
        PostMessageCommand(ticket_id=ticket_id, body=body.body, client_request_id=body.client_request_id), user,
    )
    return _record(MessageOut.of(message, user.id), "Message sent successfully", code=201)


@router.post("/tickets/{ticket_id}/attachments", summary="Attach a photo or PDF (up to 10 MB)", status_code=201)
async def attach(request: Request, ticket_id: UUID, file: Annotated[UploadFile, File()]) -> JSONResponse:
    """JPEG, PNG, WebP or PDF. The file becomes a message of kind `ATTACHMENT` in the conversation."""
    user = _user(request)
    data = await file.read(MAX_ATTACHMENT_BYTES + 1)
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise SupportValidationException("The file is larger than 10 MB.")
    message, attachment = await GetHandler.ticket_handler(request).attach_for_requester(
        AddAttachmentCommand(
            ticket_id=ticket_id, file_name=file.filename or "attachment",
            content_type=file.content_type or "", data=data,
        ),
        user,
    )
    return _record(
        {"message": dump(MessageOut.of(message, user.id)), "attachment": dump(AttachmentOut.of(attachment))},
        "File attached successfully",
        code=201,
    )


@router.get("/attachments/{attachment_id}", summary="Download an attachment of my ticket")
async def download(request: Request, attachment_id: UUID) -> FileResponse:
    attachment, path = await GetHandler.ticket_handler(request).open_attachment(attachment_id, _user(request))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        media_type=attachment.mime_type,
        filename=attachment.file_name,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
