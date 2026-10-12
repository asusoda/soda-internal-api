"""add mcp oauth tables

Revision ID: aeaa90ab92f5
Revises: 378869ecefc5
Create Date: 2026-10-12 06:19:06.438396

The tables of OAuth for the MCP server: clients (registered, or cached Client ID Metadata Documents), open
authorization requests, approved grants, and the jti of used client assertions (private_key_jwt).
A grant points at the machine token of kind oauth that its client uses.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "aeaa90ab92f5"
down_revision: str | Sequence[str] | None = "378869ecefc5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=2048), nullable=False),
        sa.Column("info", sa.JSON(), nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=True),
        sa.Column("cache_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("oauth_clients", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_oauth_clients_client_id"), ["client_id"], unique=True)

    op.create_table(
        "oauth_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=2048), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=True),
        sa.Column("code_hash", sa.String(length=64), nullable=True),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("redirect_uri_explicit", sa.Boolean(), nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("requested_scopes", sa.JSON(), nullable=True),
        sa.Column("resource", sa.Text(), nullable=True),
        sa.Column("discord_id", sa.String(length=255), nullable=True),
        sa.Column("officer_org_ids", sa.JSON(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("limits", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["oauth_clients.client_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_table(
        "oauth_grants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("machine_token_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=2048), nullable=False),
        sa.Column("refresh_hash", sa.String(length=64), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["oauth_clients.client_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["machine_token_id"], ["machine_tokens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("oauth_grants", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_oauth_grants_machine_token_id"), ["machine_token_id"], unique=True)
        batch_op.create_index(batch_op.f("ix_oauth_grants_refresh_hash"), ["refresh_hash"], unique=True)
    op.create_table(
        "oauth_assertions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jti_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti_hash"),
    )
    with op.batch_alter_table("oauth_assertions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_oauth_assertions_expires_at"), ["expires_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("oauth_assertions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_oauth_assertions_expires_at"))

    op.drop_table("oauth_assertions")
    with op.batch_alter_table("oauth_grants", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_oauth_grants_refresh_hash"))
        batch_op.drop_index(batch_op.f("ix_oauth_grants_machine_token_id"))

    op.drop_table("oauth_grants")
    op.drop_table("oauth_requests")
    with op.batch_alter_table("oauth_clients", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_oauth_clients_client_id"))

    op.drop_table("oauth_clients")
