"""HTTP mirror of the MCP tools: GET /api/tools lists them, POST /api/tools/<name> calls one.

Both take a machine token (Bearer plat_...). The body of a call is the tool's arguments as JSON.

The API also serves the OAuth discovery documents of the MCP server at the root of its host, because a
client looks for them there and the reverse proxy sends only /mcp to the MCP server.
"""

from flask import Blueprint, jsonify, request

from core.db import db_connect
from core.http.request_log import bearer_token
from core.tools import ToolError
from modules.auth import machine_tokens
from modules.mcp import oauth, runtime

tools_blueprint = Blueprint("tools", __name__)
well_known_blueprint = Blueprint("mcp_well_known", __name__)


def _caller(db):
    return machine_tokens.verify(db, bearer_token())


@tools_blueprint.route("", methods=["GET"])
def list_tools():
    db = db_connect.SessionLocal()
    try:
        caller = _caller(db)
        if caller is None:
            return jsonify({"error": "A valid machine token is required"}), 401
        try:
            return jsonify({"tools": [runtime.describe(spec) for spec in runtime.available(db, caller)]})
        except ToolError as e:
            return jsonify({"error": e.message}), e.status
    finally:
        db.close()


@tools_blueprint.route("/<string:name>", methods=["POST"])
def call_tool(name):
    db = db_connect.SessionLocal()
    try:
        caller = _caller(db)
        if caller is None:
            return jsonify({"error": "A valid machine token is required"}), 401
        arguments = request.get_json(silent=True)
        if arguments is not None and not isinstance(arguments, dict):
            return jsonify({"error": "Body must be a JSON object of arguments"}), 400
        try:
            return jsonify({"result": runtime.call(db, caller, name, arguments, source="api")})
        except ToolError as e:
            return jsonify({"error": e.message}), e.status
    finally:
        db.close()


def _document(body: dict | None):
    if body is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(body), 200, {"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=3600"}


def _on(path: str) -> bool:
    """Whether OAuth is on and the request path is one of the MCP server's discovery paths."""
    return bool(oauth.public_url()) and path in [oauth.resource_metadata_path(), *oauth.server_metadata_paths()]


@well_known_blueprint.route("/oauth-protected-resource/<path:resource>", methods=["GET"])
def protected_resource(resource):
    """Protected resource metadata (RFC 9728) of the MCP server."""
    return _document(oauth.resource_metadata() if _on(request.path) else None)


@well_known_blueprint.route("/oauth-authorization-server", methods=["GET"])
@well_known_blueprint.route("/oauth-authorization-server/<path:issuer>", methods=["GET"])
def authorization_server(issuer=None):
    """Authorization server metadata (RFC 8414) of the MCP server."""
    return _document(oauth.server_metadata() if _on(request.path) else None)
