"""Shared apps: apps the deployment owns on This server, which orgs subscribe to and use. No Flask here.

A shared app is an App row with no org. The superadmin registers, deploys and rolls it back with the same hosting
service as an org's app. Its secrets are deployment secrets named shared_<app>_<key>. A dash in the app name is
two underscores, so one app's secret cannot match another's. An org subscribes on the Shared tab of Explore.
The manifest's "access" field says what a subscription does in the app:

- vaultwarden: Platform signs in to the Vaultwarden admin page with the app's ADMIN_TOKEN and invites each email.
  Each person sets their own master password, so Platform never holds the keys of an org's vault. The first officer
  makes the org's Vaultwarden organization, and the org's items stay inside it.
"""

import re
from typing import Any, cast

import requests

from core import secrets
from core.errors import ServiceError
from core.log import get_logger
from core.time import iso
from modules.runpod import service
from modules.runpod.models import App, SharedAppSubscription

logger = get_logger(__name__)

SECRET_PREFIX = "shared_"  # nosec B105 - a secret name prefix, not a value
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,}$")
MAX_EMAILS = 20
TIMEOUT_SECONDS = 15
SECRET_KEY = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class SharedAppError(ServiceError, ValueError):
    pass


def _find(db, name: str) -> App:
    app = db.query(App).filter(App.organization_id.is_(None), App.name == name).first()
    if app is None:
        raise SharedAppError("No shared app with this name", 404)
    return app


def _manifest(app: App) -> dict:
    return service._manifest(app)


def _summary(db, app: App) -> dict:
    manifest = _manifest(app)
    subscribers = db.query(SharedAppSubscription).filter_by(app_id=app.id).count()
    return {
        "name": app.name,
        "kind": manifest.get("kind", "service"),
        "description": manifest.get("description"),
        "url": manifest.get("url"),
        "access": (manifest.get("access") or {}).get("kind"),
        "current_tag": app.current_tag,
        "subscribers": subscribers,
    }


# The superadmin side


def list_shared(db) -> list[dict]:
    """Every shared app, with its latest deployment and how many orgs subscribe."""
    apps = db.query(App).filter(App.organization_id.is_(None)).order_by(App.name).all()
    return [service._app_dict(db, app) | {"subscribers": _summary(db, app)["subscribers"]} for app in apps]


def put_shared(db, name: str, manifest: Any) -> dict:
    """Create a shared app or replace its manifest. Shared apps run on This server. Commits."""
    return service.put_app(db, None, name, manifest=manifest, provider=service.SERVER)


def get_shared(db, name: str) -> dict:
    app = _find(db, name)
    return service.get_app(db, None, name) | {
        "secrets": _secret_keys(db, name),
        "subscribers": [
            {"org_id": s.organization_id, "invited": len(s.invited or []), "since": iso(s.created_at)}
            for s in db.query(SharedAppSubscription).filter_by(app_id=app.id).all()
        ],
    }


def _secret_prefix(name: str) -> str:
    """shared_<app>_ with each dash in the app name written as two underscores."""
    return f"{SECRET_PREFIX}{name.replace('-', '__')}_"


def secret_name(app_name: str, key: str) -> str:
    """The deployment secret that a shared app's manifest names in secret_env."""
    return _secret_prefix(app_name) + key.lower()


def _secret_keys(db, name: str) -> list[str]:
    """The env keys saved for this app. A secret that only shares the name prefix of another app is left out."""
    prefix = _secret_prefix(name)
    keys = []
    for secret in secrets.deployment_secret_names(db, prefix):
        key = secret[len(prefix) :]
        if SECRET_KEY.match(key.upper()):
            keys.append(key)
    return keys


def set_secrets(db, name: str, values: Any, actor: str | None) -> dict:
    """Save or remove (null) the shared app's secrets, by env key. Values are never returned. Commits."""
    _find(db, name)
    if not isinstance(values, dict) or not values:
        raise SharedAppError('Send "secrets": an object of env key to value, or null to remove')
    chosen = []
    for key, value in values.items():
        if not isinstance(key, str) or not SECRET_KEY.match(key):
            raise SharedAppError("A secret key is an env name in capitals, such as ADMIN_TOKEN")
        secret = secret_name(name, key)
        if len(secret) > 100:
            raise SharedAppError("The secret name is too long. Use a shorter app name or env key")
        chosen.append((secret, value))
    for secret, value in chosen:
        try:
            if value is None:
                secrets.delete_deployment_secret(db, secret)
            else:
                secrets.set_deployment_secret(db, secret, value, actor)
        except secrets.SecretsError as e:
            raise SharedAppError(str(e), 503) from e
    return {"secrets": _secret_keys(db, name)}


