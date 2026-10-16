"""Superadmin logic: guilds without an org, an officer's orgs, guild roles, new orgs, the server's health and
services, and each org's limits. No Flask here."""

import re
from typing import Any

from sqlalchemy import Table, delete, or_, select, update

from core import host, hosting, jobs
from core import limits as core_limits
from core.config import superadmin_ids
from core.db import Base
from core.errors import ServiceError
from core.integrations import server as runner
from core.integrations.discord import DiscordUnavailable
from core.log import get_logger
from core.time import utcnow
from modules.godfather.models import ComputePod
from modules.organizations import service as organizations
from modules.organizations.config import OrganizationSettings
from modules.organizations.models import Organization
from modules.runpod.models import App
from modules.superadmin.models import ServiceOwner

logger = get_logger(__name__)


def is_superadmin(discord_id: object) -> bool:
    """Whether the Discord id is one of the ids in SYS_ADMIN."""
    return str(discord_id) in superadmin_ids()


ORG_HAS_PODS = "The org has apps or pods on a hosting provider. Delete them first, then delete the org"


def _org_filters(table: Table, owned: dict[str, Any], org_id: int) -> list[Any]:
    """The conditions that select the rows of table that belong to the org, directly or through a parent row."""
    filters = []
    for fk in table.foreign_keys:
        parent = fk.column.table
        if parent.name == "organizations":
            if fk.ondelete != "SET NULL":
                filters.append(fk.parent == org_id)
        elif parent.name in owned:
            ids = select(fk.column).where(owned[parent.name])
            filters.append(fk.parent.in_(ids))
    return filters


def delete_organization(db, org_id: int) -> str:
    """Delete the org and every row that belongs to it. Returns the org's name. Commits.

    Rows that refer to the org with ON DELETE SET NULL, such as submodules, stay and lose the org.
    Refuses with 409 while an app of the org has a pod, or the org has a godfather pod.
    """
    org = db.get(Organization, org_id)
    if org is None:
        raise ServiceError("Organization not found", 404)
    pods = db.query(ComputePod.id).filter_by(organization_id=org_id).first()
    apps = db.query(App.id).filter(App.organization_id == org_id, App.pod_id.is_not(None)).first()
    if pods is not None or apps is not None:
        raise ServiceError(ORG_HAS_PODS, 409)
    name = str(org.name)
    tables = Base.metadata.sorted_tables
    owned: dict[str, Any] = {}
    for table in tables:
        filters = _org_filters(table, owned, org_id)
        if filters:
            owned[table.name] = or_(*filters)
    for table in reversed(tables):
        for fk in table.foreign_keys:
            if fk.column.table.name == "organizations" and fk.ondelete == "SET NULL":
                db.execute(update(table).where(fk.parent == org_id).values({fk.parent.name: None}))
        if table.name in owned:
            db.execute(delete(table).where(owned[table.name]))
    db.expunge(org)
    db.execute(delete(Organization.__table__).where(Organization.__table__.c.id == org_id))
    db.commit()
    logger.info("org deleted id=%s name=%s", org_id, name)
    return name


def available_guilds(guilds: list[dict], orgs: list[Organization]) -> list[dict]:
    """The bot's guilds that have no org yet."""
    taken = {org.guild_id for org in orgs}
    return [
        {"id": guild["id"], "name": guild["name"], "icon": {"url": guild["icon_url"]}}
        for guild in guilds
        if guild["id"] not in taken
    ]


def officer_orgs(directory, orgs: list[Organization], officer_id: object) -> list[Organization]:
    """The orgs whose guild has the member. An org whose guild cannot be read is left out."""
    if not officer_id:
        return []
    found = []
    for org in orgs:
        try:
            if directory.check_user_membership(officer_id, org.guild_id):
                found.append(org)
        except (ValueError, DiscordUnavailable) as e:
            logger.debug(f"Error checking organization {org.name}: {e}")
    return found


def guild_roles(directory, guild_id: int) -> list[dict]:
    """The guild's roles without @everyone and integration roles, highest position first."""
    roles = [
        {key: role[key] for key in ("id", "name", "color", "position", "permissions")}
        for role in directory.get_guild_roles(guild_id)
        if role["name"] != "@everyone" and not role["managed"]
    ]
    roles.sort(key=lambda x: x["position"], reverse=True)
    return roles


