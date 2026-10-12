"""Lists and runs tools for a machine token. Shared by the MCP server and /api/tools. No Flask here.

The tools are the modules' tools in core.tools.TOOLS and the tools of connected services that
modules/integrations passes through to their MCP servers. The batch tool runs up to MAX_BATCH of those
calls in one request; each call gets its own scope check, confirm step and audit entry.

Each call of a tool, also inside a batch, counts against the org's mcp.calls_per_minute limit.
"""

import time
from typing import Any

import jsonschema

from core import audit, limits
from core.cache import cache
from core.errors import ServiceError
from core.log import get_logger
from core.tools import TOOLS, ToolError, ToolSpec
from modules.auth.machine_tokens import MachineCaller
from modules.integrations import service as remote
from modules.organizations import service as organizations
from modules.organizations.models import Organization

logger = get_logger("tools")

CALLS_LIMIT = "mcp.calls_per_minute"
limits.declare(CALLS_LIMIT, "mcp", "Tool calls a minute (MCP and /api/tools)", 300, window="minute", unit="calls")

BATCH = "batch"
MAX_BATCH = 25
BATCH_SPEC = ToolSpec(
    name=BATCH,
    description=(
        f"Run 1 to {MAX_BATCH} tool calls in order and get one result for each. Each call has the same scope "
        "check, confirm step and audit entry as a single call. A confirm tool without confirm=true in its "
        "arguments returns its preview. stop_on_error stops at the first call that fails. A batch cannot hold a batch."
    ),
    scope="",
    func=lambda *args, **kwargs: None,
    input_schema={
        "type": "object",
        "properties": {
            "calls": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_BATCH,
                "items": {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string", "minLength": 1, "maxLength": 200},
                        "arguments": {"type": "object"},
                    },
                    "required": ["tool"],
                    "additionalProperties": False,
                },
            },
            "stop_on_error": {"type": "boolean"},
        },
        "required": ["calls"],
        "additionalProperties": False,
    },
)


def _org(db, caller: MachineCaller) -> Organization:
    org = db.query(Organization).filter_by(id=caller.organization_id, is_active=True).first()
    if org is None:
        raise ToolError("The token's organization is inactive or gone", 403)
    return org


def _usable(db, spec: ToolSpec, org: Organization, caller: MachineCaller, *, any_scope: bool = False) -> bool:
    """Whether the caller may call the tool. any_scope skips the scope check, for step-up."""
    if not any_scope and not caller.allows(spec.scope):
        return False
    if spec.module is not None and not organizations.module_enabled(org, spec.module):
        return False
    return spec.available is None or spec.available(db, caller.organization_id)


def available(db, caller: MachineCaller, *, step_up: bool = False) -> list[ToolSpec]:
    """Tools this token may call: its scopes allow them, its org has their module on and their service connected.

    With step_up, also the module tools that need a scope the token does not have, so that an OAuth client
    can call one, get 403 insufficient_scope and ask the officer for the scope (see edges.py).
    """
    org = _org(db, caller)
    local = [spec for spec in TOOLS.values() if _usable(db, spec, org, caller, any_scope=step_up)]
    found = local + _remote(db, org, caller)
    return sorted(found + [BATCH_SPEC] if found else found, key=lambda s: s.name)


def missing_scope(db, caller: MachineCaller, name: str) -> str | None:
    """The scope that a module tool needs and the caller does not have, or None.

    None also when the tool does not exist or its org cannot use it: those calls get 404 from call().
    """
    spec = TOOLS.get(name)
    if spec is None or caller.allows(spec.scope):
        return None
    org = db.query(Organization).filter_by(id=caller.organization_id, is_active=True).first()
    if org is None or not _usable(db, spec, org, caller, any_scope=True):
        return None
    return spec.scope


def _remote(db, org: Organization, caller: MachineCaller) -> list[ToolSpec]:
    """The tools of the org's connected MCP servers, when the integrations module is on."""
    if not organizations.module_enabled(org, "integrations"):
        return []
    return remote.tools_for(db, caller.organization_id, caller)