# The org side


def for_org(db, org_id: int) -> list[dict]:
    """The deployed shared apps that orgs subscribe to (those with an access kind), and whether the org subscribes
    and whom it invited. Others, such as the embedding server, are the deployment's own."""
    apps = db.query(App).filter(App.organization_id.is_(None), App.current_tag.isnot(None)).order_by(App.name).all()
    apps = [a for a in apps if (_manifest(a).get("access") or {}).get("kind")]
    mine = {s.app_id: s for s in db.query(SharedAppSubscription).filter_by(organization_id=org_id).all()}
    out = []
    for app in apps:
        sub = mine.get(app.id)
        out.append(
            _summary(db, app)
            | {"subscribed": sub is not None, "invited": list(cast(list, sub.invited) or []) if sub else []}
        )
    return out


def _emails(value: Any) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > MAX_EMAILS:
        raise SharedAppError(f"Send emails: a list of 1 to {MAX_EMAILS} email addresses")
    found = []
    for email in value:
        if not isinstance(email, str) or not EMAIL.match(email.strip()):
            raise SharedAppError(f"Not an email address: {email}")
        found.append(email.strip().lower())
    return sorted(set(found))


def _vaultwarden_invite(db, app: App, emails: list[str]) -> dict[str, str]:
    """Invite each email to Vaultwarden through its admin page. Returns email to result."""
    manifest = _manifest(app)
    base = str(manifest.get("url") or "").rstrip("/")
    token_name = (manifest.get("secret_env") or {}).get("ADMIN_TOKEN")
    token = secrets.get_deployment_secret(db, token_name) if token_name else None
    if not base or not token:
        raise SharedAppError("The vault has no url or no ADMIN_TOKEN secret yet. Ask the superadmin", 409)
    session = requests.Session()
    session.headers["User-Agent"] = "Platform shared apps"
    try:
        login = session.post(f"{base}/admin", data={"token": token}, timeout=TIMEOUT_SECONDS, allow_redirects=False)
    except requests.RequestException as e:
        raise SharedAppError(f"The vault did not answer: {type(e).__name__}", 502) from e
    if login.status_code >= 400 or "VW_ADMIN" not in session.cookies:
        raise SharedAppError("The vault refused the admin token. Ask the superadmin to save it again", 502)
    results = {}
    for email in emails:
        try:
            response = session.post(f"{base}/admin/invite", json={"email": email}, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as e:
            results[email] = f"not invited: {type(e).__name__}"
            continue
        if response.status_code < 400:
            results[email] = "invited"
        elif response.status_code == 409 or "already" in response.text.lower():
            results[email] = "already has an account"
        else:
            results[email] = f"not invited: the vault answered {response.status_code}"
    return results


ACCESS = {"vaultwarden": _vaultwarden_invite}


def subscribe(db, org_id: int, name: str, emails: Any, actor: str | None) -> dict:
    """Subscribe the org to a shared app and give the emails access, as the app's access kind says. Commits."""
    app = _find(db, name)
    if not app.current_tag:
        raise SharedAppError("This shared app is not deployed yet", 409)
    access = (_manifest(app).get("access") or {}).get("kind")
    if not access:
        raise SharedAppError("Orgs do not subscribe to this shared app", 409)
    chosen = _emails(emails) if access else []
    results = ACCESS[access](db, app, chosen) if access else {}
    sub = db.query(SharedAppSubscription).filter_by(app_id=app.id, organization_id=org_id).first()
    if sub is None:
        sub = SharedAppSubscription(app_id=app.id, organization_id=org_id, invited=[], created_by=actor)
        db.add(sub)
    done = [email for email, result in results.items() if not result.startswith("not ")]
    sub.invited = sorted({*(sub.invited or []), *done})
    db.commit()
    logger.info("shared app subscribed app=%s org=%s invited=%s", name, org_id, len(done))
    return {"name": name, "subscribed": True, "results": results, "invited": sub.invited}


def unsubscribe(db, org_id: int, name: str) -> dict:
    """End the org's subscription. The accounts in the app stay; the app's admin removes them. Commits."""
    app = _find(db, name)
    db.query(SharedAppSubscription).filter_by(app_id=app.id, organization_id=org_id).delete()
    db.commit()
    return {"name": name, "subscribed": False}
