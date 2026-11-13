"""mcc shift delay

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14 12:00:00

Must run on PostgreSQL and SQLite (DECISION-025).

`mcc_master.shift_delay` ("HH:MM"): the time taken off the clock when a collection is
entered on the web (DECISION-029). Existing MCCs get "00:00", so nothing changes for them.

The column is only added when missing: a database adopted from `create_all` (SchemaMigrator)
can already have it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003'
down_revision: str | Sequence[str] | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c['name'] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if _has_column('mcc_master', 'shift_delay'):
        return
    op.add_column(
        'mcc_master',
        sa.Column('shift_delay', sa.String(length=5), server_default='00:00', nullable=False),
    )


def downgrade() -> None:
    if not _has_column('mcc_master', 'shift_delay'):
        return
    with op.batch_alter_table('mcc_master') as batch:
        batch.drop_column('shift_delay')
