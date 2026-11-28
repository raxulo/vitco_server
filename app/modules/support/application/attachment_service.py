"""
Ticket Attachment Service (REQ-70, REQ-71)

Validates an uploaded file (JPEG, PNG, WebP, PDF or an audio recording, up to 10 MB, content
checked and not only the declared type) and stores it under `support/<ticket id>/` of the media
storage. That folder is not a `MediaCategory`, so the public `/api/v1/media/...` route can never
serve it; files are only reachable through `TicketHandler.open_attachment`, which checks the reader.

Audio (voice messages): M4A / AAC / MP4 audio, MP3, Ogg, WebM and WAV, the formats phones and
browsers record in. A file sent as `application/octet-stream` (some mobile HTTP clients do that)
is recognised by its content.

A file written in a transaction that later rolls back is removed again; files of a deleted
message are removed after the transaction commits.

Python 3.13+
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.media.domain.storage_interface import StorageInterface
from app.modules.media.infrastructure.file_cleanup import delete_after_commit, delete_on_rollback
from app.modules.support.application.ticket_command import AddAttachmentCommand
from app.modules.support.domain.entities import TicketAttachment
from app.modules.support.domain.exceptions import SupportValidationException

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


def _mp4(data: bytes) -> bool:            # ISO media (M4A, MP4 audio, 3GP): "ftyp" box first
    return data[4:8] == b"ftyp"


def _mp3(data: bytes) -> bool:            # an ID3 tag or an MPEG audio frame sync
    return data.startswith(b"ID3") or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)


def _aac(data: bytes) -> bool:            # raw AAC in ADTS frames
    return len(data) > 1 and data[0] == 0xFF and data[1] & 0xF6 == 0xF0


def _riff(kind: bytes) -> Callable[[bytes], bool]:
    return lambda data: data.startswith(b"RIFF") and data[8:12] == kind


def _starts(*signatures: bytes) -> Callable[[bytes], bool]:
    return lambda data: data.startswith(signatures)


# type -> (stored extension, check of the real content). Images and PDF first: they win when sniffing.
_TYPES: dict[str, tuple[str, Callable[[bytes], bool]]] = {
    "image/jpeg": (".jpg", _starts(b"\xff\xd8\xff")),
    "image/png": (".png", _starts(b"\x89PNG\r\n\x1a\n")),
    "image/webp": (".webp", _riff(b"WEBP")),
    "application/pdf": (".pdf", _starts(b"%PDF-")),
    "audio/mp4": (".m4a", _mp4),
    "audio/3gpp": (".3gp", _mp4),
    "audio/ogg": (".ogg", _starts(b"OggS")),
    "audio/webm": (".webm", _starts(b"\x1a\x45\xdf\xa3")),
    "audio/wav": (".wav", _riff(b"WAVE")),
    "audio/aac": (".aac", _aac),
    "audio/mpeg": (".mp3", _mp3),
}

# Other names clients use for the same formats
_ALIASES: dict[str, str] = {
    "audio/m4a": "audio/mp4",
    "audio/x-m4a": "audio/mp4",
    "audio/mp4a-latm": "audio/mp4",
    "video/mp4": "audio/mp4",          # a recorder may label sound-only MP4 as video
    "audio/3gp": "audio/3gpp",
    "video/3gpp": "audio/3gpp",
    "audio/x-wav": "audio/wav",
    "audio/wave": "audio/wav",
    "audio/vnd.wave": "audio/wav",
    "audio/mp3": "audio/mpeg",
    "audio/x-aac": "audio/aac",
    "application/ogg": "audio/ogg",
    "audio/opus": "audio/ogg",
    "video/webm": "audio/webm",
}

# Declared by clients that do not know the type: work it out from the content
_UNKNOWN_TYPES = frozenset({"", "application/octet-stream", "binary/octet-stream"})

_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]+")


def is_audio(mime_type: str) -> bool:
    return mime_type.startswith("audio/")


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
        mime = _ALIASES.get(mime, mime)
        if mime not in _TYPES and mime not in _UNKNOWN_TYPES:
            raise SupportValidationException(
                "Only JPEG, PNG, WebP images, PDF files and audio recordings can be attached."
            )
        if not command.data:
            raise SupportValidationException("The file is empty.")
        if len(command.data) > MAX_ATTACHMENT_BYTES:
            raise SupportValidationException("The file is larger than 10 MB.")
        head = command.data[:16]
        if mime in _UNKNOWN_TYPES:
            mime = next((name for name, (_ext, check) in _TYPES.items() if check(head)), "")
            if not mime:
                raise SupportValidationException(
                    "Only JPEG, PNG, WebP images, PDF files and audio recordings can be attached."
                )
        extension, check = _TYPES[mime]
        if not check(head):
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

    def remove_after_commit(self, session: AsyncSession, storage_keys: list[str]) -> None:
        """Files of a deleted message: gone once the deletion is committed, kept if it rolls back."""
        if storage_keys:
            delete_after_commit(session, self._storage, *storage_keys)

    def path_of(self, attachment: TicketAttachment) -> Path:
        return self._storage.get_path(attachment.storage_key)