def call(db, caller: MachineCaller, name: str, arguments: dict | None, *, source: str) -> Any:
    """Run one tool. Raises ToolError. Every call, refused or not, is written to the audit log."""
    started = time.monotonic()
    status = 200
    pending = False
    try:
        org = _org(db, caller)
        if name == BATCH:
            return _batch(db, caller, arguments, source)
        limits.consume(db, caller.organization_id, CALLS_LIMIT)
        db.commit()
        spec = TOOLS.get(name)
        if spec is not None and not _usable(db, spec, org, caller):
            spec = None
        if spec is None and name not in TOOLS and organizations.module_enabled(org, "integrations"):
            spec = remote.find(db, caller.organization_id, caller, name)
        if spec is None:
            # Same answer for unknown and not allowed, so a token cannot probe for tools
            raise ToolError(f"No tool named {name}", 404)
        args = dict(arguments or {})
        try:
            jsonschema.validate(args, spec.input_schema)
        except jsonschema.ValidationError as e:
            raise ToolError(f"Invalid arguments: {e.message}", 400) from e
        if name in TOOLS and "additionalProperties" not in spec.input_schema:
            # A module tool takes only the arguments its schema names
            unknown = sorted(set(args) - set(spec.input_schema.get("properties") or {}))
            if unknown:
                raise ToolError(f"Invalid arguments: unknown {', '.join(unknown)}", 400)
        confirmed = args.pop("confirm", False) is True
        if spec.confirm and not confirmed:
            pending = True
            result = _preview(spec, args)
            if spec.preview is not None:
                result["preview"] = spec.preview(db, org, caller, **args)
            return result
        result = spec.func(db, org, caller, **args)
        if not spec.read_only:
            # Drops the cached org reads of this process, as an HTTP write does
            cache.invalidate("org")
        return result
    except ToolError as e:
        status = e.status
        db.rollback()
        raise
    except ServiceError as e:
        status = e.status
        db.rollback()
        raise ToolError(e.message, e.status) from e
    except Exception:
        status = 500
        db.rollback()
        logger.exception("tool failed name=%s", name)
        raise ToolError("Tool failed", 500) from None
    finally:
        audit.record(
            f"tool {name}",
            source=source,
            org=None if status == 403 else _prefix(db, caller),
            actor_kind="machine",
            actor_id=caller.actor,
            status=status,
            details={"ms": round((time.monotonic() - started) * 1000)} | ({"confirm": "pending"} if pending else {}),
        )


def _batch(db, caller: MachineCaller, arguments: dict | None, source: str) -> dict:
    """Run each call of a batch with call() and collect the results. A failed call stops the rest only with stop_on_error."""
    args = dict(arguments or {})
    try:
        jsonschema.validate(args, BATCH_SPEC.input_schema)
    except jsonschema.ValidationError as e:
        raise ToolError(f"Invalid arguments: {e.message}", 400) from e
    results = []
    for item in args["calls"]:
        name = item["tool"]
        try:
            if name == BATCH:
                raise ToolError("A batch cannot hold a batch", 400)
            result = call(db, caller, name, item.get("arguments"), source=source)
            results.append({"tool": name, "ok": True, "result": result, "status": 200})
        except ToolError as e:
            results.append({"tool": name, "ok": False, "error": e.message, "status": e.status})
            if args.get("stop_on_error") is True:
                break
    return {"results": results}


def _preview(spec: ToolSpec, args: dict) -> dict:
    """The answer to a confirm tool called without confirm=true. Nothing has changed."""
    return {
        "confirm_required": True,
        "tool": spec.name,
        "arguments": args,
        "message": f"Nothing changed. To run {spec.name}, call it again with the same arguments and confirm=true.",
    }


def _prefix(db, caller: MachineCaller) -> str | None:
    org = db.query(Organization).filter_by(id=caller.organization_id).first()
    return str(org.prefix) if org else None


def describe(spec: ToolSpec) -> dict:
    return {
        "name": spec.name,
        "description": spec.description,
        "scope": spec.scope,
        "read_only": spec.read_only,
        "confirm": spec.confirm,
        "input_schema": spec.input_schema,
    }
