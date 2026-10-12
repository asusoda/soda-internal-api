from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from core.db import Base
from core.time import utcnow


class OAuthClient(Base):
    """An MCP client that registered itself with dynamic client registration (RFC 7591)."""

    __tablename__ = "oauth_clients"
    id = Column(Integer, primary_key=True)
    client_id = Column(String(64), unique=True, nullable=False, index=True)
    # The registered metadata without the secret: redirect_uris, client_name, token_endpoint_auth_method
    info = Column(JSON, nullable=False)
    # The client secret, encrypted with SECRETS_KEY. None for a public client
    secret_ciphertext = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_used_at = Column(DateTime, default=utcnow, nullable=False)


class OAuthRequest(Base):
    """One authorization request, from /authorize to the code exchange. Only hashes of its secrets are stored.

    key_hash is the hash of the browser cookie: first the sign-in key, then the consent key after Discord
    sign-in. code_hash is set when an officer approves.
    """

    __tablename__ = "oauth_requests"
    id = Column(Integer, primary_key=True)
    client_id = Column(String(64), ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=True)
    code_hash = Column(String(64), unique=True, nullable=True)
    redirect_uri = Column(Text, nullable=False)
    redirect_uri_explicit = Column(Boolean, nullable=False, default=True)
    state = Column(Text, nullable=True)
    code_challenge = Column(String(128), nullable=False)
    requested_scopes = Column(JSON, nullable=True)
    resource = Column(Text, nullable=True)
    discord_id = Column(String(255), nullable=True)
    # The ids of the orgs where the signed-in member is an officer
    officer_org_ids = Column(JSON, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    scopes = Column(JSON, nullable=True)
    # Per-integration limits that the officer chose, as on machine_tokens
    limits = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class OAuthGrant(Base):
    """An approved OAuth connection: the machine token that the client uses and the hash of its refresh token."""

    __tablename__ = "oauth_grants"
    id = Column(Integer, primary_key=True)
    machine_token_id = Column(
        Integer, ForeignKey("machine_tokens.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    client_id = Column(String(64), ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False)
    refresh_hash = Column(String(64), unique=True, nullable=False, index=True)
    refresh_expires_at = Column(DateTime, nullable=False)
    resource = Column(Text, nullable=True)
    # The last time a refresh found that the approving officer still has the officer role
    checked_at = Column(DateTime, default=utcnow, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
