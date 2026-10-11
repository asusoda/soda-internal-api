"""HTTP routes for officers to manage the feeds of their org."""

from functools import partial

from flask import Blueprint

from core.http.responses import json_body
from core.jobs import defer
from modules.auth.routes import officer_route

from . import service

feeds_blueprint = Blueprint("feeds", __name__)
_route = partial(officer_route, feeds_blueprint)


@_route("/feeds", ["GET"])
def list_feeds(db, org):
    return {"feeds": service.list_feeds(db, int(org.id))}


@_route("/presets", ["GET"])
def list_presets(db, org):
    """Feeds that submodules offer. Create one with PUT /feeds/<key> and its kind and config."""
    return {"presets": service.presets(db, int(org.id))}


@_route("/feeds/<string:key>", ["GET"])
def get_feed(db, org, key):
    return {"feed": service.get_feed(db, int(org.id), key)}


@_route("/feeds/<string:key>/history", ["GET"])
def feed_history(db, org, key):
    return service.history(db, int(org.id), key)


@_route("/feeds/<string:key>", ["PUT"])
def put_feed(db, org, key):
    feed, created = service.put_feed(db, int(org.id), key, json_body())
    return {"feed": feed}, 201 if created else 200


@_route("/feeds/<string:key>", ["DELETE"])
def delete_feed(db, org, key):
    service.delete_feed(db, int(org.id), key)
    return {"deleted": True}


@_route("/feeds/<string:key>/run", ["POST"])
def run_feed(db, org, key):
    service.get_feed(db, int(org.id), key)
    post_existing = json_body().get("post_existing") is True
    defer("feeds.run_feed", org_id=int(org.id), key=key, post_existing=post_existing, org_prefix=str(org.prefix))
    return {"queued": True}, 202
