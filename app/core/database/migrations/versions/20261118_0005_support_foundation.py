"""support foundation

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-18 12:00:00

Must run on PostgreSQL and SQLite (DECISION-025).

Technical Support, Phase 25 (REQ-58 to REQ-64, DECISION-031):

- `users.role` gains `SUPPORT` (PostgreSQL native enum `role`; SQLite stores a plain string).
- `support_teams`, `support_roles`, `support_members` and `support_audit_log`.

Every step is skipped when already done: a database adopted from `create_all`
(SchemaMigrator) can already have the tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0005'
down_revision: str | Sequence[str] | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # SchemaMigrator runs every migration in one transaction (advisory lock). PostgreSQL 12+
        # allows ADD VALUE inside a transaction; the new value is only usable after the commit,
        # and nothing in this migration uses it.
        op.execute(sa.text("ALTER TYPE role ADD VALUE IF NOT EXISTS 'SUPPORT'"))

    if not _has_table('support_teams'):
        op.create_table('support_teams',
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=False),
        sa.Column('manager_user_id', sa.UUID(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['manager_user_id'], ['users.id'], name=op.f('fk_support_teams_manager_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_support_teams')),
        sa.UniqueConstraint('manager_user_id', name=op.f('uq_support_teams_manager_user_id')),
        )
        with op.batch_alter_table('support_teams', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_support_teams_code'), ['code'], unique=True)

    if not _has_table('support_roles'):
        op.create_table('support_roles',
        sa.Column('team_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('permissions', sa.JSON(), nullable=False),
        sa.Column('is_system', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['team_id'], ['support_teams.id'], name=op.f('fk_support_roles_team_id_support_teams'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_support_roles')),
        sa.UniqueConstraint('team_id', 'name', name='uq_support_roles_team_name'),
        )
        with op.batch_alter_table('support_roles', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_support_roles_team_id'), ['team_id'], unique=False)

    if not _has_table('support_members'):
        op.create_table('support_members',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('team_id', sa.UUID(), nullable=False),
        sa.Column('role_id', sa.UUID(), nullable=True),
        sa.Column('is_manager', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['role_id'], ['support_roles.id'], name=op.f('fk_support_members_role_id_support_roles')),
        sa.ForeignKeyConstraint(['team_id'], ['support_teams.id'], name=op.f('fk_support_members_team_id_support_teams'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_support_members_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_support_members')),
        sa.UniqueConstraint('user_id', name=op.f('uq_support_members_user_id')),
        )
        with op.batch_alter_table('support_members', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_support_members_role_id'), ['role_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_support_members_team_id'), ['team_id'], unique=False)

    if not _has_table('support_audit_log'):
        op.create_table('support_audit_log',
        sa.Column('actor_id', sa.UUID(), nullable=True),
        sa.Column('team_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=60), nullable=False),
        sa.Column('entity', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=True),
        sa.Column('meta', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_support_audit_log')),
        )
        with op.batch_alter_table('support_audit_log', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_support_audit_log_actor_id'), ['actor_id'], unique=False)
            batch_op.create_index('ix_support_audit_log_team_created', ['team_id', 'created_at'], unique=False)


def downgrade() -> None:
    # The `SUPPORT` enum value stays: PostgreSQL cannot drop a value from an enum type.
    for table in ('support_audit_log', 'support_members', 'support_roles', 'support_teams'):
        if _has_table(table):
            op.drop_table(table)
