"""Feed tools: list, create, run and delete the org's feeds."""

from core.tools import tool

from . import service

KEY = {"type": "string", "minLength": 1, "maxLength": 40}
ONLY_KEY = {"type": "object", "properties": {"key": KEY}, "required": ["key"], "additionalProperties": False}


@tool(
    "feeds.list",
    description="The org's feeds, their schedule, destination and last run.",
    scope="feeds:manage",
)
def feeds_list(db, org, caller):
    return {"feeds": service.list_feeds(db, int(org.id))}


@tool(
    "feeds.presets",
    description="Feeds that shared content (submodules) offers, with the kind and config to pass to feeds.save.",
    scope="feeds:manage",
)
def feeds_presets(db, org, caller):
    return {"presets": service.presets(db, int(org.id))}


@tool(
    "feeds.history",
    description="A feed's recent runs and the items it posted.",
    scope="feeds:manage",
    input_schema=ONLY_KEY,
)
def feeds_history(db, org, caller, key: str):
    return service.history(db, int(org.id), key)


@tool(
    "feeds.save",
    description=(
        "Create or change a feed. kind is github_jobs or hackathons. A new feed needs destination_id, the id of a "
        "Discord destination from webhooks.list. webhook_url is the older way and is stored as a secret."
    ),
    scope="feeds:manage",
    input_schema={
        "type": "object",
        "properties": {
            "key": KEY,
            "kind": {"type": "string", "enum": sorted(service.KINDS)},
            "config": {"type": "object"},
            "every_hours": {"type": "integer", "minimum": 1, "maximum": 168},
            "enabled": {"type": "boolean"},
            "destination_id": {"type": "integer", "minimum": 1},
            "webhook_url": {"type": "string", "maxLength": 300},
        },
        "required": ["key"],
        "additionalProperties": False,
    },
)
def feeds_save(db, org, caller, key: str, **body):
    feed, created = service.put_feed(db, int(org.id), key, body, caller.actor)
    return {"feed": feed, "created": created}


@tool(
    "feeds.delete",
    description="Delete a feed, its history and its webhook.",
    scope="feeds:manage",
    confirm=True,
    input_schema=ONLY_KEY,
)
def feeds_delete(db, org, caller, key: str):
    service.delete_feed(db, int(org.id), key)
    return {"deleted": key}


@tool(
    "feeds.run",
    description="Run a feed now and post its new items. post_existing also posts items seen before the first run.",
    scope="feeds:manage",
    input_schema={
        "type": "object",
        "properties": {"key": KEY, "post_existing": {"type": "boolean"}},
        "required": ["key"],
        "additionalProperties": False,
    },
)
def feeds_run(db, org, caller, key: str, post_existing: bool = False):
    return service.run_now(db, int(org.id), key, post_existing=post_existing)
