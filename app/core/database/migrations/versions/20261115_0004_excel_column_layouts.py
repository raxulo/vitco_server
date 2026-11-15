"""excel column layouts

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15 12:00:00

Must run on PostgreSQL and SQLite (DECISION-025).

`excel_column_layouts`: each Super Admin / Admin / Sub Admin's order and visibility of the
collection export columns (REQ-55, DECISION-030). No row = the default layout, so existing
users need no data.

The table is only created when missing: a database adopted from `create_all`
(SchemaMigrator) can already have it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0004'
down_revision: str | Sequence[str] | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = 'excel_column_layouts'


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if _has_table(_TABLE):
        return
    op.create_table(_TABLE,
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('sheet', sa.String(length=40), nullable=False),
    sa.Column('columns', sa.JSON(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('updated_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_excel_column_layouts_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_excel_column_layouts')),
    sa.UniqueConstraint('user_id', 'sheet', name='uq_excel_column_layouts_user_sheet')
    )
    with op.batch_alter_table(_TABLE, schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_excel_column_layouts_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    if not _has_table(_TABLE):
        return
    op.drop_table(_TABLE)
