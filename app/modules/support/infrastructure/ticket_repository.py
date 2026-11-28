"""
Ticket Repository (Phase 26)

Async SQLAlchemy implementation of `ITicketRepository`. It never commits: the handlers own
the transaction. Lists load the requester, the assignee, the category and the team in the
same query (no per-row lookups).

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.administration.infrastructure.models import UserModel
from app.modules.support.domain.entities import (
    Category,
    Ticket,
    TicketAttachment,
    TicketEvent,
    TicketMessage,
)
from app.modules.support.domain.enums import Scope, TicketPriority, TicketStatus
from app.modules.support.domain.exceptions import DuplicateClientRequestException
from app.modules.support.domain.irepository import ITicketRepository
from app.modules.support.infrastructure.models import (
    SupportAttachmentModel,
    SupportCategoryModel,
    SupportMemberModel,
    SupportTeamModel,
    SupportTicketCounterModel,
    SupportTicketEventModel,
    SupportTicketMessageModel,
    SupportTicketModel,
)

_Requester = aliased(UserModel, name="requester")
_Assignee = aliased(UserModel, name="assignee")
_Parent = aliased(UserModel, name="parent")
_Sender = aliased(UserModel, name="sender")
_Actor = aliased(UserModel, name="actor")


def _like(text: str) -> str:
    """A safe `ILIKE` pattern for a user typed search."""
    escaped = text.strip().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    return f"%{escaped}%"


class TicketRepository(ITicketRepository):

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # CATEGORIES
    # =========================================================

    @staticmethod
    def _to_category(row) -> Category:
        model: SupportCategoryModel = row[0]
        return Category(
            id=model.id,
            name=model.name,
            default_team_id=model.default_team_id,
            default_priority=model.default_priority,
            is_active=model.is_active,
            default_team_name=row.team_name,
        )

    def _category_query(self):
        return select(SupportCategoryModel, SupportTeamModel.name.label("team_name")).outerjoin(
            SupportTeamModel, SupportTeamModel.id == SupportCategoryModel.default_team_id,
        )

    async def add_category(self, category: Category, actor_id: UUID | None) -> None:
        self._session.add(
            SupportCategoryModel(
                id=category.id,
                name=category.name,
                default_team_id=category.default_team_id,
                default_priority=category.default_priority,
                is_active=category.is_active,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        await self._session.flush()

    async def get_category(self, category_id: UUID) -> Category | None:
        row = (
            await self._session.execute(self._category_query().where(SupportCategoryModel.id == category_id))
        ).first()
        return self._to_category(row) if row else None

    async def category_name_exists(self, name: str, exclude_category_id: UUID | None = None) -> bool:
        stmt = select(SupportCategoryModel.id).where(func.lower(SupportCategoryModel.name) == name.lower())
        if exclude_category_id is not None:
            stmt = stmt.where(SupportCategoryModel.id != exclude_category_id)
        return (await self._session.scalar(stmt.limit(1))) is not None

    async def list_categories(self, *, active_only: bool) -> list[Category]:
        stmt = self._category_query()
        if active_only:
            stmt = stmt.where(SupportCategoryModel.is_active.is_(True))
        rows = (await self._session.execute(stmt.order_by(SupportCategoryModel.name))).all()
        return [self._to_category(row) for row in rows]

    async def update_category(
        self,
        category_id: UUID,
        *,
        name: str | None,
        default_team_id: UUID | None,
        set_team: bool,
        default_priority: TicketPriority | None,
        is_active: bool | None,
        actor_id: UUID | None,
    ) -> None:
        values: dict = {"updated_by": actor_id}
        if name is not None:
            values["name"] = name
        if set_team:
            values["default_team_id"] = default_team_id
        if default_priority is not None:
            values["default_priority"] = default_priority
        if is_active is not None:
            values["is_active"] = is_active
        await self._session.execute(
            update(SupportCategoryModel).where(SupportCategoryModel.id == category_id).values(**values)
        )

    # =========================================================
    # TICKETS
    # =========================================================

    async def next_ticket_number(self, year: int) -> str:
        """`TS-YYYY-NNNNNN` from a per-year counter row, incremented atomically."""
        bump = (
            update(SupportTicketCounterModel)
            .where(SupportTicketCounterModel.year == year)
            .values(last_value=SupportTicketCounterModel.last_value + 1)
            .returning(SupportTicketCounterModel.last_value)
            .execution_options(synchronize_session=False)
        )
        value = await self._session.scalar(bump)
        if value is None:
            try:
                async with self._session.begin_nested():
                    self._session.add(SupportTicketCounterModel(year=year, last_value=0))
            except IntegrityError:
                pass  # another request created the year's row first
            value = await self._session.scalar(bump)
        return f"TS-{year}-{int(value):06d}"

    async def add_ticket(self, ticket: Ticket) -> None:
        self._session.add(
            SupportTicketModel(
                id=ticket.id,
                ticket_no=ticket.ticket_no,
                requester_user_id=ticket.requester_user_id,
                category_id=ticket.category_id,
                team_id=ticket.team_id,
                assigned_to=ticket.assigned_to,
                priority=ticket.priority,
                status=ticket.status,
                subject=ticket.subject,
                description=ticket.description,
                device_model=ticket.device_model,
                os_version=ticket.os_version,
                app_version=ticket.app_version,
                client_request_id=ticket.client_request_id,
                last_message_at=ticket.last_message_at,
                staff_unread=ticket.staff_unread,
                created_by=ticket.requester_user_id,
                updated_by=ticket.requester_user_id,
            )
        )
        await self._flush_unique_request(ticket.client_request_id)

    async def _flush_unique_request(self, client_request_id: str | None) -> None:
        """Flush; a clash on the `client_request_id` unique index becomes a domain exception."""
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if client_request_id and "client_request" in str(exc.orig).lower():
                raise DuplicateClientRequestException() from exc
            raise

    def _ticket_query(self):
        return (
            select(
                SupportTicketModel,
                _Requester.name.label("requester_name"),
                _Requester.role.label("requester_role"),
                _Requester.mobile.label("requester_mobile"),
                _Requester.email.label("requester_email"),
                _Parent.name.label("requester_parent"),
                _Assignee.name.label("assignee_name"),
                SupportCategoryModel.name.label("category_name"),
                SupportTeamModel.name.label("team_name"),
            )
            .join(_Requester, _Requester.id == SupportTicketModel.requester_user_id)
            .outerjoin(_Parent, _Parent.id == _Requester.created_by)
            .outerjoin(_Assignee, _Assignee.id == SupportTicketModel.assigned_to)
            .join(SupportCategoryModel, SupportCategoryModel.id == SupportTicketModel.category_id)
            .outerjoin(SupportTeamModel, SupportTeamModel.id == SupportTicketModel.team_id)
        )

    @staticmethod
    def _to_ticket(row) -> Ticket:
        model: SupportTicketModel = row[0]
        return Ticket(
            id=model.id,
            ticket_no=model.ticket_no,
            requester_user_id=model.requester_user_id,
            category_id=model.category_id,
            subject=model.subject,
            description=model.description,
            status=model.status,
            priority=model.priority,
            team_id=model.team_id,
            assigned_to=model.assigned_to,
            device_model=model.device_model,
            os_version=model.os_version,
            app_version=model.app_version,
            client_request_id=model.client_request_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            first_response_at=model.first_response_at,
            last_message_at=model.last_message_at,
            resolved_at=model.resolved_at,
            closed_at=model.closed_at,
            sla_due_at=model.sla_due_at,
            requester_unread=model.requester_unread,
            staff_unread=model.staff_unread,
            category_name=row.category_name,
            team_name=row.team_name,
            requester_name=row.requester_name,
            requester_role=int(row.requester_role) if row.requester_role is not None else None,
            requester_mobile=row.requester_mobile,
            requester_email=row.requester_email,
            requester_parent=row.requester_parent,
            assignee_name=row.assignee_name,
        )

    async def get_ticket(self, ticket_id: UUID) -> Ticket | None:
        row = (await self._session.execute(self._ticket_query().where(SupportTicketModel.id == ticket_id))).first()
        return self._to_ticket(row) if row else None

    async def find_by_client_request(self, requester_user_id: UUID, client_request_id: str) -> Ticket | None:
        row = (
            await self._session.execute(
                self._ticket_query().where(
                    SupportTicketModel.requester_user_id == requester_user_id,
                    SupportTicketModel.client_request_id == client_request_id,
                )
            )
        ).first()
        return self._to_ticket(row) if row else None

    async def _page(self, conditions: list, *, limit: int, offset: int) -> tuple[list[Ticket], int]:
        count_stmt = (
            select(func.count(SupportTicketModel.id))
            .join(_Requester, _Requester.id == SupportTicketModel.requester_user_id)
            .where(*conditions)
        )
        total = int(await self._session.scalar(count_stmt) or 0)
        rows = (
            await self._session.execute(
                self._ticket_query()
                .where(*conditions)
                .order_by(
                    func.coalesce(SupportTicketModel.last_message_at, SupportTicketModel.created_at).desc(),
                    SupportTicketModel.id,
                )
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return [self._to_ticket(row) for row in rows], total

    async def list_for_requester(
        self, requester_user_id: UUID, *, status: TicketStatus | None, limit: int, offset: int,
    ) -> tuple[list[Ticket], int]:
        conditions = [SupportTicketModel.requester_user_id == requester_user_id]
        if status is not None:
            conditions.append(SupportTicketModel.status == status)
        return await self._page(conditions, limit=limit, offset=offset)

    async def list_for_staff(
        self,
        *,
        scope: Scope,
        team_id: UUID | None,
        user_id: UUID,
        limit_to_assigned: bool,
        status: list[TicketStatus] | None,
        priority: TicketPriority | None,
        category_id: UUID | None,
        assignee_id: UUID | None,
        search: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Ticket], int]:
        """`team_id` None means Super Admin: every team for ALL / MINE, the pool (no team) for UNASSIGNED."""
        conditions: list = []
        if scope is Scope.UNASSIGNED:
            if team_id is None:
                conditions.append(SupportTicketModel.team_id.is_(None))
            else:
                conditions.append(SupportTicketModel.team_id == team_id)
                conditions.append(SupportTicketModel.assigned_to.is_(None))
        else:
            if team_id is not None:
                conditions.append(SupportTicketModel.team_id == team_id)
            if scope is Scope.MINE or limit_to_assigned:
                conditions.append(SupportTicketModel.assigned_to == user_id)
        if status:
            conditions.append(SupportTicketModel.status.in_(status))
        if priority is not None:
            conditions.append(SupportTicketModel.priority == priority)
        if category_id is not None:
            conditions.append(SupportTicketModel.category_id == category_id)
        if assignee_id is not None:
            conditions.append(SupportTicketModel.assigned_to == assignee_id)
        if date_from is not None:
            conditions.append(SupportTicketModel.created_at >= date_from)
        if date_to is not None:
            conditions.append(SupportTicketModel.created_at <= date_to)
        if search and search.strip():
            pattern = _like(search)
            conditions.append(
                or_(
                    SupportTicketModel.ticket_no.ilike(pattern, escape="\\"),
                    SupportTicketModel.subject.ilike(pattern, escape="\\"),
                    _Requester.name.ilike(pattern, escape="\\"),
                    _Requester.mobile.ilike(pattern, escape="\\"),
                )
            )
        return await self._page(conditions, limit=limit, offset=offset)

    async def update_ticket(self, ticket_id: UUID, values: dict) -> None:
        await self._session.execute(
            update(SupportTicketModel)
            .where(SupportTicketModel.id == ticket_id)
            .values(**values)
            .execution_options(synchronize_session=False)
        )

    async def bump_unread(self, ticket_id: UUID, *, for_staff: bool) -> None:
        column = SupportTicketModel.staff_unread if for_staff else SupportTicketModel.requester_unread
        await self._session.execute(
            update(SupportTicketModel)
            .where(SupportTicketModel.id == ticket_id)
            .values({column.key: column + 1})
            .execution_options(synchronize_session=False)
        )

    async def clear_unread(self, ticket_id: UUID, *, for_staff: bool) -> None:
        key = "staff_unread" if for_staff else "requester_unread"
        await self._session.execute(
            update(SupportTicketModel)
            .where(SupportTicketModel.id == ticket_id)
            .values({key: 0})
            .execution_options(synchronize_session=False)
        )

    async def queue_counts(self, *, team_id: UUID | None, user_id: UUID) -> dict[str, int]:
        """`team_id` None is Super Admin: every team, with the pool (no team) as "unassigned"."""
        from app.modules.support.domain.ticket_rules import OPEN_STATES

        model = SupportTicketModel
        is_open = model.status.in_(OPEN_STATES)
        waiting = model.team_id.is_(None) if team_id is None else model.assigned_to.is_(None)
        stmt = select(
            func.coalesce(func.sum(case((is_open & waiting, 1), else_=0)), 0),
            func.coalesce(func.sum(case((is_open, 1), else_=0)), 0),
            func.coalesce(func.sum(case((is_open & (model.assigned_to == user_id), 1), else_=0)), 0),
        )
        if team_id is not None:
            stmt = stmt.where(model.team_id == team_id)
        unassigned, everything, mine = (await self._session.execute(stmt)).one()
        return {"unassigned": int(unassigned), "all": int(everything), "mine": int(mine)}

    async def member_is_assignable(self, user_id: UUID, team_id: UUID) -> bool:
        stmt = (
            select(SupportMemberModel.id)
            .join(UserModel, UserModel.id == SupportMemberModel.user_id)
            .where(
                SupportMemberModel.user_id == user_id,
                SupportMemberModel.team_id == team_id,
                SupportMemberModel.is_active.is_(True),
                UserModel.is_active.is_(True),
            )
        )
        return (await self._session.scalar(stmt.limit(1))) is not None

    # =========================================================
    # MESSAGES, EVENTS, ATTACHMENTS
    # =========================================================

    @staticmethod
    def _to_message(model: SupportTicketMessageModel, sender_name: str | None) -> TicketMessage:
        return TicketMessage(
            id=model.id,
            ticket_id=model.ticket_id,
            sender_user_id=model.sender_user_id,
            sender_is_staff=model.sender_is_staff,
            body=model.body,
            kind=model.kind,
            is_internal=model.is_internal,
            client_request_id=model.client_request_id,
            created_at=model.created_at,
            deleted_at=model.deleted_at,
            sender_name=sender_name,
        )

    async def add_message(self, message: TicketMessage) -> TicketMessage:
        model = SupportTicketMessageModel(
            ticket_id=message.ticket_id,
            sender_user_id=message.sender_user_id,
            sender_is_staff=message.sender_is_staff,
            kind=message.kind,
            body=message.body,
            is_internal=message.is_internal,
            client_request_id=message.client_request_id,
            created_at=message.created_at or now_naive_ist(),
        )
        self._session.add(model)
        await self._flush_unique_request(message.client_request_id)
        message.id = model.id
        message.created_at = model.created_at
        return message

    async def get_message(self, message_id: int) -> TicketMessage | None:
        row = (
            await self._session.execute(
                select(SupportTicketMessageModel, _Sender.name.label("sender_name"))
                .outerjoin(_Sender, _Sender.id == SupportTicketMessageModel.sender_user_id)
                .where(SupportTicketMessageModel.id == message_id)
            )
        ).first()
        return self._to_message(row[0], row.sender_name) if row else None

    async def delete_message(self, message_id: int, *, deleted_by: UUID, deleted_at: datetime) -> list[str]:
        """Blank the message, drop its attachment rows and return their storage keys (removed after commit)."""
        attachments = (
            await self._session.scalars(
                select(SupportAttachmentModel).where(SupportAttachmentModel.message_id == message_id)
            )
        ).all()
        keys = [attachment.storage_key for attachment in attachments]
        await self._session.execute(delete(SupportAttachmentModel).where(SupportAttachmentModel.message_id == message_id))
        await self._session.execute(
            update(SupportTicketMessageModel)
            .where(SupportTicketMessageModel.id == message_id)
            .values(body="", deleted_at=deleted_at, deleted_by=deleted_by)
        )
        return keys

    async def find_message_by_client_request(
        self, ticket_id: UUID, sender_user_id: UUID, client_request_id: str,
    ) -> TicketMessage | None:
        row = (
            await self._session.execute(
                select(SupportTicketMessageModel, _Sender.name.label("sender_name"))
                .outerjoin(_Sender, _Sender.id == SupportTicketMessageModel.sender_user_id)
                .where(
                    SupportTicketMessageModel.ticket_id == ticket_id,
                    SupportTicketMessageModel.sender_user_id == sender_user_id,
                    SupportTicketMessageModel.client_request_id == client_request_id,
                )
            )
        ).first()
        return self._to_message(row[0], row.sender_name) if row else None

    async def list_messages(
        self, ticket_id: UUID, *, include_internal: bool, after_id: int | None, limit: int,
    ) -> list[TicketMessage]:
        stmt = (
            select(SupportTicketMessageModel, _Sender.name.label("sender_name"))
            .outerjoin(_Sender, _Sender.id == SupportTicketMessageModel.sender_user_id)
            .where(SupportTicketMessageModel.ticket_id == ticket_id)
        )
        if not include_internal:
            stmt = stmt.where(SupportTicketMessageModel.is_internal.is_(False))
        if after_id is not None:
            stmt = stmt.where(SupportTicketMessageModel.id > after_id)
        rows = (await self._session.execute(stmt.order_by(SupportTicketMessageModel.id).limit(limit))).all()
        messages = [self._to_message(row[0], row.sender_name) for row in rows]
        if messages:
            by_id = {message.id: message for message in messages}
            attachments = (
                await self._session.scalars(
                    select(SupportAttachmentModel).where(SupportAttachmentModel.message_id.in_(list(by_id)))
                )
            ).all()
            for attachment in attachments:
                by_id[attachment.message_id].attachments.append(self._to_attachment(attachment))
        return messages

    async def add_event(self, event: TicketEvent) -> TicketEvent:
        model = SupportTicketEventModel(
            ticket_id=event.ticket_id,
            actor_user_id=event.actor_user_id,
            event_type=event.event_type,
            from_value=event.from_value,
            to_value=event.to_value,
            meta=event.meta,
            is_public=event.is_public,
            created_at=event.created_at or now_naive_ist(),
        )
        self._session.add(model)
        await self._session.flush()
        event.id = model.id
        event.created_at = model.created_at
        return event

    async def list_events(self, ticket_id: UUID, *, public_only: bool) -> list[TicketEvent]:
        stmt = (
            select(SupportTicketEventModel, _Actor.name.label("actor_name"))
            .outerjoin(_Actor, _Actor.id == SupportTicketEventModel.actor_user_id)
            .where(SupportTicketEventModel.ticket_id == ticket_id)
        )
        if public_only:
            stmt = stmt.where(SupportTicketEventModel.is_public.is_(True))
        rows = (await self._session.execute(stmt.order_by(SupportTicketEventModel.id))).all()
        return [
            TicketEvent(
                id=row[0].id,
                ticket_id=row[0].ticket_id,
                actor_user_id=row[0].actor_user_id,
                event_type=row[0].event_type,
                from_value=row[0].from_value,
                to_value=row[0].to_value,
                meta=row[0].meta or {},
                is_public=row[0].is_public,
                created_at=row[0].created_at,
                actor_name=row.actor_name,
            )
            for row in rows
        ]

    @staticmethod
    def _to_attachment(model: SupportAttachmentModel) -> TicketAttachment:
        return TicketAttachment(
            id=model.id,
            ticket_id=model.ticket_id,
            message_id=model.message_id,
            uploaded_by=model.uploaded_by,
            file_name=model.file_name,
            mime_type=model.mime_type,
            size_bytes=model.size_bytes,
            storage_key=model.storage_key,
            created_at=model.created_at,
        )

    async def add_attachment(self, attachment: TicketAttachment) -> None:
        self._session.add(
            SupportAttachmentModel(
                id=attachment.id,
                ticket_id=attachment.ticket_id,
                message_id=attachment.message_id,
                uploaded_by=attachment.uploaded_by,
                file_name=attachment.file_name,
                mime_type=attachment.mime_type,
                size_bytes=attachment.size_bytes,
                storage_key=attachment.storage_key,
            )
        )
        await self._session.flush()

    async def get_attachment(self, attachment_id: UUID) -> TicketAttachment | None:
        model = await self._session.get(SupportAttachmentModel, attachment_id)
        return self._to_attachment(model) if model else None
