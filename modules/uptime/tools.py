"""Uptime tools."""

from core.tools import tool

from . import service


@tool(
    "uptime.list",
    description=(
        "The org's uptime monitors: target, state (up, down or null before the first check), "
        "percent up over 24 hours and 7 days, and the last check with its status code, latency and error."
    ),
    scope="uptime:read",
    module="uptime",
)
def uptime_list(db, org, caller):
    monitors = service.list_monitors(db, int(org.id))
    return {"monitors": [{k: v for k, v in m.items() if k != "recent"} for m in monitors]}


ID = {"type": "integer", "minimum": 1}
FIELDS = {
    "name": {"type": "string", "minLength": 1, "maxLength": service.MAX_NAME},
    "target_kind": {"type": "string", "enum": list(service.KINDS)},
    "target": {"type": "string", "minLength": 1, "maxLength": service.MAX_URL},
    "expected_status": {"type": "string", "pattern": service.STATUS_PATTERN.pattern},
    "timeout_seconds": {"type": "integer", "minimum": service.TIMEOUT_RANGE[0], "maximum": service.TIMEOUT_RANGE[1]},
    "interval_minutes": {
        "type": "integer",
        "minimum": service.INTERVAL_RANGE[0],
        "maximum": service.INTERVAL_RANGE[1],
    },
    "enabled": {"type": "boolean"},
}


@tool(
    "uptime.get",
    description="One monitor with its recent checks, newest first.",
    scope="uptime:read",
    module="uptime",
    input_schema={"type": "object", "properties": {"id": ID}, "required": ["id"], "additionalProperties": False},
)
def uptime_get(db, org, caller, id: int):
    return {"monitor": service.get_monitor(db, int(org.id), id)}


@tool(
    "uptime.targets",
    description="The Hosting apps that a monitor with target_kind app can check, and the address it reads.",
    scope="uptime:read",
    module="uptime",
)
def uptime_targets(db, org, caller):
    return {"apps": service.targets(db, int(org.id))}


@tool(
    "uptime.save",
    description=(
        "Add a monitor, or change the monitor with id. target is a public https URL, or an app name when "
        "target_kind is app. expected_status is a class such as 2xx or a code such as 204. A missing field is kept."
    ),
    scope="uptime:manage",
    module="uptime",
    input_schema={
        "type": "object",
        "properties": {"id": ID, **FIELDS},
        "minProperties": 1,
        "additionalProperties": False,
    },
)
def uptime_save(db, org, caller, id: int | None = None, **body):
    if id is None:
        return {"monitor": service.create_monitor(db, int(org.id), body)}
    return {"monitor": service.update_monitor(db, int(org.id), id, body)}


@tool(
    "uptime.delete",
    description="Delete monitors and their checks by id, up to 50. If one id is missing, nothing changes.",
    scope="uptime:manage",
    module="uptime",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {"ids": {"type": "array", "items": ID, "minItems": 1, "maxItems": service.MAX_IDS}},
        "required": ["ids"],
        "additionalProperties": False,
    },
)
def uptime_delete(db, org, caller, ids: list[int]):
    return service.delete_monitors(db, int(org.id), ids)


@tool(
    "uptime.check",
    description="Check a monitor now, on or off, and wait for the result. Returns the check and the monitor.",
    scope="uptime:manage",
    module="uptime",
    input_schema={"type": "object", "properties": {"id": ID}, "required": ["id"], "additionalProperties": False},
)
def uptime_check(db, org, caller, id: int):
    return service.check_now(db, int(org.id), id)
