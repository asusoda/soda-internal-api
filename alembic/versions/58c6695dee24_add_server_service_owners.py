"""add server service owners

Revision ID: 58c6695dee24
Revises: b4d6f8a0c2e4
Create Date: 2026-10-11 15:35:33.917506

The superadmin sets who owns each container or host process that the host agent lists.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "58c6695dee24"
down_revision: str | Sequence[str] | None = "b4d6f8a0c2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "server_service_owners",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("owner", sa.String(length=16), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("server_service_owners")
