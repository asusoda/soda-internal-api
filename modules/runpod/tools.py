"""App tools. Apps run on a hosting provider: RunPod or This server. Shared apps are the deployment's, so their
tools work with the runpod module off."""

from functools import partial

from core import hosting
from core.tools import tool as _tool
from modules.runpod import service, shared, templates

# Every tool here needs the runpod module on for the caller's org
tool = partial(_tool, module="runpod")


@tool(
    "apps.list",
    description="Apps the organization runs: provider, image tag, pod id and the latest deployment's status.",
    scope="apps:read",
)
def apps_list(db, org, caller):
    apps = service.list_apps(db, int(org.id))
    return {"apps": [{k: v for k, v in app.items() if k != "manifest"} for app in apps]}


NAME = {"type": "string", "minLength": 1, "maxLength": 64}


@tool(
    "apps.get",
    description="One app: its manifest, pod, tag and recent deployments.",
    scope="apps:read",
    input_schema={"type": "object", "properties": {"name": NAME}, "required": ["name"], "additionalProperties": False},
)
def apps_get(db, org, caller, name: str):
    return service.get_app(db, int(org.id), name) | {"deployments": service.deployments(db, int(org.id), name)}


@tool(
    "apps.register",
    description="Create an app or replace its manifest. Send a manifest object, or a repo whose manifest file is read. "
    "provider runpod (default) takes gpu or cpu; provider server (This server) takes memory in MB, and optionally "
    "publish, volumes, command, workdir, and group with alias for the parts of one app. health is a path, or "
    "{port, tcp: true} for a database, or {running: true} for a part with no port.",
    scope="apps:manage",
    input_schema={
        "type": "object",
        "properties": {
            "name": NAME,
            "manifest": {"type": "object"},
            "repo": {"type": "string", "maxLength": 200},
            "manifest_path": {"type": "string", "maxLength": 200},
            "provider": {"type": "string", "maxLength": 32},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
)
def apps_register(db, org, caller, name: str, manifest=None, repo=None, manifest_path=None, provider=None):
    return service.put_app(db, int(org.id), name, manifest, repo, manifest_path, provider)


@tool(
    "apps.delete",
    description="Forget an app. On This server its container goes too; a RunPod pod keeps running until it is "
    "terminated on RunPod.",
    scope="apps:manage",
    confirm=True,
    input_schema={"type": "object", "properties": {"name": NAME}, "required": ["name"], "additionalProperties": False},
)
def apps_delete(db, org, caller, name: str):
    return service.delete_app(db, int(org.id), name)


def _deploy_preview(db, org, caller, name: str, tag: str, ref: str | None = None):
    return service.deploy(db, int(org.id), str(org.prefix), name, tag, caller.actor, dry_run=True, ref=ref)


def _rollback_preview(db, org, caller, name: str):
    return service.rollback(db, int(org.id), str(org.prefix), name, caller.actor, dry_run=True)


@tool(
    "apps.deploy",
    description="Deploy an image tag of an app. The health check rolls a failed deploy back.",
    scope="apps:deploy",
    confirm=True,
    preview=_deploy_preview,
    input_schema={
        "type": "object",
        "properties": {
            "name": NAME,
            "tag": {"type": "string", "minLength": 1, "maxLength": 128},
            "ref": {"type": "string", "maxLength": 200},
        },
        "required": ["name", "tag"],
        "additionalProperties": False,
    },
)
def apps_deploy(db, org, caller, name: str, tag: str, ref: str | None = None):
    return service.deploy(db, int(org.id), str(org.prefix), name, tag, caller.actor, ref=ref)


@tool(
    "apps.rollback",
    description="Deploy the newest healthy tag other than the current one.",
    scope="apps:manage",
    confirm=True,
    preview=_rollback_preview,
    input_schema={"type": "object", "properties": {"name": NAME}, "required": ["name"], "additionalProperties": False},
)
def apps_rollback(db, org, caller, name: str):
    return service.rollback(db, int(org.id), str(org.prefix), name, caller.actor)


@tool(
    "apps.pod",
    description="The live pod of an app on its provider: status, address and hardware.",
    scope="apps:read",
    input_schema={"type": "object", "properties": {"name": NAME}, "required": ["name"], "additionalProperties": False},
)
def apps_pod(db, org, caller, name: str):
    return {"pod": service.pod(db, int(org.id), name)}


@tool(
    "apps.templates",
    description="App templates to create an app from, with the inputs each one asks for.",
    scope="apps:read",
)
def apps_templates(db, org, caller):
    return {"templates": templates.list_templates()}


@tool(
    "hosting.providers",
    description="The hosting providers that apps and pods run on, and whether the org set each one up.",
    scope="apps:read",
)
def hosting_providers(db, org, caller):
    return {"providers": hosting.listing(db, int(org.id))}


@tool(
    "apps.create_from_template",
    description=(
        "Register a new app from a template. values maps the template's input keys to text. secrets maps its "
        "secret keys to values; they are saved as org secrets and never returned. Deploy it with apps.deploy."
    ),
    scope="apps:manage",
    input_schema={
        "type": "object",
        "properties": {
            "template": {"type": "string", "minLength": 1, "maxLength": 64},
            "name": NAME,
            "values": {"type": "object", "additionalProperties": {"type": "string", "maxLength": 2000}},
            "secrets": {"type": "object", "additionalProperties": {"type": "string", "maxLength": 20000}},
            "provider": {"type": "string", "maxLength": 32},
        },
        "required": ["template", "name"],
        "additionalProperties": False,
    },
)
def apps_create_from_template(db, org, caller, template: str, name: str, values=None, secrets=None, provider=None):
    return templates.create(db, int(org.id), template, name, values, secrets, provider, caller.actor)


@tool(
    "apps.action",
    description="Start, stop or restart a deployed app.",
    scope="apps:manage",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {"name": NAME, "action": {"enum": list(service.ACTIONS)}},
        "required": ["name", "action"],
        "additionalProperties": False,
    },
)
def apps_action(db, org, caller, name: str, action: str):
    return service.app_action(db, int(org.id), name, action)


@tool(
    "apps.logs",
    description="The last lines of a This server app's output.",
    scope="apps:read",
    input_schema={
        "type": "object",
        "properties": {"name": NAME, "lines": {"type": "integer", "minimum": 1, "maximum": service.MAX_LOG_LINES}},
        "required": ["name"],
        "additionalProperties": False,
    },
)
def apps_logs(db, org, caller, name: str, lines: int = 200):
    return service.app_logs(db, int(org.id), name, lines)


@_tool(
    "shared_apps.list",
    description="The shared apps the deployment runs for every org, such as the vault: what each is, whether the org "
    "subscribes, and whom it invited.",
    scope="submodules:read",
)
def shared_apps_list(db, org, caller):
    return {"apps": shared.for_org(db, int(org.id))}


@_tool(
    "shared_apps.subscribe",
    description="Subscribe the org to a shared app and invite people by email. For the vault, each person gets an "
    "invite and sets their own master password.",
    scope="submodules:manage",
    confirm=True,
    input_schema={
        "type": "object",
        "properties": {
            "name": NAME,
            "emails": {"type": "array", "items": {"type": "string", "maxLength": 254}, "maxItems": shared.MAX_EMAILS},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
)
def shared_apps_subscribe(db, org, caller, name: str, emails=None):
    return shared.subscribe(db, int(org.id), name, emails, caller.actor)