def role_in_guild(directory, guild_id: Any, role_id: Any) -> bool:
    """Whether the guild has the role. Raises ValueError when an id is not a number."""
    role_ids = {role["id"] for role in directory.get_guild_roles(int(guild_id))}
    return str(int(role_id)) in role_ids


def prefix_for(name: str, guild_id: object) -> str:
    """A prefix from a guild name: lowercase letters, digits and underscores, 2 to 20 characters."""
    prefix = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:20].rstrip("_")
    return prefix if len(prefix) >= 2 else f"org_{str(guild_id)[-6:]}"


def new_organization(guild: dict) -> Organization:
    """An unsaved org for a guild, with a prefix from the guild name, default settings and new-org module switches."""
    return Organization(
        name=guild["name"],
        guild_id=guild["id"],
        prefix=prefix_for(guild["name"], guild["id"]),
        description=f"Discord server: {guild['name']}",
        icon_url=guild["icon_url"],
        config={**OrganizationSettings().to_dict(), "modules": organizations.new_org_switches()},
    )


# A limit is near when the org uses this share of it or more
NEAR = 0.8


def server(db, bot_ready: bool | None) -> dict:
    """The server's health, whether the Discord bot answers, and the job queue."""
    return host.stats(db) | {
        "bot_ready": bot_ready,
        "jobs": {"backend": jobs.queue_backend(), "queue": jobs.queue_counts(db)},
    }


def _near(row: dict) -> bool:
    return row["value"] is not None and row["enabled"] and row["used"] >= NEAR * max(row["value"], 1)


def org_limits(db, org: Organization) -> dict:
    """The org, its limits with what it uses, and its overrides."""
    rows = organizations.limits(db, org)
    return {
        "org": {"id": org.id, "name": org.name, "prefix": org.prefix, "is_active": org.is_active},
        "limits": rows,
        "near": sorted(row["key"] for row in rows if _near(row)),
        "overrides": core_limits.overrides_of(db, org.id),
    }


def all_limits(db) -> dict:
    """Every declared limit, and each org's limits and use."""
    orgs = db.query(Organization).order_by(Organization.name).all()
    return {
        "catalog": core_limits.catalog(),
        "near": NEAR,
        "orgs": [org_limits(db, org) for org in orgs],
    }


def set_org_limits(db, org: Organization, changes: object, actor: str | None) -> dict:
    """Set the org's overrides. Commits."""
    core_limits.set_values(db, org.id, changes, actor=actor)
    return org_limits(db, org)


OWNERS = ("platform", "infrastructure", "org")
MAX_SERVICE_NAME = 128


class ServerError(ServiceError):
    """A bad request about the server's services."""


def _owner_of(service: dict, row: ServiceOwner | None, orgs: dict) -> dict:
    """The owner the superadmin set; else the org of a platform.org label; else Platform for Platform's own
    containers."""
    if row is not None:
        org = orgs["id"].get(row.organization_id)
        return {"owner": row.owner, "org": org, "set": True}
    if service.get("org") and service["org"] in orgs["prefix"]:
        return {"owner": "org", "org": orgs["prefix"][service["org"]], "set": False}
    if service.get("platform"):
        return {"owner": "platform", "org": None, "set": False}
    return {"owner": None, "org": None, "set": False}


def server_services(db) -> dict:
    """Each container and host process on the server, from the host agent, with its owner."""
    snapshot = host.agent_snapshot()
    if snapshot is None:
        return {"agent": None, "services": []}
    rows = {row.name: row for row in db.query(ServiceOwner).all()}
    orgs: dict[str, dict] = {"id": {}, "prefix": {}}
    for org in db.query(Organization).all():
        brief = {"id": org.id, "name": org.name, "prefix": org.prefix}
        orgs["id"][org.id] = brief
        orgs["prefix"][org.prefix] = brief
    services = [
        {
            key: s.get(key)
            for key in (
                "name",
                "kind",
                "state",
                "status",
                "image",
                "project",
                "memory_used",
                "memory_limit",
                "cpu_percent",
                "ports",
                "domains",
            )
        }
        | _owner_of(s, rows.get(s.get("name")), orgs)
        for s in snapshot["services"]
        if isinstance(s, dict) and s.get("name")
    ]
    return {"agent": {"age_seconds": snapshot["age_seconds"], "stale": snapshot["stale"]}, "services": services}


