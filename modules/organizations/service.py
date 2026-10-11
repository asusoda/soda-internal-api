"""Organization logic shared by the REST API, the bot and jobs. No Flask here."""

import re
from typing import cast
from urllib.parse import urlparse

from sqlalchemy.orm.attributes import flag_modified

from core import secrets
from core.errors import ServiceError
from modules.auth import machine_tokens, scopes
from modules.manifest import NEW_ORG_MODULES
from modules.organizations.models import Organization

scopes.declare("org:read", "Read the org's name, description, settings and enabled modules")
scopes.declare(
    "settings:write",
    "Turn modules on or off; change the description, points settings, branding, CI repos and LeetCode post; "
    "resolve and delete notifications and errors",
)
scopes.declare("secrets:manage", "List the names of the org's secrets, and set or delete them. Values are never read")
scopes.declare(
    "tokens:manage",
    "List, make and revoke machine tokens. A token made with a tool gets only scopes that the calling token has",
)

# Modules an organization can turn off. Every other module is always on. A module missing from an org's config is
# on, so existing orgs keep every feature until an officer turns one off. A new org starts with the modules in
# NEW_ORG_MODULES of modules/manifest.py on and the rest of these off.
OPTIONAL_MODULES = {
    "points": "Points, leaderboards and event check-ins",
    "storefront": "Merch store paid with points",
    "calendar": "Notion to Google Calendar sync and the public events feed",
    "games": "Jeopardy games in the org's Discord server",
    "leetcode": "Daily LeetCode post in the org's channel, with solve checks",
    "godfather": "GPU and CPU pods on the org's RunPod account that members SSH into",
    "event_webhook": "Events of the org, such as a failed job, sent to Discord webhooks",
    "job_webhook": "New internship and new grad roles posted to a Discord webhook",
    "hackathon_webhook": "Upcoming hackathons posted to a Discord webhook",
    "uptime": "Checks of sites and Hosting apps, with an event when one goes down or up",
    "knowledge": "Pages and documents that agents search",
    "agents": "Conversations, memories and pending actions of the org's agents",
    "integrations": "Tools of the services the org connects, for agents",
    "accounts": "Accounts that members connect for agents to read",
    "runpod": "Apps the org deploys to a hosting provider",
}


class ModuleError(ValueError):
    pass


class OrganizationError(ValueError):
    pass


class BrandingError(ServiceError, ValueError):
    pass


class SettingsError(ServiceError, ValueError):
    pass


PREFIX_PATTERN = re.compile(r"^[a-z0-9_-]{2,20}$")
ACCENT_PATTERN = re.compile(r"#[0-9a-fA-F]{6}")
BRANDING_KEYS = ("logo_url", "accent_color", "website_url")
MAX_URL = 500


def find_by_prefix(db, prefix: str | None, *, active_only: bool = False) -> Organization | None:
    """The org with this prefix, or None. With active_only, an inactive org is None too."""
    query = db.query(Organization).filter_by(prefix=prefix)
    if active_only:
        query = query.filter_by(is_active=True)
    return query.first()


def name_for_guild(db, guild_id: object) -> str | None:
    """The name of the active org on this Discord server, or None."""
    org = db.query(Organization).filter_by(guild_id=str(guild_id), is_active=True).first()
    return cast(str, org.name) if org else None


def module_enabled(org: Organization, name: str) -> bool:
    if name not in OPTIONAL_MODULES:
        return True
    settings = (org.config or {}).get("modules") or {}
    return settings.get(name, True) is not False


def module_states(org: Organization) -> list[dict]:
    return [
        {"name": name, "description": description, "enabled": module_enabled(org, name)}
        for name, description in OPTIONAL_MODULES.items()
    ]


def limits(db, org: Organization) -> list[dict]:
    """Each declared limit for the org, what it uses, and whether the limit's module is on for it."""
    from core import limits as core_limits
    from modules.manifest import load_tools

    load_tools()  # imports every module's service, so each limit is declared
    return [row | {"enabled": module_enabled(org, row["module"])} for row in core_limits.report(db, cast(int, org.id))]


def new_org_switches() -> dict[str, bool]:
    """The module switches of a new org: on for the modules in NEW_ORG_MODULES, off for the others."""
    return {name: name in NEW_ORG_MODULES for name in OPTIONAL_MODULES}


def set_modules(db, org: Organization, changes: object) -> list[dict]:
    """Turn modules on or off. `changes` maps module name to a bool. Commits."""
    if not isinstance(changes, dict) or not changes:
        raise ModuleError("Send a non-empty object of module name to true or false")
    for name, enabled in changes.items():
        if name not in OPTIONAL_MODULES:
            raise ModuleError(f"Unknown or required module: {name}")
        if not isinstance(enabled, bool):
            raise ModuleError(f"Value for {name} must be true or false")
    config = dict(cast(dict, org.config) or {})
    config["modules"] = {**(config.get("modules") or {}), **changes}
    org.config = config
    flag_modified(org, "config")
    db.commit()
    return module_states(org)


