"""HTTP routes for apps on RunPod. Machine tokens only; the organization is the token's."""

from functools import partial
from typing import cast

from flask import Blueprint, g

from core.http.responses import json_body
from modules.auth.routes import machine_route

from . import service, templates

apps_blueprint = Blueprint("apps", __name__)
_route = partial(machine_route, apps_blueprint, module="runpod")


def _actor() -> str:
    caller = g.machine_caller
    return f"{caller.kind}:{caller.name}#{caller.token_id}"


def _org_id(org) -> int:
    return cast(int, org.id)


@_route("", "apps:read", ["GET"])
def list_apps(db, org):
    return {"apps": service.list_apps(db, _org_id(org))}


@_route("/templates", "apps:read", ["GET"])
def list_templates(db, org):
    return {"templates": templates.list_templates()}


@_route("/templates/<string:template>", "apps:manage", ["POST"])
def create_from_template(db, org, template):
    data = json_body()
    app = templates.create(
        db,
        _org_id(org),
        template,
        data.get("name"),
        data.get("values"),
        data.get("secrets"),
        data.get("provider"),
        _actor(),
    )
    return app, 201


@_route("/<string:name>", "apps:read", ["GET"])
def get_app(db, org, name):
    return service.get_app(db, _org_id(org), name)


@_route("/<string:name>", "apps:manage", ["PUT"])
def put_app(db, org, name):
    data = json_body()
    return service.put_app(
        db, _org_id(org), name, data.get("manifest"), data.get("repo"), data.get("manifest_path"), data.get("provider")
    )


@_route("/<string:name>", "apps:manage", ["DELETE"])
def delete_app(db, org, name):
    return service.delete_app(db, _org_id(org), name)


@_route("/<string:name>/deployments", "apps:read", ["GET"])
def list_deployments(db, org, name):
    return {"deployments": service.deployments(db, _org_id(org), name)}


@_route("/<string:name>/pod", "apps:read", ["GET"])
def get_pod(db, org, name):
    return {"pod": service.pod(db, _org_id(org), name)}


@_route("/<string:name>/deploy", "apps:deploy", ["POST"])
def deploy(db, org, name):
    data = json_body()
    result = service.deploy(
        db,
        _org_id(org),
        str(org.prefix),
        name,
        data.get("tag"),
        _actor(),
        dry_run=data.get("dry_run") is True,
        ref=data.get("ref"),
    )
    return result, 200 if result.get("dry_run") else 202


@_route("/<string:name>/rollback", "apps:manage", ["POST"])
def rollback(db, org, name):
    result = service.rollback(
        db, _org_id(org), str(org.prefix), name, _actor(), dry_run=json_body().get("dry_run") is True
    )
    return result, 200 if result.get("dry_run") else 202
