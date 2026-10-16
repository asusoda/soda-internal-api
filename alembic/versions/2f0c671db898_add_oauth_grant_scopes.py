"""add the approved scopes of an mcp oauth grant

Revision ID: 2f0c671db898
Revises: aeaa90ab92f5
Create Date: 2026-10-16 10:02:45.554587

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2f0c671db898"
down_revision: str | Sequence[str] | None = "aeaa90ab92f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    # Null on an existing grant: the scopes of its machine token are the grant
    with op.batch_alter_table("oauth_grants", schema=None) as batch_op:
        batch_op.add_column(sa.Column("scopes", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("oauth_grants", schema=None) as batch_op:
        batch_op.drop_column("scopes")
