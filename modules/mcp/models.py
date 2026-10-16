from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base
from core.time import utcnow


class OAuthClient(Base):
    """An MCP client: one that registered itself (RFC 7591), or the cached Client ID Metadata Document of one."""

    __tablename__ = "oauth_clients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # An id from /register, or the https URL of a Client ID Metadata Document
    client_id: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False, index=True)
    # The registered metadata without the secret: redirect_uris, client_name, token_endpoint_auth_method
    info: Mapped[Any] = mapped_column(JSON, nullable=False)
    # The client secret, encrypted with SECRETS_KEY. None for a public client
    secret_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    # For a metadata document: the time to fetch it again. None for a client from /register
    cache_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class OAuthRequest(Base):
    """One authorization request, from /authorize to the code exchange. Only hashes of its secrets are stored.

    key_hash is the hash of the browser cookie: first the sign-in key, then the consent key after Discord
    sign-in. code_hash is set when an officer approves.
    """

    __tablename__ = "oauth_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[str] = mapped_column(
        String(2048), ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False
    )
    key_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    code_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri_explicit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_scopes: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    resource: Mapped[str | None] = mapped_column(Text, nullable=True)
    discord_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # The ids of the orgs where the signed-in member is an officer
    officer_org_ids: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    scopes: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    # Per-integration limits that the officer chose, as on machine_tokens
    limits: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OAuthGrant(Base):
    """An approved OAuth connection: the machine token that the client uses and the hash of its refresh token."""

    __tablename__ = "oauth_grants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_token_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("machine_tokens.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    client_id: Mapped[str] = mapped_column(
        String(2048), ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False
    )
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resource: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The scopes the officer approved. A refresh can ask for fewer for the access token, never for more.
    # None on a grant from before this column: the scopes of its machine token are the grant.
    scopes: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    # The last time a refresh found that the approving officer still has the officer role
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class OAuthAssertion(Base):
    """A client assertion (RFC 7523) that was used, until it expires, so that it cannot be used again."""

    __tablename__ = "oauth_assertions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # SHA-256 of the client_id and the jti of the assertion
    jti_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
