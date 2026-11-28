"""
Ticket Attachment Service (REQ-70, REQ-71)

Validates an uploaded file (JPEG, PNG, WebP or PDF, up to 10 MB, content checked and not only
the declared type) and stores it under `support/<ticket id>/` of the media storage. That
folder is not a `MediaCategory`, so the public `/api/v1/media/...` route can never serve it;
files are only reachable through `TicketHandler.open_attachment`, which checks the reader.

A file written in a transaction that later rolls back is removed again.

Python 3.13+
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.media.domain.storage_interface import StorageInterface
from app.modules.media.infrastructure.file_cleanup import delete_on_rollback
from app.modules.support.application.ticket_command import AddAttachmentCommand
from app.modules.support.domain.entities import TicketAttachment
from app.modules.support.domain.exceptions import SupportValidationException

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

# declared type -> (stored extension, leading bytes the real file must start with)
_TYPES: dict[str, tuple[str, tuple[bytes, ...]]] = {
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/webp": (".webp", (b"RIFF",)),
    "application/pdf": (".pdf", (b"%PDF-",)),
}

_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_file_name(name: str | None, extension: str) -> str:
    """A display name without path parts or odd characters, never empty."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = _UNSAFE_NAME.sub("_", base).strip(" ._")[:120]
    if not base:
        base = "attachment"
    return base if base.lower().endswith(extension) else f"{base}{extension}"


class AttachmentService:

    __slots__ = ("_storage",)

    def __init__(self, storage: StorageInterface) -> None:
        self._storage = storage

    @staticmethod
    def validate(command: AddAttachmentCommand) -> tuple[str, str]:
        """(extension, mime type) of an acceptable file, else a validation error."""
        mime = (command.content_type or "").split(";")[0].strip().lower()
        if mime not in _TYPES:
            raise SupportValidationException("Only JPEG, PNG, WebP images and PDF files can be attached.")
        if not command.data:
            raise SupportValidationException("The file is empty.")
        if len(command.data) > MAX_ATTACHMENT_BYTES:
            raise SupportValidationException("The file is larger than 10 MB.")
        extension, signatures = _TYPES[mime]
        head = command.data[:16]
        if not head.startswith(signatures) or (mime == "image/webp" and command.data[8:12] != b"WEBP"):
            raise SupportValidationException("The file does not match its type.")
        return extension, mime

    async def store(self, session: AsyncSession, ticket_id: UUID, command: AddAttachmentCommand) -> TicketAttachment:
        """Check and write the file; the database row is added by the caller in the same transaction."""
        extension, mime = self.validate(command)
        attachment_id = uuid4()
        storage_key = f"support/{ticket_id.hex}/{attachment_id.hex}{extension}"
        await asyncio.to_thread(self._write, command.data, storage_key)
        delete_on_rollback(session, self._storage, storage_key)
        return TicketAttachment(
            id=attachment_id,
            ticket_id=ticket_id,
            message_id=None,
            uploaded_by=None,
            file_name=safe_file_name(command.file_name, extension),
            mime_type=mime,
            size_bytes=len(command.data),
            storage_key=storage_key,
        )

    def _write(self, data: bytes, storage_key: str) -> None:
        # LocalStorage.save is declared async but only does blocking file I/O; write directly
        path = self._storage.get_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as destination:
            destination.write(data)

    def path_of(self, attachment: TicketAttachment) -> Path:
        return self._storage.get_path(attachment.storage_key)
