"""support message delete

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-28 12:00:00

Must run on PostgreSQL and SQLite (DECISION-025).

Technical Support: a sender may delete their own message. The row stays as a "deleted" placeholder,
so `deleted_at` and `deleted_by` are added to `support_ticket_messages`. Voice messages (kind AUDIO)
need no schema change: the kind is a plain string column.

Every step is skipped when already done: a database adopted from `create_all`
(SchemaMigrator) can already have the columns.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0010'
down_revision: str | Sequence[str] | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    return {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    existing = _columns('support_ticket_messages')
    with op.batch_alter_table('support_ticket_messages', schema=None) as batch_op:
        if 'deleted_at' not in existing:
            batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        if 'deleted_by' not in existing:
            batch_op.add_column(sa.Column('deleted_by', sa.UUID(), nullable=True))


def downgrade() -> None:
    existing = _columns('support_ticket_messages')
    with op.batch_alter_table('support_ticket_messages', schema=None) as batch_op:
        if 'deleted_by' in existing:
            batch_op.drop_column('deleted_by')
        if 'deleted_at' in existing:
            batch_op.drop_column('deleted_at')
