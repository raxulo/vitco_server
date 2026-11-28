"""support calls

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-21 12:00:00

Must run on PostgreSQL and SQLite (DECISION-025).

Technical Support, Phase 29 (REQ-78): `support_call_logs`, one row per click-to-call with its outcome.
Activity numbers (REQ-79) are aggregates over existing tables; the extra indexes serve them.

Every step is skipped when already done: a database adopted from `create_all`
(SchemaMigrator) can already have the tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0009'
down_revision: str | Sequence[str] | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if not _has_table('support_call_logs'):
        op.create_table('support_call_logs',
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('member_user_id', sa.UUID(), nullable=False),
        sa.Column('requester_user_id', sa.UUID(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('outcome', sa.String(length=20), nullable=True),
        sa.Column('duration_s', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['member_user_id'], ['users.id'], name=op.f('fk_support_call_logs_member_user_id_users')),
        sa.ForeignKeyConstraint(['requester_user_id'], ['users.id'], name=op.f('fk_support_call_logs_requester_user_id_users'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], name=op.f('fk_support_call_logs_ticket_id_support_tickets'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_support_call_logs')),
        )
        with op.batch_alter_table('support_call_logs', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_support_call_logs_ticket_id'), ['ticket_id'], unique=False)
            batch_op.create_index('ix_support_call_logs_member_started', ['member_user_id', 'started_at'], unique=False)


def downgrade() -> None:
    if _has_table('support_call_logs'):
        op.drop_table('support_call_logs')
