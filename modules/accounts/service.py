"""Members' connected accounts: logins, encrypted grants, and access tokens for agents. No Flask here.

An agent starts a login for a member and sends them the link. The link first has the browser sign
in to Discord, and the login continues only if that Discord account is the member the login was
started for, so a forwarded link cannot connect someone else's account. The provider then redirects
back with a code, and the grant is stored encrypted with SECRETS_KEY. Agents read a fresh access
token when they call the provider for the member; the platform refreshes it when it is near expiry.
"""

import datetime
import secrets as token_bytes

from core import secrets
from core.errors import ServiceError
from core.log import get_logger
from core.time import iso, utcnow
from modules.accounts import providers
from modules.accounts.models import AccountGrant, AccountLogin
from modules.auth import scopes

logger = get_logger("accounts")

scopes.declare("accounts:link", "Start logins for members, list and remove their connected accounts")
scopes.declare("accounts:token", "Read access tokens of members' connected accounts")

LOGIN_SECONDS = 600
REFRESH_MARGIN = datetime.timedelta(seconds=60)


class AccountError(ServiceError, ValueError):
    pass


def member(discord_id: object) -> str:
    if not isinstance(discord_id, str) or not discord_id.isdigit() or len(discord_id) > 32:
        raise AccountError("discord_id must be a numeric Discord id")
    return discord_id


def _provider(name: str) -> providers.Provider:
    provider = providers.get(name)
    if provider is None:
        raise AccountError(f"{name} accounts are not enabled on this platform", 404)
    return provider


def begin_login(db, org_id: int, discord_id: str, provider_name: str) -> dict:
    """Start a login. Returns the link to send the member. Commits."""
    _provider(provider_name)
    if not secrets.configured():
        raise AccountError("SECRETS_KEY is not set, so tokens cannot be stored", 503)
    state = token_bytes.token_urlsafe(32)
    expires_at = utcnow() + datetime.timedelta(seconds=LOGIN_SECONDS)
    db.add(
        AccountLogin(
            state=state,
            organization_id=org_id,
            discord_id=member(discord_id),
            provider=provider_name,
            expires_at=expires_at,
        )
    )
    db.commit()
    return {"url": f"{providers.base_url()}/api/accounts/start/{state}", "expires_at": iso(expires_at)}


def open_login(db, state: str) -> AccountLogin:
    login = db.query(AccountLogin).filter_by(state=state).first()
    if login is None or login.expires_at <= utcnow():
        raise AccountError("This link has expired or was already used. Ask for a new one.", 404)
    return login


def verify_login(db, state: str, discord_id: str) -> str:
    """Record that Discord confirmed the member. Returns the provider's consent URL. Commits."""
    login = open_login(db, state)
    if not token_bytes.compare_digest(str(login.discord_id), discord_id):
        raise AccountError("You signed in to Discord as a different account than the one this link is for.", 403)
    provider = _provider(str(login.provider))
    login.verified_at = utcnow()
    db.commit()
    return provider.consent_url(state)


def finish_login(db, state: str, provider_name: str, code: str, session_discord_id: str | None) -> str:
    """Exchange the code and store the grant. One use. Returns the provider name. Commits."""
    login = open_login(db, state)
    if login.verified_at is None or login.provider != provider_name:
        raise AccountError("This link has expired or was already used. Ask for a new one.", 404)
    if session_discord_id is None or not token_bytes.compare_digest(str(login.discord_id), session_discord_id):
        raise AccountError("Finish the login in the same browser you started it in.", 403)
    org_id, discord_id = login.organization_id, str(login.discord_id)
    db.delete(login)
    db.commit()
    try:
        tokens = _provider(provider_name).exchange(code)
    except providers.ProviderError as e:
        raise AccountError(f"{provider_name} would not complete the login. Ask for a new link.", 502) from e
    _save(db, org_id, discord_id, provider_name, tokens)
    return provider_name


def _seal(value: str) -> str:
    sealed = secrets.encrypt(value)
    if sealed is None:
        raise AccountError("SECRETS_KEY is not set, so tokens cannot be stored", 503)
    return sealed


def _save(db, org_id: int, discord_id: str, provider_name: str, tokens: providers.Tokens) -> None:
    grant = (
        db.query(AccountGrant).filter_by(organization_id=org_id, discord_id=discord_id, provider=provider_name).first()
    )
    if grant is None:
        grant = AccountGrant(organization_id=org_id, discord_id=discord_id, provider=provider_name)
        db.add(grant)
    grant.access_token = _seal(tokens.access_token)
    grant.refresh_token = _seal(tokens.refresh_token) if tokens.refresh_token else None
    grant.scopes = tokens.scopes
    grant.expires_at = tokens.expires_at
    grant.updated_at = utcnow()
    db.commit()


def list_grants(db, org_id: int, discord_id: str) -> list[dict]:
    grants = (
        db.query(AccountGrant)
        .filter_by(organization_id=org_id, discord_id=member(discord_id))
        .order_by(AccountGrant.provider)
        .all()
    )
    return [
        {
            "provider": g.provider,
            "scopes": str(g.scopes or "").split(),
            "expires_at": iso(g.expires_at),
            "connected_at": iso(g.created_at),
            "updated_at": iso(g.updated_at),
        }
        for g in grants
    ]


def disconnect(db, org_id: int, discord_id: str, provider_name: str) -> bool:
    deleted = (
        db.query(AccountGrant)
        .filter_by(organization_id=org_id, discord_id=member(discord_id), provider=provider_name)
        .delete(synchronize_session=False)
    )
    db.commit()
    return bool(deleted)


def access_token(db, org_id: int, discord_id: str, provider_name: str) -> dict:
    """A usable access token, refreshed when it expires within a minute. Commits on refresh."""
    grant = (
        db.query(AccountGrant)
        .filter_by(organization_id=org_id, discord_id=member(discord_id), provider=provider_name)
        .first()
    )
    if grant is None:
        raise AccountError(f"The member has not connected {provider_name}", 404)
    access = secrets.decrypt(str(grant.access_token))
    if access is None:
        raise AccountError("The stored token cannot be decrypted with SECRETS_KEY", 503)

    if grant.expires_at is not None and grant.expires_at - REFRESH_MARGIN <= utcnow():
        refresh = secrets.decrypt(str(grant.refresh_token)) if grant.refresh_token else None
        if refresh is None:
            raise AccountError(f"The {provider_name} connection expired. The member has to connect again.", 409)
        try:
            tokens = _provider(provider_name).refresh(refresh, str(grant.scopes or ""))
        except providers.ProviderError as e:
            if e.refused:
                db.delete(grant)
                db.commit()
                raise AccountError(
                    f"{provider_name} revoked the connection. The member has to connect again.", 409
                ) from e
            raise AccountError(f"{provider_name} could not refresh the token", 502) from e
        _save(db, org_id, str(grant.discord_id), provider_name, tokens)
        access = tokens.access_token

    return {"access_token": access, "scopes": str(grant.scopes or "").split(), "expires_at": iso(grant.expires_at)}


def prune(db, now: datetime.datetime | None = None) -> dict:
    """Delete logins past their expiry. Commits."""
    deleted = (
        db.query(AccountLogin).filter(AccountLogin.expires_at <= (now or utcnow())).delete(synchronize_session=False)
    )
    db.commit()
    return {"logins": deleted}
