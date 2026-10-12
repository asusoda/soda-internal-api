"""Per-organization secrets (API tokens an org brings for its own integrations), encrypted at rest, and the
deployment's own secrets, such as the admin token of a shared app.

Modules declare the secrets they read with declare(). Values are encrypted with Fernet using
SECRETS_KEY; to rotate, put the new key first and keep the old one after a comma until every
secret has been saved again. Without SECRETS_KEY, secrets cannot be saved and reads return None,
so callers fall back to the instance-wide setting. The API never returns a secret's value.
"""

import os
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base
from core.log import get_logger

logger = get_logger("secrets")

# name -> description, filled by the modules that read them
KNOWN: dict[str, str] = {}
# name prefix -> description, for modules whose secrets are named by the org (app env values)
PREFIXES: dict[str, str] = {}


class SecretsError(ValueError):
    pass


class OrgSecret(Base):
    __tablename__ = "org_secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_org_secret_name"),)


class DeploymentSecret(Base):
    """A secret of the deployment, not of an org, such as the admin token of a shared app."""

    __tablename__ = "deployment_secrets"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


def declare(name: str, description: str) -> None:
    KNOWN[name] = description


def declare_prefix(prefix: str, description: str) -> None:
    PREFIXES[prefix] = description


def _allowed(name: str) -> bool:
    if name in KNOWN:
        return True
    return any(name.startswith(p) and len(name) > len(p) and len(name) <= 100 for p in PREFIXES)


def _fernet() -> MultiFernet | None:
    keys = [k.strip() for k in os.environ.get("SECRETS_KEY", "").split(",") if k.strip()]
    if not keys:
        return None
    return MultiFernet([Fernet(k) for k in keys])


def configured() -> bool:
    return _fernet() is not None


def encrypt(text: str) -> str | None:
    """Encrypt with SECRETS_KEY, or None when it is not configured."""
    fernet = _fernet()
    return fernet.encrypt(text.encode()).decode() if fernet else None


def decrypt(ciphertext: str) -> str | None:
    """Decrypt with SECRETS_KEY, or None when it is missing or the key does not match."""
    fernet = _fernet()
    if fernet is None:
        return None
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return None


def set_secret(db, org_id: int, name: str, value: object, updated_by: str | None = None) -> None:
    """Encrypt and store a secret. Commits."""
    if not _allowed(name):
        raise SecretsError(f"Unknown secret: {name}")
    if not isinstance(value, str) or not value.strip():
        raise SecretsError("Value must be a non-empty string")
    fernet = _fernet()
    if fernet is None:
        raise SecretsError("SECRETS_KEY is not configured on this server")
    ciphertext = fernet.encrypt(value.strip().encode()).decode()
    row = db.query(OrgSecret).filter_by(organization_id=org_id, name=name).first()
    if row is None:
        row = OrgSecret(organization_id=org_id, name=name)
        db.add(row)
    row.ciphertext = ciphertext
    row.updated_at = datetime.now(UTC)
    row.updated_by = updated_by
    db.commit()


def get_secret(db, org_id: int, name: str) -> str | None:
    """The decrypted value, or None if unset, undecryptable, or SECRETS_KEY is missing."""
    row = db.query(OrgSecret).filter_by(organization_id=org_id, name=name).first()
    if row is None:
        return None
    fernet = _fernet()
    if fernet is None:
        logger.warning("secret %s is set for org %s but SECRETS_KEY is missing", name, org_id)
        return None
    try:
        return fernet.decrypt(str(row.ciphertext).encode()).decode()
    except InvalidToken:
        logger.error("secret %s for org %s cannot be decrypted with SECRETS_KEY", name, org_id)
        return None


def delete_secret(db, org_id: int, name: str) -> bool:
    row = db.query(OrgSecret).filter_by(organization_id=org_id, name=name).first()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def list_secrets(db, org_id: int) -> list[dict]:
    """Every declared secret, and every prefixed one the org set, and whether it is set. Never includes values."""
    rows = {row.name: row for row in db.query(OrgSecret).filter_by(organization_id=org_id).all()}
    named = dict(KNOWN)
    for name in rows:
        prefix = next((p for p in PREFIXES if name.startswith(p)), None)
        if name not in named and prefix is not None:
            named[name] = PREFIXES[prefix]
    return [
        {
            "name": name,
            "description": description,
            "set": name in rows,
            "updated_at": rows[name].updated_at.isoformat() if name in rows else None,
            "updated_by": rows[name].updated_by if name in rows else None,
        }
        for name, description in sorted(named.items())
    ]


def set_deployment_secret(db, name: str, value: object, updated_by: str | None = None) -> None:
    """Encrypt and store a secret of the deployment. Commits."""
    if not isinstance(value, str) or not value.strip():
        raise SecretsError("Value must be a non-empty string")
    ciphertext = encrypt(value.strip())
    if ciphertext is None:
        raise SecretsError("SECRETS_KEY is not configured on this server")
    row = db.get(DeploymentSecret, name)
    if row is None:
        row = DeploymentSecret(name=name)
        db.add(row)
    row.ciphertext, row.updated_at, row.updated_by = ciphertext, datetime.now(UTC), updated_by
    db.commit()


def get_deployment_secret(db, name: str) -> str | None:
    """The decrypted value of a deployment secret, or None when it is unset or cannot be decrypted."""
    row = db.get(DeploymentSecret, name)
    return decrypt(str(row.ciphertext)) if row is not None else None


def delete_deployment_secret(db, name: str) -> bool:
    row = db.get(DeploymentSecret, name)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def deployment_secret_names(db, prefix: str) -> list[str]:
    """The names of the deployment secrets that start with prefix. Never the values."""
    return sorted(n for (n,) in db.query(DeploymentSecret.name).filter(DeploymentSecret.name.startswith(prefix)))
