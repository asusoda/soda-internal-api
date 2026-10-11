"""HTTP routes for submodules and their live queries. Machine tokens only; the organization is the token's.

/api/asu keeps the routes of the old asu module for clients that still call them.
"""

from functools import partial

from flask import Blueprint

from core.http import audit_hook
from core.http.responses import json_body
from modules.auth.routes import machine_route

from . import service

submodules_blueprint = Blueprint("submodules", __name__)
_route = partial(machine_route, submodules_blueprint, module="knowledge")
# Subscriptions belong to the submodule, not to one module, so no module switch gates them
_core_route = partial(machine_route, submodules_blueprint)
asu_blueprint = Blueprint("asu", __name__)
_asu_route = partial(machine_route, asu_blueprint, module="knowledge")

# Live queries are reads sent as POST
audit_hook.SKIPPED_ROUTES.add("/api/submodules/<string:name>/query")
audit_hook.SKIPPED_ROUTES.add("/api/asu/query")


@_route("", "knowledge:read", ["GET"])
def list_submodules(db, org):
    return {"submodules": service.list_submodules(db, int(org.id))}


@_route("/<string:name>/queries", "knowledge:read", ["GET"])
def list_queries(db, org, name):
    return {"queries": service.query_sources(name)}


@_route("/<string:name>/query", "knowledge:read", ["POST"])
def run_query(db, org, name):
    data = json_body()
    return service.query(db, int(org.id), str(org.prefix), name, data.get("source"), data.get("params"))


@_core_route("/<string:name>/subscription", "submodules:manage", ["PUT"])
def subscribe(db, org, name):
    """Subscribe the token's org to the submodule: its pages, feeds and other parts."""
    return service.subscribe(db, int(org.id), name, actor="machine")


@_core_route("/<string:name>/subscription", "submodules:manage", ["DELETE"])
def unsubscribe(db, org, name):
    return service.unsubscribe(db, int(org.id), name)


@_route("/<string:name>/sync", "knowledge:write", ["POST"])
def sync_submodule(db, org, name):
    """Older name of PUT /<name>/subscription."""
    return service.sync(db, int(org.id), str(org.prefix), name)


@_asu_route("/queries", "knowledge:read", ["GET"])
def asu_queries(db, org):
    return {"queries": service.query_sources("asu")}


@_asu_route("/query", "knowledge:read", ["POST"])
def asu_query(db, org):
    data = json_body()
    return service.query(db, int(org.id), str(org.prefix), "asu", data.get("source"), data.get("params"))


@_asu_route("/sync", "knowledge:write", ["POST"])
def asu_sync(db, org):
    return service.sync(db, int(org.id), str(org.prefix), "asu")