def set_service_owner(db, name: str, body: Any, actor: str | None) -> dict:
    """Set the owner of a service: {"owner": "platform" | "infrastructure" | "org" | null, "organization_id": id}.
    null goes back to the owner from the labels. Commits."""
    if not name or len(name) > MAX_SERVICE_NAME:
        raise ServerError(f"The service name must have 1 to {MAX_SERVICE_NAME} characters")
    if not isinstance(body, dict) or "owner" not in body:
        raise ServerError('Send "owner": platform, infrastructure, org or null')
    owner, org_id = body.get("owner"), body.get("organization_id")
    row = db.query(ServiceOwner).filter_by(name=name).first()
    if owner is None:
        if row is not None:
            db.delete(row)
            db.commit()
        logger.info("service owner cleared name=%s actor=%s", name, actor)
        return {"name": name, "owner": None}
    if owner not in OWNERS:
        raise ServerError(f"owner must be one of {', '.join(OWNERS)}, or null")
    if owner == "org":
        if not isinstance(org_id, int) or isinstance(org_id, bool) or db.get(Organization, org_id) is None:
            raise ServerError("organization_id must be the id of an org")
    else:
        org_id = None
    if row is None:
        row = ServiceOwner(name=name)
        db.add(row)
    row.owner, row.organization_id, row.updated_at, row.updated_by = owner, org_id, utcnow(), actor
    db.commit()
    logger.info("service owner set name=%s owner=%s org=%s actor=%s", name, owner, org_id, actor)
    return {"name": name, "owner": owner, "organization_id": org_id}


SERVICE_ACTIONS = ("start", "stop", "restart")


def _target(name: str) -> tuple[str, str | None, str]:
    """How to control a service of the host agent's list: ("app", org or None, container), ("containers", None,
    name) or ("units", None, unit). Raises ServerError when the service cannot be controlled."""
    snapshot = host.agent_snapshot()
    found = next((s for s in (snapshot or {}).get("services", []) if s.get("name") == name), None)
    if found is None:
        raise ServerError("No service with this name on the server", 404)
    if found.get("kind") == "container":
        if name.startswith(("app-", "shared-")):
            for app in runner.call("GET", "/apps")["apps"]:
                if app.get("id") == name:
                    return "app", (None if app.get("shared") else str(app["org"])), name
        return "containers", None, name
    if str(found.get("status") or "").startswith("systemd "):
        return "units", None, name
    raise ServerError("This process is not in a systemd unit, so it cannot be controlled", 409)


def service_action(db, name: str, action: object, actor: str | None) -> dict:
    """Start, stop or restart a service: an app container through its app, another container or unit through the
    runner's host_control list."""
    if action not in SERVICE_ACTIONS:
        raise ServerError(f"action must be one of {', '.join(SERVICE_ACTIONS)}")
    try:
        kind, org, target = _target(name)
        if kind == "app":
            client = runner.ServerClient(org)
            {"start": client.start_pod, "stop": client.stop_pod, "restart": client.restart_pod}[str(action)](target)
            result = {"name": name, "state": str((client.get_pod(target) or {}).get("state"))}
        else:
            result = runner.host_action(kind, target, str(action))
    except hosting.HostingError as e:
        raise ServerError(e.message, e.status or 502) from e
    logger.info("service %s name=%s actor=%s", action, name, actor)
    return result


def service_logs(db, name: str, lines: int = 200) -> dict:
    """The last lines of a service's output."""
    try:
        kind, org, target = _target(name)
        if kind == "app":
            return {"logs": runner.ServerClient(org).logs(target, lines)}
        return {"logs": runner.host_logs(kind, target, lines)}
    except hosting.HostingError as e:
        raise ServerError(e.message, e.status or 502) from e
