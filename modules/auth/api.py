import secrets
import time
from urllib.parse import urlencode

import requests
from flask import Blueprint, jsonify, redirect, request, session

from core.config import config
from core.db import db_connect
from core.http.request_log import bearer_token
from core.http.responses import error_handler
from core.integrations.discord import DiscordUnavailable
from core.log import logger
from modules.auth.access import decide, discord_directory, officer_guilds
from modules.auth.decorators import auth_required
from modules.auth.tokens import token_manager

auth_blueprint = Blueprint("auth", __name__, template_folder=None, static_folder=None)
CLIENT_ID = config.CLIENT_ID
CLIENT_SECRET = config.CLIENT_SECRET
REDIRECT_URI = config.REDIRECT_URI

logger.info(f"Auth API using CLIENT_ID: {CLIENT_ID} and REDIRECT_URI: {REDIRECT_URI}")


# One-time login codes: the OAuth callback hands the browser a code, not the tokens, and the
# client trades it for the tokens with POST /exchange. Held in memory, so this assumes one API
# process (main.py runs one). Codes live LOGIN_CODE_SECONDS and work once.
LOGIN_CODE_SECONDS = 60
_login_codes: dict[str, tuple[float, str, str]] = {}


def _issue_login_code(access_token: str, refresh_token: str) -> str:
    now = time.monotonic()
    for code in [c for c, entry in _login_codes.items() if entry[0] <= now]:
        _login_codes.pop(code, None)
    code = secrets.token_urlsafe(32)
    _login_codes[code] = (now + LOGIN_CODE_SECONDS, access_token, refresh_token)
    return code


def _client_url(client: str | None) -> str:
    """Where the browser goes after login: the dashboard when it started there and DASHBOARD_URL is set."""
    dashboard = getattr(config, "DASHBOARD_URL", "")
    return dashboard if client == "dashboard" and dashboard else config.CLIENT_URL


@auth_blueprint.route("/login", methods=["GET"])
def login():
    logger.info(f"Redirecting to Discord OAuth login for client_id: {CLIENT_ID} and REDIRECT_URI: {REDIRECT_URI}")
    # An officer login that follows an unfinished store login must not return to the store
    session.pop("store_login_org", None)
    return _discord_redirect("identify guilds")


@auth_blueprint.route("/store_login", methods=["GET"])
def store_login():
    """Start a member's Discord sign-in for the store of the org in ?org. The callback returns to the store."""
    from modules.organizations.service import find_by_prefix

    with db_connect.SessionLocal() as db:
        organization = find_by_prefix(db, request.args.get("org", ""), active_only=True)
    if not organization:
        return jsonify({"error": "Organization not found"}), 404
    session["store_login_org"] = organization.prefix
    return _discord_redirect("identify")


def _discord_redirect(scope: str):
    """Redirect to Discord's consent page with a new state that /callback checks."""
    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    session["oauth_client"] = "dashboard" if request.args.get("client") == "dashboard" else "web"
    query = urlencode(
        {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": scope,
            "state": state,
        }
    )
    return redirect(f"https://discord.com/oauth2/authorize?{query}")


@auth_blueprint.route("/exchange", methods=["POST"])
def exchange_login_code():
    """Trade a one-time login code from the OAuth callback for the token pair."""
    data = request.get_json(silent=True) or {}
    entry = _login_codes.pop(str(data.get("code", "")), None)
    if entry is None or entry[0] <= time.monotonic():
        return jsonify({"error": "Invalid or expired login code"}), 400
    _, access_token, refresh_token = entry
    return jsonify({"access_token": access_token, "refresh_token": refresh_token}), 200


@auth_blueprint.route("/validToken", methods=["GET"])
@auth_required
def validToken():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"status": "error", "valid": False, "message": "No authorization header"}), 401
    token = bearer_token()
    if token_manager.is_token_valid(token):
        return jsonify({"status": "success", "valid": True, "expired": False}), 200
    else:
        return jsonify({"status": "error", "valid": False}), 401


