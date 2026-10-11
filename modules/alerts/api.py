"""HTTP routes for officers to manage the alert destinations of their org, under /api/dashboard/<org_prefix>."""

from functools import partial

from flask import Blueprint

from core.http import audit_hook
from core.http.responses import json_body
from modules.auth import access
from modules.auth.routes import officer_route

from . import service

alerts_blueprint = Blueprint("alerts", __name__)
_route = partial(officer_route, alerts_blueprint)

# A test sends a message and changes no settings
audit_hook.SKIPPED_ROUTES.add("/api/dashboard/<string:org_prefix>/webhooks/<int:webhook_id>/test")


def _actor() -> str:
    principal = access.current_principal()
    return f"officer:{principal.discord_id}" if principal and principal.discord_id else "officer"


@_route("/webhooks", ["GET"])
def list_webhooks(db, org):
    return service.listing(db, org)


@_route("/webhooks", ["POST"])
def create_webhook(db, org):
    return service.create(db, org, json_body(), _actor()), 201


@_route("/webhooks/<int:webhook_id>", ["PUT"])
def update_webhook(db, org, webhook_id):
    return service.update(db, org, webhook_id, json_body())


@_route("/webhooks/<int:webhook_id>", ["DELETE"])
def delete_webhook(db, org, webhook_id):
    service.delete(db, org, webhook_id)
    return {"deleted": True}


@_route("/webhooks/<int:webhook_id>/test", ["POST"])
def test_webhook(db, org, webhook_id):
    return service.send_test(db, org, webhook_id)
