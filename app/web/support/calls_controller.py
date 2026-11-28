"""
Support call screens (Plan 29.1, REQ-78)

POST /support/tickets/{id}/calls     record the intent; JSON with the `tel:` link (the page then dials)
POST /support/calls/{id}/finish      outcome, length and note; back to the ticket

Python 3.13+
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions.base import ApplicationException
from app.modules.dependencies import GetHandler
from app.modules.support.domain.exceptions import (
    CallNotFoundException,
    SupportAccessDeniedException,
    TicketNotFoundException,
)
from app.web.framework.renderer import Renderer
from app.web.support.forms import optional_uuid
from app.web.support.portal import SupportPortal


def _error(exc: ApplicationException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": False, "error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


class SupportCallsController:

    @staticmethod
    async def start(request: Request, ticket_id: UUID):
        try:
            await SupportPortal.context(request)
            call, number = await GetHandler.call_handler(request).start_call(ticket_id, request.state.user)
        except SupportAccessDeniedException as exc:
            return _error(exc)
        except ApplicationException as exc:
            return _error(exc)
        digits = "".join(ch for ch in number if ch.isdigit() or ch == "+")
        return JSONResponse(
            content={"status": True, "data": {"call_id": str(call.id), "tel": f"tel:{digits}"}},
            headers={"Cache-Control": "no-store"},
        )

    @staticmethod
    async def finish(request: Request, call_id: UUID):
        try:
            await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return SupportPortal.denied()
        form = await request.form()
        ticket_id = optional_uuid(str(form.get("ticket_id") or ""))
        back = f"/support/tickets/{ticket_id}" if ticket_id else "/support/tickets"
        minutes = str(form.get("minutes") or "").strip()
        try:
            duration = round(float(minutes) * 60) if minutes else None
        except ValueError:
            return Renderer.redirect(f"{back}?notice=invalid")
        try:
            await GetHandler.call_handler(request).finish_call(
                call_id,
                outcome=str(form.get("outcome") or ""),
                duration_s=duration,
                note=str(form.get("note") or ""),
                actor=request.state.user,
            )
        except (CallNotFoundException, TicketNotFoundException):
            return Renderer.redirect(back)
        except ApplicationException:
            return Renderer.redirect(f"{back}?notice=invalid")
        return Renderer.redirect(f"{back}?notice=call_logged")
