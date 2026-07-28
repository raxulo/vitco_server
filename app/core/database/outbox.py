"""
RealTimeTransfer
================

Enterprise Transactional Outbox Pattern

Guarantees eventual consistency and zero event loss across distributed microservices.

Python 3.13+
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import Column, String, DateTime, Text, Boolean, select
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession

OutboxBase = declarative_base()


class OutboxMessage(OutboxBase):
    """
    Outbox table schema for recording published domain events.
    """

    __tablename__ = "outbox_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(255), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processed = Column(Boolean, default=False, nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)


class OutboxRepository:
    """
    Repository for persisting and managing Transactional Outbox messages.
    """

    __slots__ = ("_session",)

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_event(self, event_type: str, payload_json: str) -> OutboxMessage:
        """
        Appends an event message to the outbox inside the active transaction.
        """
        msg = OutboxMessage(
            event_type=event_type,
            payload=payload_json,
        )
        self._session.add(msg)
        return msg

    async def get_unprocessed(self, limit: int = 100) -> Sequence[OutboxMessage]:
        """
        Fetch pending unprocessed outbox events for background relay.
        """
        stmt = (
            select(OutboxMessage)
            .where(OutboxMessage.processed == False)  # noqa: E712
            .order_by(OutboxMessage.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def mark_processed(self, message_id: str) -> None:
        """
        Mark an outbox message as delivered.
        """
        msg = await self._session.get(OutboxMessage, message_id)
        if msg:
            msg.processed = True
            msg.processed_at = datetime.now(timezone.utc)
