"""notifications: device tokens and push outbox

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-20 12:00:00

Must run on PostgreSQL and SQLite (DECISION-025).

Push notifications for every module (REQ-76, REQ-77, DECISION-033); Technical Support is the first user:

- `notification_device_tokens`: FCM tokens of the app installations, one row per token.
- `notification_outbox`: pushes written with the change they report (`source` module + `reference_id`,
  no foreign key to any feature table), sent afterwards by the push worker.

Every step is skipped when already done: a database adopted from `create_all`
(SchemaMigrator) can already have the tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0008'
down_revision: str | Sequence[str] | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if not _has_table('notification_device_tokens'):
        op.create_table('notification_device_tokens',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('fcm_token', sa.String(length=512), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('app_version', sa.String(length=30), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_seen', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notification_device_tokens_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_device_tokens')),
        sa.UniqueConstraint('fcm_token', name=op.f('uq_notification_device_tokens_fcm_token')),
        )
        with op.batch_alter_table('notification_device_tokens', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_notification_device_tokens_user_id'), ['user_id'], unique=False)

    if not _has_table('notification_outbox'):
        op.create_table('notification_outbox',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('source', sa.String(length=30), nullable=False),
        sa.Column('type', sa.String(length=40), nullable=False),
        sa.Column('reference_id', sa.String(length=64), nullable=True),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('body', sa.String(length=255), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('skip_if_online', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notification_outbox_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_outbox')),
        )
        with op.batch_alter_table('notification_outbox', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_notification_outbox_user_id'), ['user_id'], unique=False)
            batch_op.create_index('ix_notification_outbox_status_next', ['status', 'next_attempt_at'], unique=False)
            batch_op.create_index('ix_notification_outbox_source_reference', ['source', 'reference_id'], unique=False)


def downgrade() -> None:
    for table in ('notification_outbox', 'notification_device_tokens'):
        if _has_table(table):
            op.drop_table(table)
