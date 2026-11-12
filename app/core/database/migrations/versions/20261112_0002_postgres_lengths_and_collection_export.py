"""postgres column lengths and collection export job kinds

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12 23:40:00

Must run on PostgreSQL and SQLite (DECISION-025).

- `exceljobkind` gets MCC_COLLECTION_EXPORT and VLCC_COLLECTION_EXPORT (DECISION-028).
- `users.mobile` 20 -> 32 and `farmer_master.farmer_code` 30 -> 50: a soft delete stores
  "del_<6 hex>_" + the mobile and "<code>__del_<6 hex>", which PostgreSQL refused as too long.

All three are PostgreSQL-only. SQLite keeps enum values as plain text and never enforces a
VARCHAR length, and changing a length there would rebuild these large, much-referenced tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0002'
down_revision: str | Sequence[str] | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_JOB_KINDS = ('MCC_COLLECTION_EXPORT', 'VLCC_COLLECTION_EXPORT')


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == 'postgresql'


def upgrade() -> None:
    if not _is_postgres():
        return
    for kind in _NEW_JOB_KINDS:
        op.execute(f"ALTER TYPE exceljobkind ADD VALUE IF NOT EXISTS '{kind}'")
    op.alter_column('users', 'mobile', existing_type=sa.String(length=20), type_=sa.String(length=32),
                    existing_nullable=True)
    op.alter_column('farmer_master', 'farmer_code', existing_type=sa.String(length=30), type_=sa.String(length=50),
                    existing_nullable=False)


def downgrade() -> None:
    # Enum values cannot be dropped in PostgreSQL; shortening a column could cut stored values
    if not _is_postgres():
        return
    op.alter_column('farmer_master', 'farmer_code', existing_type=sa.String(length=50), type_=sa.String(length=30),
                    existing_nullable=False)
    op.alter_column('users', 'mobile', existing_type=sa.String(length=32), type_=sa.String(length=20),
                    existing_nullable=True)
