"""add org_limits (the superadmin's per-org limits) and usage_counters (rate limit use per window)

Revision ID: 055016fe0645
Revises: e9a1c3d5f7b9
Create Date: 2026-10-11 13:10:11.580265

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "055016fe0645"
down_revision: str | Sequence[str] | None = "e9a1c3d5f7b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "org_limits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_org_limit_key"),
    )
    with op.batch_alter_table("org_limits", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_org_limits_organization_id"), ["organization_id"], unique=False)

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("count", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", "window_start", name="uq_usage_counter_window"),
    )
    with op.batch_alter_table("usage_counters", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_usage_counters_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_usage_counters_window_start"), ["window_start"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("usage_counters", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_usage_counters_window_start"))
        batch_op.drop_index(batch_op.f("ix_usage_counters_organization_id"))

    op.drop_table("usage_counters")
    with op.batch_alter_table("org_limits", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_org_limits_organization_id"))

    op.drop_table("org_limits")