@auth_blueprint.route("/callback", methods=["GET"])
def callback():
    directory = discord_directory()
    if directory is None or not directory.is_ready():
        logger.error("Discord directory is not configured for /callback")
        return jsonify({"error": "Authentication service temporarily unavailable. Bot not ready."}), 503

    code = request.args.get("code")
    if not code:
        logger.warning("No authorization code provided in /callback")
        return jsonify({"error": "No authorization code provided"}), 400

    # The state must match the one /login stored, so a login started elsewhere is not accepted
    expected_state = session.pop("oauth_state", None)
    client_url = _client_url(session.pop("oauth_client", None))
    store_org = session.pop("store_login_org", None)
    store_url = f"{client_url}/store/{store_org}"
    if not expected_state or not secrets.compare_digest(expected_state, request.args.get("state", "")):
        # A store login is new, so it refuses a wrong state in report mode too
        if store_org:
            return redirect(f"{store_url}?error=Sign-in expired, please try again")
        if decide("oauth_state_mismatch"):
            return redirect(f"{client_url}/auth/?error=Login expired, please try again")

    logger.info("Received authorization code, exchanging for token.")
    token_response = requests.post(
        "https://discord.com/api/v10/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,  # Add timeout to prevent hanging requests
    )
    token_response_data = token_response.json()

    if "access_token" in token_response_data:
        access_token = token_response_data["access_token"]
        logger.info("Access token received, fetching user info.")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        user_response = requests.get("https://discord.com/api/v10/users/@me", headers=headers, timeout=30)
        user_info = user_response.json()
        user_id = user_info["id"]
        if store_org:
            # The store routes check that this Discord user is in the org's server
            session["discord_id"] = user_id
            return redirect(store_url)
        try:
            guilds = officer_guilds(directory, user_id)
        except DiscordUnavailable:
            logger.exception("Discord unavailable during /callback")
            return jsonify({"error": "Authentication service temporarily unavailable."}), 503
        logger.debug(f"Officer guilds: {guilds}")
        if guilds:  # If user is officer in at least one organization
            # Server nickname in the first officer guild, else the Discord display name
            try:
                name = directory.get_display_name(guilds[0], user_id)
            except DiscordUnavailable:
                name = None
            name = name or user_info.get("global_name") or user_info.get("username")
            access_token, refresh_token = token_manager.generate_token_pair(
                username=name, discord_id=user_id, access_exp_minutes=30, refresh_exp_days=7
            )
            session["user"] = {
                "username": name,
                "discord_id": user_id,
                "role": "officer",
                "officer_guilds": guilds,  # Store the list of guild IDs where user is officer
            }
            session["token"] = access_token
            session["refresh_token"] = refresh_token
            # Redirect to the React frontend with a one-time code; the tokens stay out of the URL
            login_code = _issue_login_code(access_token, refresh_token)
            return redirect(f"{client_url}/auth/?code={login_code}")
        else:
            full_url = f"{client_url}/auth/?error=Unauthorized Access"
            return redirect(full_url)
    else:
        logger.error(f"Failed to retrieve access token from Discord: {token_response_data}")
        return jsonify({"error": "Failed to retrieve access token"}), 400


@auth_blueprint.route("/refresh", methods=["POST"])
def refresh_token():
    """
    Refresh access token using refresh token.
    """
    try:
        data = request.get_json()
        if not data or "refresh_token" not in data:
            return jsonify({"error": "Refresh token required"}), 400

        refresh_token = data["refresh_token"]

        new_access_token = token_manager.refresh_access_token(refresh_token)

        if new_access_token:
            return jsonify(
                {
                    "access_token": new_access_token,
                    "token_type": "Bearer",  # nosec B105 - OAuth2 token type, not a password
                    "expires_in": 1800,  # 30 minutes in seconds
                }
            ), 200
        else:
            return jsonify({"error": "Invalid or expired refresh token"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_blueprint.route("/revoke", methods=["POST"])
@auth_required
def revoke_token():
    """
    Revoke refresh token (logout).
    """
    try:
        data = request.get_json()
        if not data or "refresh_token" not in data:
            return jsonify({"error": "Refresh token required"}), 400

        refresh_token = data["refresh_token"]

        if token_manager.revoke_refresh_token(refresh_token):
            current_token = bearer_token()
            if current_token:
                token_manager.delete_token(current_token)

            return jsonify({"message": "Token revoked successfully"}), 200
        else:
            return jsonify({"error": "Invalid refresh token"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_blueprint.route("/validateToken", methods=["GET"])
def valid_token():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"status": "error", "valid": False, "message": "No authorization header"}), 401
    token = bearer_token()
    if token_manager.is_token_valid(token):
        if token_manager.is_token_expired(token):
            logger.info("Token is valid but expired.")
            return jsonify({"status": "success", "valid": True, "expired": True}), 200
        else:
            logger.info("Token is valid and not expired.")
            return jsonify({"status": "success", "valid": True, "expired": False}), 200
    else:
        logger.warning("Token validation failed (invalid).")
        return jsonify({"status": "error", "valid": False, "message": "Token is invalid"}), 401


@auth_blueprint.route("/appToken", methods=["GET"])
@auth_required
@error_handler
def get_app_token():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "No authorization header"}), 401
    token = bearer_token()
    appname = request.args.get("appname")
    if not appname:
        return jsonify({"error": "appname query parameter is required"}), 400

    username = token_manager.retrieve_username(token)
    if not username:
        return jsonify({"error": "Invalid user token"}), 401

    logger.info(f"Generating app token for user {username}, app: {appname}")
    app_token_value = token_manager.generate_app_token(username, appname, token_manager.retrieve_discord_id(token))
    return jsonify({"app_token": app_token_value}), 200


