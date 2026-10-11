"""Organization tools."""

from core import secrets
from core.tools import ToolError, tool
from modules.auth import machine_tokens, scopes
from modules.organizations import service


@tool(
    "org.info", description="The organization's name, prefix, description and which modules are on.", scope="org:read"
)
def org_info(db, org, caller):
    return {
        "name": org.name,
        "prefix": org.prefix,
        "description": org.description,
        "modules": {m["name"]: m["enabled"] for m in service.module_states(org)},
    }


@tool(
    "org.set_modules",
    description='Turn optional modules on or off, for example {"points": false}.',
    scope="settings:write",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {"modules": {"type": "object", "additionalProperties": {"type": "boolean"}, "minProperties": 1}},
        "required": ["modules"],
        "additionalProperties": False,
    },
)
def org_set_modules(db, org, caller, modules: dict):
    try:
        return {"modules": service.set_modules(db, org, modules)}
    except service.ModuleError as e:
        raise ToolError(str(e), 400) from e


@tool(
    "org.limits",
    description=(
        "The org's resource limits and what it uses now: counts such as knowledge sources or pods, and rates such as "
        "texts embedded a day. value null means no limit. Only the deployment's superadmin changes limits."
    ),
    scope="org:read",
)
def org_limits(db, org, caller):
    return {"limits": [row for row in service.limits(db, org) if row["enabled"]]}


@tool("org.branding", description="The org's logo, accent color and website.", scope="org:read")
def org_branding(db, org, caller):
    return service.branding(org)


@tool(
    "org.set_branding",
    description="Change the org's branding. Send only the fields to change; null clears a field.",
    scope="settings:write",
    input_schema={
        "type": "object",
        "properties": {
            "logo_url": {"type": ["string", "null"], "maxLength": 500},
            "accent_color": {"type": ["string", "null"], "maxLength": 7},
            "website_url": {"type": ["string", "null"], "maxLength": 500},
        },
        "minProperties": 1,
        "additionalProperties": False,
    },
)
def org_set_branding(db, org, caller, **changes):
    return service.set_branding(db, org, changes)


@tool(
    "org.settings",
    description="The org's name, prefix, description, points for each message and the cooldown between them.",
    scope="org:read",
)
def org_settings(db, org, caller):
    return service.settings(org)


@tool(
    "org.update_settings",
    description="Change the description, the points a member gets for a message, or the cooldown in seconds.",
    scope="settings:write",
    input_schema={
        "type": "object",
        "properties": {
            "description": {"type": ["string", "null"], "maxLength": service.MAX_DESCRIPTION},
            "points_per_message": {"type": "integer", "minimum": 0, "maximum": 1000},
            "points_cooldown": {"type": "integer", "minimum": 0, "maximum": 86400},
        },
        "minProperties": 1,
        "additionalProperties": False,
    },
)
def org_update_settings(db, org, caller, **changes):
    return service.set_settings(db, org, changes)


SECRET_NAME = {"type": "string", "minLength": 1, "maxLength": 100}


@tool(
    "secrets.list",
    description="The org's secrets: name, description, whether it is set, and who set it when. Never the values.",
    scope="secrets:manage",
)
def secrets_list(db, org, caller):
    return service.secret_names(db, int(org.id))


@tool(
    "secrets.set",
    description="Save one org secret. It replaces the old value. The value is stored encrypted and never returned.",
    scope="secrets:manage",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {"name": SECRET_NAME, "value": {"type": "string", "minLength": 1, "maxLength": 20000}},
        "required": ["name", "value"],
        "additionalProperties": False,
    },
)
def secrets_set(db, org, caller, name: str, value: str):
    try:
        service.save_secret(db, int(org.id), name, value, caller.actor)
    except secrets.SecretsError as e:
        raise ToolError(str(e), 503 if "SECRETS_KEY" in str(e) else 400) from e
    return {"name": name, "set": True}


@tool(
    "secrets.delete",
    description="Delete org secrets by name, up to 50.",
    scope="secrets:manage",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {"names": {"type": "array", "items": SECRET_NAME, "minItems": 1, "maxItems": 50}},
        "required": ["names"],
        "additionalProperties": False,
    },
)
def secrets_delete(db, org, caller, names: list[str]):
    return service.delete_secrets(db, int(org.id), names)


@tool(
    "tokens.list",
    description="The org's active machine tokens: name, kind, scopes, limits, first characters and dates. Never values.",
    scope="tokens:manage",
)
def tokens_list(db, org, caller):
    return {"tokens": machine_tokens.list_active(db, int(org.id)), "scopes": scopes.SCOPES}


@tool(
    "tokens.create",
    description=(
        "Make a machine token. It gets only scopes that the calling token has, and the calling token's limits. "
        "The result has the token value once; it cannot be read again."
    ),
    scope="tokens:manage",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 100},
            "kind": {"type": "string", "enum": list(machine_tokens.KINDS)},
            "scopes": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 100},
            "expires_days": {"type": "integer", "minimum": 1, "maximum": 3650},
        },
        "required": ["name", "kind", "scopes"],
        "additionalProperties": False,
    },
)
def tokens_create(db, org, caller, **data):
    return service.issue_child_token(db, caller, data)


@tool(
    "tokens.revoke",
    description="Revoke machine tokens by id, up to 100. If one id is not an active token, nothing changes.",
    scope="tokens:manage",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {"ids": {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": 100}},
        "required": ["ids"],
        "additionalProperties": False,
    },
)
def tokens_revoke(db, org, caller, ids: list[int]):
    return service.revoke_tokens(db, int(org.id), ids)