def create_organization(
    db,
    *,
    name: str,
    prefix: str,
    guild_id: str,
    officer_role_id: str | None = None,
    description: str | None = None,
    modules_on: tuple[str, ...] = (),
    modules_off: tuple[str, ...] = (),
) -> Organization:
    """Create an org with default settings and the module switches of a new org, then the given changes. Commits."""
    from modules.organizations.config import OrganizationSettings

    if not PREFIX_PATTERN.match(prefix):
        raise OrganizationError("Prefix must be 2-20 characters of lowercase letters, numbers, - and _")
    if not str(guild_id).isdigit():
        raise OrganizationError("Guild id must be a Discord id (digits only)")
    if find_by_prefix(db, prefix):
        raise OrganizationError(f"Prefix {prefix} is taken")
    if db.query(Organization).filter_by(guild_id=str(guild_id)).first():
        raise OrganizationError(f"Guild {guild_id} already has an organization")
    unknown = [m for m in (*modules_on, *modules_off) if m not in OPTIONAL_MODULES]
    if unknown:
        raise OrganizationError(f"Unknown or required module: {', '.join(unknown)}")
    config = OrganizationSettings().to_dict()
    config["modules"] = new_org_switches() | dict.fromkeys(modules_on, True) | dict.fromkeys(modules_off, False)
    org = Organization(
        name=name,
        prefix=prefix,
        guild_id=str(guild_id),
        officer_role_id=officer_role_id,
        description=description,
        is_active=True,
        config=config,
    )
    db.add(org)
    db.commit()
    return org


def branding(org: Organization) -> dict:
    """The org's logo URL, accent color and website URL from config.branding, each None when unset."""
    saved = (cast(dict, org.config) or {}).get("branding") or {}
    return {key: saved.get(key) or None for key in BRANDING_KEYS}


def _clean_url(field: str, value: object) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > MAX_URL:
        raise BrandingError(f"{field} must be an https URL of at most {MAX_URL} characters")
    if any(ch.isspace() or ord(ch) < 32 for ch in value):
        raise BrandingError(f"{field} must not contain spaces or control characters")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise BrandingError(f"{field} must be an https URL")
    return value


def _clean_accent(value: object) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not ACCENT_PATTERN.fullmatch(value):
        raise BrandingError("accent_color must be a hex color like #1f6feb")
    return value.lower()


def set_branding(db, org: Organization, changes: object) -> dict:
    """Update the given branding keys. An empty string or null clears a key. Commits."""
    if not isinstance(changes, dict) or not changes:
        raise BrandingError("Send an object with one or more of logo_url, accent_color and website_url")
    unknown = [key for key in changes if key not in BRANDING_KEYS]
    if unknown:
        raise BrandingError(f"Unknown branding field: {', '.join(sorted(unknown))}")
    current = branding(org)
    for field in ("logo_url", "website_url"):
        if field in changes:
            current[field] = _clean_url(field, cast(dict, changes)[field])
    if "accent_color" in changes:
        current["accent_color"] = _clean_accent(cast(dict, changes)["accent_color"])
    config = dict(cast(dict, org.config) or {})
    config["branding"] = {key: value for key, value in current.items() if value}
    org.config = config
    flag_modified(org, "config")
    db.commit()
    return branding(org)


MAX_DESCRIPTION = 500
SETTING_KEYS = ("description", "points_per_message", "points_cooldown")


def settings(org: Organization) -> dict:
    """The org's description, points for each message and the cooldown in seconds between them."""
    return {
        "name": org.name,
        "prefix": org.prefix,
        "description": org.description,
        "points_per_message": org.points_per_message,
        "points_cooldown": org.points_cooldown,
    }


