"""add shared apps

Revision ID: 378869ecefc5
Revises: c6e8a0b2d4f6
Create Date: 2026-10-11 17:49:06.482631

A shared app is a runpod_apps row with no org: the deployment owns it and orgs subscribe to it. Its secrets are
deployment secrets. The downgrade deletes the shared apps and their deployments.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "378869ecefc5"
down_revision: str | Sequence[str] | None = "c6e8a0b2d4f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "deployment_secrets",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_table(
        "shared_app_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("invited", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["app_id"], ["runpod_apps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("app_id", "organization_id", name="uq_shared_app_subscription"),
    )
    with op.batch_alter_table("runpod_apps", schema=None) as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.INTEGER(), nullable=True)


def downgrade() -> None:
    shared = (
        sa.select(sa.column("id")).select_from(sa.table("runpod_apps")).where(sa.column("organization_id").is_(None))
    )
    op.execute(sa.table("runpod_deployments", sa.column("app_id")).delete().where(sa.column("app_id").in_(shared)))
    op.execute(
        sa.table("runpod_apps", sa.column("organization_id")).delete().where(sa.column("organization_id").is_(None))
    )
    with op.batch_alter_table("runpod_apps", schema=None) as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.INTEGER(), nullable=False)

    op.drop_table("shared_app_subscriptions")
    op.drop_table("deployment_secrets")
