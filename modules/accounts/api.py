"""HTTP routes for connected accounts: agent routes (machine tokens), the browser login, member self-service."""

import html
from typing import cast

from flask import Blueprint, jsonify, redirect, request, session

from core.config import config
from core.db import db_connect
from core.http import audit_hook
from modules.auth.decorators import member_required
from modules.auth.routes import machine_route

from . import providers, service

accounts_blueprint = Blueprint("accounts", __name__)

M = "/members/<string:discord_id>"

# Releasing a token is a read worth recording
audit_hook.AUDITED_READS.add(f"/api/accounts{M}/<string:provider>/token")


def _page(message: str, status: int = 200):
    body = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Connect an account</title></head>'
        '<body style="font-family: system-ui, sans-serif; max-width: 32rem; margin: 4rem auto; padding: 0 1rem; '
        f'line-height: 1.5"><p>{html.escape(message)}</p></body></html>'
    )
    return body, status, {"Content-Type": "text/html; charset=utf-8"}


def _agent_route(rule: str, scope: str, methods: list[str]):
    """A machine route under /members/<discord_id>. The view gets (db, org_id, discord_id, **path args)."""

    def decorator(view):
        def bound(db, org, discord_id, **kwargs):
            return view(db, cast(int, org.id), service.member(discord_id), **kwargs)

        bound.__name__ = view.__name__
        machine_route(accounts_blueprint, M + rule, scope, methods, module="accounts")(bound)
        return view

    return decorator


@accounts_blueprint.route("/providers", methods=["GET"])
def list_providers():
    return jsonify({"providers": providers.enabled()})


@_agent_route("", "accounts:link", ["GET"])
def member_accounts(db, org_id, discord_id):
    return {"accounts": service.list_grants(db, org_id, discord_id)}


@_agent_route("/<string:provider>/login", "accounts:link", ["POST"])
def start_login(db, org_id, discord_id, provider):
    return service.begin_login(db, org_id, discord_id, provider), 201


@_agent_route("/<string:provider>", "accounts:link", ["DELETE"])
def remove_account(db, org_id, discord_id, provider):
    return {"removed": service.disconnect(db, org_id, discord_id, provider)}


@_agent_route("/<string:provider>/token", "accounts:token", ["GET"])
def read_token(db, org_id, discord_id, provider):
    return service.access_token(db, org_id, discord_id, provider)


# Browser login: start link, Discord check, provider callback


@accounts_blueprint.route("/start/<string:state>", methods=["GET"])
def start(state):
    db = db_connect.SessionLocal()
    try:
        service.open_login(db, state)
    except service.AccountError as e:
        return _page(e.message, e.status)
    finally:
        db.close()
    session["accounts_login"] = state
    return redirect(providers.discord_consent_url(config.CLIENT_ID, state))


@accounts_blueprint.route("/discord/callback", methods=["GET"])
def discord_callback():
    state = request.args.get("state", "")
    expected = session.get("accounts_login")
    if not expected or expected != state or not request.args.get("code"):
        return _page("This sign-in was not started here, or was cancelled. Open the link again.", 400)
    try:
        discord_id = providers.discord_user_id(config.CLIENT_ID, config.CLIENT_SECRET, request.args["code"])
    except providers.ProviderError:
        return _page("Discord sign-in failed. Open the link again.", 502)
    db = db_connect.SessionLocal()
    try:
        consent_url = service.verify_login(db, state, discord_id)
    except service.AccountError as e:
        return _page(e.message, e.status)
    finally:
        db.close()
    session["discord_id"] = discord_id
    return redirect(consent_url)


@accounts_blueprint.route("/<string:provider>/callback", methods=["GET"])
def provider_callback(provider):
    if request.args.get("error"):
        return _page("The login was cancelled or refused. You can close this tab.")
    state, code = request.args.get("state", ""), request.args.get("code", "")
    if not state or not code:
        return _page("The login link was incomplete. Ask for a new one.", 400)
    db = db_connect.SessionLocal()
    try:
        service.finish_login(db, state, provider, code, session.get("discord_id"))
    except service.AccountError as e:
        db.rollback()
        return _page(e.message, e.status)
    finally:
        db.close()
    session.pop("accounts_login", None)
    return _page(f"Your {provider} account is connected. You can close this tab.")


# Member self-service


@accounts_blueprint.route("/<string:org_prefix>/me", methods=["GET"])
@member_required
def my_accounts(org_prefix, user_discord_id, organization):
    db = db_connect.SessionLocal()
    try:
        return jsonify({"accounts": service.list_grants(db, int(organization.id), str(user_discord_id))})
    finally:
        db.close()


@accounts_blueprint.route("/<string:org_prefix>/me/<string:provider>", methods=["DELETE"])
@member_required
def remove_my_account(org_prefix, provider, user_discord_id, organization):
    db = db_connect.SessionLocal()
    try:
        return jsonify({"removed": service.disconnect(db, int(organization.id), str(user_discord_id), provider)})
    finally:
        db.close()
