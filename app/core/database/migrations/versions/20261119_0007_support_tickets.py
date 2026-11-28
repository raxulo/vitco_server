"""support tickets

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-19 12:00:00

Must run on PostgreSQL and SQLite (DECISION-025).

Technical Support, Phase 26 (REQ-66 to REQ-72):

- `support_categories`, `support_ticket_counters`, `support_tickets`,
  `support_ticket_messages`, `support_ticket_events` and `support_attachments`.
- Status, priority, message kind and event type are plain string columns (no native enum),
  so adding a value later needs no migration on PostgreSQL.

Every step is skipped when already done: a database adopted from `create_all`
(SchemaMigrator) can already have the tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0007'
down_revision: str | Sequence[str] | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# BIGINT on PostgreSQL, INTEGER on SQLite (the only type that auto-increments there)
_SEQ = sa.BigInteger().with_variant(sa.Integer(), 'sqlite')


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    ]


def upgrade() -> None:
    if not _has_table('support_categories'):
        op.create_table('support_categories',
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('default_team_id', sa.UUID(), nullable=True),
        sa.Column('default_priority', sa.String(length=10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('sla_minutes', sa.Integer(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['default_team_id'], ['support_teams.id'], name=op.f('fk_support_categories_default_team_id_support_teams'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_support_categories')),
        sa.UniqueConstraint('name', name=op.f('uq_support_categories_name')),
        )

    if not _has_table('support_ticket_counters'):
        op.create_table('support_ticket_counters',
        sa.Column('year', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('last_value', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('year', name=op.f('pk_support_ticket_counters')),
        )

    if not _has_table('support_tickets'):
        op.create_table('support_tickets',
        sa.Column('ticket_no', sa.String(length=20), nullable=False),
        sa.Column('requester_user_id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=False),
        sa.Column('team_id', sa.UUID(), nullable=True),
        sa.Column('assigned_to', sa.UUID(), nullable=True),
        sa.Column('priority', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('subject', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('device_model', sa.String(length=100), nullable=True),
        sa.Column('os_version', sa.String(length=50), nullable=True),
        sa.Column('app_version', sa.String(length=30), nullable=True),
        sa.Column('client_request_id', sa.String(length=64), nullable=True),
        sa.Column('first_response_at', sa.DateTime(), nullable=True),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('sla_due_at', sa.DateTime(), nullable=True),
        sa.Column('requester_unread', sa.Integer(), nullable=False),
        sa.Column('staff_unread', sa.Integer(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], name=op.f('fk_support_tickets_assigned_to_users')),
        sa.ForeignKeyConstraint(['category_id'], ['support_categories.id'], name=op.f('fk_support_tickets_category_id_support_categories')),
        sa.ForeignKeyConstraint(['requester_user_id'], ['users.id'], name=op.f('fk_support_tickets_requester_user_id_users')),
        sa.ForeignKeyConstraint(['team_id'], ['support_teams.id'], name=op.f('fk_support_tickets_team_id_support_teams')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_support_tickets')),
        sa.UniqueConstraint('requester_user_id', 'client_request_id', name='uq_support_tickets_client_request'),
        )
        with op.batch_alter_table('support_tickets', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_support_tickets_ticket_no'), ['ticket_no'], unique=True)
            batch_op.create_index(batch_op.f('ix_support_tickets_requester_user_id'), ['requester_user_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_support_tickets_category_id'), ['category_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_support_tickets_last_message_at'), ['last_message_at'], unique=False)
            batch_op.create_index('ix_support_tickets_team_status', ['team_id', 'status'], unique=False)
            batch_op.create_index('ix_support_tickets_assigned_status', ['assigned_to', 'status'], unique=False)

    if not _has_table('support_ticket_messages'):
        op.create_table('support_ticket_messages',
        sa.Column('id', _SEQ, autoincrement=True, nullable=False),
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('sender_user_id', sa.UUID(), nullable=True),
        sa.Column('sender_is_staff', sa.Boolean(), nullable=False),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_internal', sa.Boolean(), nullable=False),
        sa.Column('client_request_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], name=op.f('fk_support_ticket_messages_sender_user_id_users')),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], name=op.f('fk_support_ticket_messages_ticket_id_support_tickets'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_support_ticket_messages')),
        sa.UniqueConstraint('ticket_id', 'sender_user_id', 'client_request_id', name='uq_support_messages_client_request'),
        )
        with op.batch_alter_table('support_ticket_messages', schema=None) as batch_op:
            batch_op.create_index('ix_support_ticket_messages_ticket_id_id', ['ticket_id', 'id'], unique=False)

    if not _has_table('support_ticket_events'):
        op.create_table('support_ticket_events',
        sa.Column('id', _SEQ, autoincrement=True, nullable=False),
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('actor_user_id', sa.UUID(), nullable=True),
        sa.Column('event_type', sa.String(length=24), nullable=False),
        sa.Column('from_value', sa.String(length=80), nullable=True),
        sa.Column('to_value', sa.String(length=80), nullable=True),
        sa.Column('meta', sa.JSON(), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], name=op.f('fk_support_ticket_events_actor_user_id_users')),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], name=op.f('fk_support_ticket_events_ticket_id_support_tickets'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_support_ticket_events')),
        )
        with op.batch_alter_table('support_ticket_events', schema=None) as batch_op:
            batch_op.create_index('ix_support_ticket_events_ticket_id_id', ['ticket_id', 'id'], unique=False)

    if not _has_table('support_attachments'):
        op.create_table('support_attachments',
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('message_id', _SEQ, nullable=True),
        sa.Column('uploaded_by', sa.UUID(), nullable=True),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['support_ticket_messages.id'], name=op.f('fk_support_attachments_message_id_support_ticket_messages'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], name=op.f('fk_support_attachments_ticket_id_support_tickets'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('fk_support_attachments_uploaded_by_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_support_attachments')),
        )
        with op.batch_alter_table('support_attachments', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_support_attachments_ticket_id'), ['ticket_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_support_attachments_message_id'), ['message_id'], unique=False)


def downgrade() -> None:
    for table in (
        'support_attachments', 'support_ticket_events', 'support_ticket_messages',
        'support_tickets', 'support_ticket_counters', 'support_categories',
    ):
        if _has_table(table):
            op.drop_table(table)
