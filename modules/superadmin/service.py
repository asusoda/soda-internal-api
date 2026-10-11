"""Superadmin logic: guilds without an org, an officer's orgs, guild roles, new orgs, the server's health and each
org's limits. No Flask here."""

import re
from typing import Any, cast

from core import host, jobs
from core import limits as core_limits
from core.config import superadmin_ids
from core.integrations.discord import DiscordUnavailable
from core.log import get_logger
from modules.organizations import service as organizations
from modules.organizations.config import OrganizationSettings
from modules.organizations.models import Organization

logger = get_logger(__name__)


def is_superadmin(discord_id: object) -> bool:
    """Whether the Discord id is one of the ids in SYS_ADMIN."""
    return str(discord_id) in superadmin_ids()


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
        "overrides": core_limits.overrides_of(db, cast(int, org.id)),
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
    core_limits.set_values(db, cast(int, org.id), changes, actor=actor)
    return org_limits(db, org)
