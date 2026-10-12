"""Machine tokens: opaque bearer tokens for apps, agents and CLIs, one org each, with scopes.

The token is shown once at creation. The database keeps a SHA-256 hash, so a leaked database
does not leak usable tokens. No Flask here; routes and the MCP server both call these functions.
"""

import datetime
import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from core.time import iso, utcnow
from modules.auth.models import MachineToken
from modules.auth.scopes import SCOPES

PREFIX = "plat_"
KINDS = ("app", "agent", "cli")
# The kind of a token that an MCP OAuth client gets (modules/mcp/oauth.py). An officer cannot make one by hand.
OAUTH_KIND = "oauth"


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class MachineCaller:
    """Who a valid machine token stands for."""

    token_id: int
    organization_id: int
    name: str
    kind: str
    scopes: frozenset[str]
    created_by: str | None = None
    limits: dict = field(default_factory=dict, hash=False, compare=False)

    def allows(self, scope: str) -> bool:
        return scope in self.scopes

    def limit(self, integration: str, name: str) -> list[str] | None:
        """The token's list for one limit of an integration, or None when the token has no such limit."""
        value = (self.limits.get(integration) or {}).get(name)
        return list(value) if isinstance(value, list) else None

    @property
    def actor(self) -> str:
        """How the audit log and updated_by fields name this token."""
        return f"{self.kind}:{self.name}#{self.token_id}"


# Checks for the limits of each integration. Each one returns the cleaned limits or raises TokenError.
LIMIT_CHECKS: dict[str, Callable[[object], dict]] = {}
LIMIT_NAMES: dict[str, tuple[str, ...]] = {}


def declare_limits(integration: str, names: tuple[str, ...], check: Callable[[object], dict]) -> None:
    LIMIT_CHECKS[integration] = check
    LIMIT_NAMES[integration] = names


def check_limits(value: object) -> dict | None:
    """Cleaned per-integration limits, or None for no limits. Raises TokenError."""
    if value is None or value == {}:
        return None
    if not isinstance(value, dict):
        raise TokenError("limits must be an object of integration names")
    cleaned = {}
    for integration, limits in value.items():
        check = LIMIT_CHECKS.get(str(integration))
        if check is None:
            raise TokenError(f"No limits for {integration}")
        cleaned[integration] = check(limits)
    return cleaned


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def is_machine_token(token: str | None) -> bool:
    return bool(token) and str(token).startswith(PREFIX)


def _set_value(row: MachineToken) -> str:
    """Give the row a new token value. Returns the value; the row keeps its hash and first characters."""
    value = PREFIX + secrets.token_urlsafe(32)
    row.token_hash = _hash(value)
    row.display = value[: len(PREFIX) + 6]
    return value


def issue(
    db,
    *,
    organization_id: int,
    name: object,
    kind: object,
    scopes: object,
    created_by: str | None = None,
    expires_days: object = None,
    limits: object = None,
) -> tuple[str, MachineToken]:
    """Create a token from untrusted input. Returns the token value (shown once) and its row. Commits."""
    if not isinstance(name, str) or not name.strip():
        raise TokenError("name is required")
    if kind not in KINDS:
        raise TokenError(f"kind must be one of {', '.join(KINDS)}")
    if not isinstance(scopes, list) or not scopes:
        raise TokenError("scopes must be a non-empty list")
    unknown = [str(s) for s in scopes if s not in SCOPES]
    if unknown:
        raise TokenError(f"Unknown scope: {', '.join(unknown)}")
    if expires_days is not None and (not isinstance(expires_days, int) or expires_days < 1):
        raise TokenError("expires_days must be a positive integer")
    cleaned_limits = check_limits(limits)
    row = MachineToken(
        organization_id=organization_id,
        name=name.strip(),
        kind=kind,
        scopes=sorted(set(scopes)),
        limits=cleaned_limits,
        created_by=created_by,
        expires_at=utcnow() + datetime.timedelta(days=expires_days) if expires_days else None,
    )
    value = _set_value(row)
    db.add(row)
    db.commit()
    return value, row


def issue_oauth(
    db,
    *,
    organization_id: int,
    name: str,
    scopes: list[str],
    created_by: str,
    expires_seconds: int,
    limits: dict | None = None,
) -> tuple[str, MachineToken]:
    """A token of kind oauth for an MCP OAuth client that an officer approved. Does not commit.

    limits must be cleaned by check_limits.
    """
    row = MachineToken(
        organization_id=organization_id,
        name=name[:255],
        kind=OAUTH_KIND,
        scopes=sorted(set(scopes) & set(SCOPES)),
        limits=limits or None,
        created_by=created_by,
        expires_at=utcnow() + datetime.timedelta(seconds=expires_seconds),
    )
    value = _set_value(row)
    db.add(row)
    db.flush()
    return value, row


def rotate(db, row: MachineToken, expires_seconds: int, scopes: list[str] | None = None) -> str:
    """Replace the value of a token and set a new expiry. The old value stops working. Does not commit."""
    value = _set_value(row)
    row.expires_at = utcnow() + datetime.timedelta(seconds=expires_seconds)
    if scopes is not None:
        row.scopes = sorted(set(scopes) & {str(s) for s in cast(list, row.scopes or [])})
    return value


def verify(db, token: str | None) -> MachineCaller | None:
    """The caller for a valid, unrevoked, unexpired token, else None. Records last use."""
    if not is_machine_token(token):
        return None
    row = db.query(MachineToken).filter_by(token_hash=_hash(str(token))).first()
    now = utcnow()
    if row is None or row.revoked_at is not None or (row.expires_at is not None and row.expires_at <= now):
        return None
    if row.last_used_at is None or (now - row.last_used_at).total_seconds() > 60:
        row.last_used_at = now
        db.commit()
    return MachineCaller(
        token_id=int(row.id),
        organization_id=int(row.organization_id),
        name=str(row.name),
        kind=str(row.kind),
        scopes=frozenset(row.scopes or []),
        created_by=str(row.created_by) if row.created_by is not None else None,
        limits=dict(row.limits or {}),
    )


def revoke(db, organization_id: int, token_id: int) -> bool:
    row = db.query(MachineToken).filter_by(id=token_id, organization_id=organization_id).first()
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = utcnow()
    db.commit()
    return True


def to_dict(row: MachineToken) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "scopes": row.scopes,
        "limits": row.limits or {},
        "display": row.display,
        "created_by": row.created_by,
        "created_at": iso(row.created_at),
        "expires_at": iso(row.expires_at),
        "last_used_at": iso(row.last_used_at),
    }


def list_active(db, organization_id: int) -> list[dict]:
    rows = (
        db.query(MachineToken)
        .filter(MachineToken.organization_id == organization_id, MachineToken.revoked_at.is_(None))
        .order_by(MachineToken.id.desc())
        .all()
    )
    return [to_dict(row) for row in rows]
