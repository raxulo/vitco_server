"""admin self brand

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-27 12:00:00

Must run on PostgreSQL and SQLite (DECISION-025).

Self Brand (issue #41): a Super Admin can give an Admin its own logo, shown on the
web to the Admin and everyone under it.

- `users.self_brand` (bool, default false) and `users.brand_logo_url` (nullable).
  Existing users get false / NULL, so nothing changes for them.
- `media_category_enum` gains BRAND (logos are kept in brand/<admin_id>/). PostgreSQL
  stores it as a native enum type; SQLite keeps the category as plain VARCHAR, so it
  needs nothing there.

Every step is skipped when already applied: a database adopted from `create_all`
(SchemaMigrator) can already have the columns.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0005'
down_revision: str | Sequence[str] | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c['name'] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column('users', 'self_brand'):
        op.add_column(
            'users',
            sa.Column('self_brand', sa.Boolean(), server_default=sa.false(), nullable=False),
        )
    if not _has_column('users', 'brand_logo_url'):
        op.add_column(
            'users',
            sa.Column('brand_logo_url', sa.String(length=255), nullable=True),
        )

    if op.get_bind().dialect.name == 'postgresql':
        # Runs inside the migration's transaction: SchemaMigrator hands Alembic an open
        # connection, so `autocommit_block()` is unavailable. PostgreSQL 12+ allows
        # ADD VALUE in a transaction; the new value is only used after commit.
        op.execute("ALTER TYPE media_category_enum ADD VALUE IF NOT EXISTS 'BRAND'")


def downgrade() -> None:
    # PostgreSQL cannot drop an enum value; BRAND stays on the type (unused)
    with op.batch_alter_table('users') as batch:
        if _has_column('users', 'brand_logo_url'):
            batch.drop_column('brand_logo_url')
        if _has_column('users', 'self_brand'):
            batch.drop_column('self_brand')