def set_settings(db, org: Organization, changes: object) -> dict:
    """Set the description and points settings that changes has. Commits."""
    if not isinstance(changes, dict) or not changes or set(changes) - set(SETTING_KEYS):
        raise SettingsError(f"Send an object with one or more of {', '.join(SETTING_KEYS)}")
    changes = cast(dict, changes)
    if "description" in changes:
        value = changes["description"]
        if value is not None and (not isinstance(value, str) or len(value.strip()) > MAX_DESCRIPTION):
            raise SettingsError(f"description must be text of at most {MAX_DESCRIPTION} characters")
        org.description = value.strip() if value else None
    for key in ("points_per_message", "points_cooldown"):
        if key in changes:
            value = changes[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise SettingsError(f"{key} must be a whole number of 0 or more")
            setattr(org, key, value)
    db.commit()
    return settings(org)


# Org secrets and machine tokens


def active_org(db, org_id: int) -> Organization | None:
    """The active org with this id, or None."""
    return db.query(Organization).filter_by(id=org_id, is_active=True).first()


def secret_names(db, org_id: int) -> dict:
    """Whether SECRETS_KEY is set, and the names of the secrets the org saved. Values are never returned."""
    return {"configured": secrets.configured(), "secrets": secrets.list_secrets(db, org_id)}


def save_secret(db, org_id: int, name: str, value: object, set_by: str | None) -> None:
    """Save an org secret. Raises secrets.SecretsError when the name or value is refused."""
    secrets.set_secret(db, org_id, name, value, set_by)


def delete_secret(db, org_id: int, name: str) -> bool:
    """Delete an org secret. False when it was not set."""
    return secrets.delete_secret(db, org_id, name)


def token_list(db, org_id: int) -> dict:
    """The org's active machine tokens, the scopes a token can hold, and each integration with the scopes that reach it.

    An integration's scopes give its own tools: tools names the Platform tools under each scope, and remote is true
    when the tools come from the service's own MCP server. Its through scopes are Platform scopes that call it for
    the agent, and used_by names the modules that use it.
    """
    from core.integrations import registry
    from core.tools import TOOLS
    from modules.integrations.servers import SERVERS

    tools: dict[str, dict[str, list[str]]] = {}
    for spec in sorted(TOOLS.values(), key=lambda t: t.name):
        if spec.integration is not None:
            tools.setdefault(spec.integration, {}).setdefault(spec.scope, []).append(spec.name)

    direct: dict[str, list[str]] = {}
    for scope, integration in scopes.INTEGRATION_SCOPES.items():
        direct.setdefault(integration, []).append(scope)
    through: dict[str, list[str]] = {}
    for scope, keys in scopes.SCOPE_USES.items():
        for key in keys:
            through.setdefault(key, []).append(scope)
    titles = {key: i.title for key, i in registry.INTEGRATIONS.items()}
    keys = sorted(set(titles) | set(direct), key=lambda k: titles.get(k, k).lower())
    integrations = [
        {
            "key": key,
            "title": titles.get(key, key),
            "connected": registry.connected(db, org_id, key),
            "scopes": sorted(direct.get(key, [])),
            "through": sorted(through.get(key, [])),
            "limits": sorted(machine_tokens.LIMIT_NAMES.get(key, ())),
            "tools": tools.get(key, {}),
            "remote": any(server.integration == key for server in SERVERS.values()),
            "used_by": sorted(registry.INTEGRATIONS[key].used_by) if key in registry.INTEGRATIONS else [],
        }
        for key in keys
    ]
    uses = {scope: [k for k in found if k in titles] for scope, found in scopes.SCOPE_USES.items()}
    return {
        "tokens": machine_tokens.list_active(db, org_id),
        "scopes": scopes.SCOPES,
        "integrations": integrations,
        "uses": uses,
    }


def issue_token(db, org_id: int, data: dict, created_by: str | None) -> dict:
    """Issue a machine token from {"name", "kind", "scopes", "expires_days", "limits"}. The value is in the result only.

    Raises machine_tokens.TokenError when the request is refused.
    """
    value, row = machine_tokens.issue(
        db,
        organization_id=org_id,
        name=data.get("name"),
        kind=data.get("kind"),
        scopes=data.get("scopes"),
        created_by=created_by,
        expires_days=data.get("expires_days"),
        limits=data.get("limits"),
    )
    return {"token": value, **machine_tokens.to_dict(row)}


def revoke_token(db, org_id: int, token_id: int) -> bool:
    """Revoke a machine token of the org. False when there is none."""
    return machine_tokens.revoke(db, org_id, token_id)


def issue_child_token(db, caller: machine_tokens.MachineCaller, data: dict) -> dict:
    """Issue a token for the caller's org with a subset of the caller's scopes and the caller's limits.

    The value is in the result only. Raises SettingsError when the request asks for more than the caller has.
    """
    wanted = data.get("scopes")
    if isinstance(wanted, list):
        extra = sorted({str(s) for s in wanted} - set(caller.scopes))
        if extra:
            raise SettingsError(f"The calling token does not have these scopes: {', '.join(extra)}", 403)
    request = {**data, "limits": dict(caller.limits) or None}
    try:
        return issue_token(db, caller.organization_id, request, caller.actor)
    except machine_tokens.TokenError as e:
        raise SettingsError(str(e)) from e


def revoke_tokens(db, org_id: int, token_ids: list[int]) -> dict:
    """Revoke the org's active tokens with these ids. If one id is not active, nothing changes."""
    active = {t["id"] for t in machine_tokens.list_active(db, org_id)}
    missing = sorted(set(token_ids) - active)
    if missing:
        raise SettingsError(f"No active tokens with ids {', '.join(str(i) for i in missing)}", 404)
    for token_id in sorted(set(token_ids)):
        machine_tokens.revoke(db, org_id, token_id)
    return {"revoked": sorted(set(token_ids))}


def delete_secrets(db, org_id: int, names: list[str]) -> dict:
    """Delete org secrets by name. Returns the names deleted and the names that were not set."""
    deleted = [name for name in dict.fromkeys(names) if secrets.delete_secret(db, org_id, name)]
    return {"deleted": deleted, "not_set": [name for name in dict.fromkeys(names) if name not in deleted]}