@auth_blueprint.route("/name", methods=["GET"])
@auth_required
def get_name():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "No authorization header"}), 401
    return jsonify({"name": token_manager.retrieve_username(bearer_token())}), 200


@auth_blueprint.route("/logout", methods=["POST"])
def logout():
    """
    Logout endpoint that revokes refresh token.
    """
    try:
        data = request.get_json()
        if data and "refresh_token" in data:
            token_manager.revoke_refresh_token(data["refresh_token"])

        token = bearer_token()
        if token:
            token_manager.delete_token(token)

        session.clear()

        return jsonify({"message": "Logged out successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_blueprint.route("/success")
def success():
    return "You have successfully logged in with Discord! (This is a generic success page)"


@auth_blueprint.route("/appTokens", methods=["GET"])
@auth_required
def list_app_tokens():
    """App tokens the signed-in officer issued and has not revoked."""
    from modules.auth.models import AppToken

    discord_id = _caller_discord_id()
    db = db_connect.SessionLocal()
    try:
        tokens = (
            db.query(AppToken)
            .filter(AppToken.discord_id == discord_id, AppToken.revoked_at.is_(None))
            .order_by(AppToken.created_at.desc())
            .all()
        )
        return jsonify(
            [
                {
                    "id": t.id,
                    "app_name": t.app_name,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "expires_at": t.expires_at.isoformat(),
                }
                for t in tokens
            ]
        ), 200
    finally:
        db.close()


@auth_blueprint.route("/appTokens/<int:token_id>", methods=["DELETE"])
@auth_required
def revoke_app_token(token_id):
    """Revoke one of the signed-in officer's app tokens. The superadmin may revoke any."""
    import datetime

    from modules.auth.access import is_superadmin
    from modules.auth.models import AppToken

    discord_id = _caller_discord_id()
    db = db_connect.SessionLocal()
    try:
        token = db.query(AppToken).filter(AppToken.id == token_id).first()
        if token is None or (token.discord_id != discord_id and not is_superadmin(discord_id)):
            return jsonify({"error": "App token not found"}), 404
        token.revoked_at = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        db.commit()
        return jsonify({"message": "App token revoked"}), 200
    finally:
        db.close()


def _caller_discord_id():
    token = session.get("token")
    if not token:
        token = bearer_token()
    return token_manager.retrieve_discord_id(token) if token else None


@auth_blueprint.route("/machine/whoami", methods=["GET"])
def machine_whoami():
    """What a machine token is: its org, name, kind and scopes. 401 for anything else."""
    from modules.auth import machine_tokens
    from modules.organizations.models import Organization

    token = bearer_token()
    db = db_connect.SessionLocal()
    try:
        caller = machine_tokens.verify(db, token)
        if caller is None:
            return jsonify({"error": "A valid machine token is required"}), 401
        org = db.query(Organization).filter_by(id=caller.organization_id).first()
        return jsonify(
            {
                "org": org.prefix if org else None,
                "name": caller.name,
                "kind": caller.kind,
                "scopes": sorted(caller.scopes),
            }
        )
    finally:
        db.close()
