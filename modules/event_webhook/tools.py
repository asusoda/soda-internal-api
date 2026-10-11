"""Event webhook tools: list, add, change, test and delete the org's outbound webhooks."""

from core.tools import ToolError, tool
from core.webhooks import Webhook
from modules.auth import scopes

from . import service

scopes.declare(
    "webhooks:manage", "List, add, change, test and delete the org's outbound webhooks. URLs are never returned"
)

WEBHOOK_ID = {"type": "integer", "minimum": 1}


@tool(
    "webhooks.list",
    description="The org's webhooks, the events and kinds to pick from, and the feeds of the webhook modules. URLs are never returned.",
    scope="webhooks:manage",
    module="event_webhook",
)
def webhooks_list(db, org, caller):
    return service.listing(db, org)


@tool(
    "webhooks.save",
    description=(
        "Add a webhook, or change the webhook with id. A new webhook needs name, events and url. The URL must "
        "match the kind and is stored encrypted. A missing field is kept."
    ),
    scope="webhooks:manage",
    module="event_webhook",
    input_schema={
        "type": "object",
        "properties": {
            "id": WEBHOOK_ID,
            "name": {"type": "string", "minLength": 1, "maxLength": service.MAX_NAME},
            "kind": {"type": "string", "maxLength": 32},
            "url": {"type": "string", "maxLength": 1000},
            "events": {"type": "array", "items": {"type": "string", "maxLength": 64}, "minItems": 1},
            "enabled": {"type": "boolean"},
        },
        "minProperties": 1,
        "additionalProperties": False,
    },
)
def webhooks_save(db, org, caller, id: int | None = None, **body):
    if id is None:
        return {"webhook": service.create(db, org, body, caller.actor)}
    return {"webhook": service.update(db, org, id, body)}


@tool(
    "webhooks.test",
    description="Send a test message to a webhook now and return whether it worked.",
    scope="webhooks:manage",
    module="event_webhook",
    input_schema={
        "type": "object",
        "properties": {"id": WEBHOOK_ID},
        "required": ["id"],
        "additionalProperties": False,
    },
)
def webhooks_test(db, org, caller, id: int):
    return service.send_test(db, org, id)


@tool(
    "webhooks.delete",
    description="Delete webhooks by id, up to 20. If one id is missing, nothing changes.",
    scope="webhooks:manage",
    module="event_webhook",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {"ids": {"type": "array", "items": WEBHOOK_ID, "minItems": 1, "maxItems": service.MAX_IDS}},
        "required": ["ids"],
        "additionalProperties": False,
    },
)
def webhooks_delete(db, org, caller, ids: list[int]):
    known = {row.id for row in db.query(Webhook.id).filter(Webhook.organization_id == org.id, Webhook.id.in_(ids))}
    missing = sorted(set(ids) - known)
    if missing:
        raise ToolError(f"No webhooks with ids {', '.join(str(i) for i in missing)}", 404)
    for webhook_id in sorted(known):
        service.delete(db, org, webhook_id)
    return {"deleted": sorted(known)}
