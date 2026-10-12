"""Member tools: list, add and change the org's members, and add the members of its Discord server."""

from core.tools import ToolError, tool
from modules.points import service as points
from modules.users import service

FIELDS = {
    "name": {"type": "string", "maxLength": 255},
    "username": {"type": "string", "maxLength": 255},
    "email": {"type": "string", "maxLength": 255},
    "student_id": {"type": "string", "maxLength": 50},
    "class_standing": {"type": "string", "maxLength": 50},
    "major": {"type": "string", "maxLength": 255},
    "profile_fields": {"type": "object", "additionalProperties": {"type": ["string", "number", "boolean", "null"]}},
}
DISCORD_ID = {"type": "string", "pattern": "^[0-9]{5,25}$"}
ROLES = {"type": "array", "items": {"type": "string", "pattern": "^[0-9]{1,25}$"}, "maxItems": 50}


@tool(
    "members.list",
    description=(
        "The org's active members: name, username, email, student id, class standing, major, profile fields, "
        "Discord id and total points. query keeps members whose name, username or email has that text."
    ),
    scope="members:read",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 100},
            "limit": {"type": "integer", "minimum": 1, "maximum": 5000},
        },
        "additionalProperties": False,
    },
)
def members_list(db, org, caller, query: str | None = None, limit: int = 500):
    totals = points.totals_by_user(db, int(org.id))
    found = []
    text = (query or "").lower()
    for membership, user in service.active_members(db, int(org.id)):
        if text and not any(text in str(value or "").lower() for value in (user.name, user.username, user.email)):
            continue
        found.append(service.member_dict(user, membership) | {"points": totals.get(user.id) or 0})
    return {"total": len(found), "members": found[:limit]}


@tool(
    "members.add",
    description=(
        "Add a member to the org, or make an existing person a member. A person is found by email, student id "
        "or Discord id; a sent field changes theirs."
    ),
    scope="members:write",
    input_schema={
        "type": "object",
        "properties": {**FIELDS, "discord_id": DISCORD_ID},
        "anyOf": [{"required": ["name"]}, {"required": ["username"]}, {"required": ["email"]}],
        "additionalProperties": False,
    },
)
def members_add(db, org, caller, discord_id: str | None = None, **fields):
    user, ok, message = service.manage_user_in_organization(db, int(org.id), fields, discord_id)
    if not ok or user is None:
        raise ToolError(message, 400)
    return {"message": message, "member": service.member_dict(user, service.active_membership(db, user.id, org.id))}


@tool(
    "members.update",
    description=(
        "Change fields of a member, found by email, uuid or username. In profile_fields, null removes a key. "
        "If a field fails, the others are still saved."
    ),
    scope="members:write",
    input_schema={
        "type": "object",
        "properties": {"member": {"type": "string", "minLength": 1, "maxLength": 255}, **FIELDS},
        "required": ["member"],
        "minProperties": 2,
        "additionalProperties": False,
    },
)
def members_update(db, org, caller, member: str, **changes):
    result = service.update_member(db, int(org.id), member, changes)
    if result["errors"]:
        raise ToolError("Some fields failed to update: " + "; ".join(result["errors"]), 400)
    return {
        "updated_fields": result["updated_fields"],
        "member": service.member_dict(result["user"], result["membership"]),
    }


@tool(
    "members.discord_roles",
    description="The roles of the org's Discord server that members.discord_sync can filter by.",
    scope="members:read",
)
def members_discord_roles(db, org, caller):
    return {"roles": service.server_roles(service.bot_directory(), org.guild_id)}


def _sync_preview(db, org, caller, roles: list[str] | None = None):
    return service.sync_from_discord(db, int(org.id), org.guild_id, service.bot_directory(), roles or [], True)


@tool(
    "members.discord_sync",
    description=(
        "Make the members of the org's Discord server members of the org: those with one of roles, or all when "
        "roles is empty. Returns counts: matched, new_users, joined and already."
    ),
    scope="members:write",
    confirm=True,
    preview=_sync_preview,
    input_schema={"type": "object", "properties": {"roles": ROLES}, "additionalProperties": False},
)
def members_discord_sync(db, org, caller, roles: list[str] | None = None):
    return service.sync_from_discord(db, int(org.id), org.guild_id, service.bot_directory(), roles or [], False)
