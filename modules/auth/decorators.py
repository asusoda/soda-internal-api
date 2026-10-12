"""Route decorators: who may call a view. Each answers with JSON and a status when it refuses."""

from functools import wraps

from flask import g, jsonify, request, session

from core.db import db_connect
from core.http.request_log import bearer_token
from core.log import get_logger
from modules.auth import clerk, machine_tokens
from modules.auth.access import (
    discord_directory,
    is_superadmin,
    officer_guild_ids,
    org_officer_denial,
    superadmin_denial,
)
from modules.auth.tokens import token_manager
from modules.organizations import service as organizations

logger = get_logger(__name__)

# (message, status) for each problem with a platform token in a header, and in the session cookie
_HEADER_REFUSALS: dict[str, tuple[str, int]] = {
    "invalid": ("Token is invalid!", 401),
    "expired": ("Token is expired!", 403),
}
_SESSION_REFUSALS: dict[str, tuple[str, int]] = {
    "invalid": ("Session token is invalid!", 401),
    "expired": ("Session token has expired!", 401),
}


def _token_problem(token: str) -> str | None:
    """Why a platform token cannot be used: "invalid", "expired", or None when it can."""
    if not token_manager.is_token_valid(token):
        return "invalid"
    if token_manager.is_token_expired(token):
        return "expired"
    return None


def _refuse(message: str, status: int):
    return jsonify({"message": message}), status


def _session_refusal():
    """The refusal for a bad session token, which also leaves the session. None when the token is good."""
    problem = _token_problem(session["token"])
    if problem is None:
        return None
    session.pop("token", None)
    return _refuse(*_SESSION_REFUSALS[problem])


def dual_auth_required(f):
    """Accept a Clerk session token, else a platform token in the session cookie or the header.

    Sets g.clerk_user_email: the Clerk email, or the platform token's username.
    A Clerk sign-in also sets g.clerk_user.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        token = bearer_token()

        if token:
            try:
                result = clerk.verify_clerk_token(token)
                if result:
                    email, clerk_user = result
                    logger.debug(f"Dual auth: Clerk authentication successful for {email}")
                    g.clerk_user_email = email
                    g.clerk_user = clerk_user
                    return f(*args, **kwargs)
                logger.debug("Dual auth: Clerk token verification failed, trying Discord OAuth")
            except Exception as e:
                logger.debug(f"Dual auth: Clerk verification error: {e}, trying Discord OAuth")

        if session.get("token"):
            try:
                refusal = _session_refusal()
                if refusal:
                    return refusal
                username = token_manager.retrieve_username(session["token"])
                if username:
                    g.clerk_user_email = username
                return f(*args, **kwargs)
            except Exception as e:
                logger.debug(f"Dual auth: Session authentication error: {e}")
                session.pop("token", None)

        if not token:
            return _refuse("Authentication required!", 401)

        try:
            problem = _token_problem(token)
            if problem:
                return _refuse(*_HEADER_REFUSALS[problem])
            username = token_manager.retrieve_username(token)
            if username:
                g.clerk_user_email = username
            return f(*args, **kwargs)
        except Exception as e:
            logger.debug(f"Dual auth: Discord OAuth token authentication error: {e}")
            return _refuse("Authentication failed due to an internal error.", 401)

    return wrapper


def auth_required(f):
    """Require a platform token in the session cookie or the header, from an officer of the org in the URL."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("token"):
            try:
                refusal = _session_refusal()
                if refusal:
                    return refusal
            except Exception:
                session.pop("token", None)
                return _refuse("Session authentication failed!", 401)
            return _with_org_scope(f, *args, **kwargs)

        token = bearer_token()
        if not token:
            return _refuse("Authentication required!", 401)

        try:
            problem = _token_problem(token)
            if problem:
                return _refuse(*_HEADER_REFUSALS[problem])
        except Exception as e:
            logger.debug(f"Token check error: {e}")
            return _refuse("Authentication failed due to an internal error.", 401)
        return _with_org_scope(f, *args, **kwargs)

    return wrapper


def org_officer_required(f):
    """For routes behind dual_auth_required that only officers use: refuse members and other orgs' officers."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        return _with_org_scope(f, *args, **kwargs)

    return wrapper


def _with_org_scope(f, *args, **kwargs):
    """Run an authenticated route, refusing callers who are not officers of the org in its URL."""
    denial = org_officer_denial()
    if denial:
        return _refuse(*denial)
    return f(*args, **kwargs)


def superadmin_required(f):
    """Require the superadmin: an admin session, or a platform token whose discord_id is the superadmin."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        token = session.get("token")
        if token:
            try:
                problem = _token_problem(token)
                if problem:
                    return _refuse(*_HEADER_REFUSALS[problem])
                if session.get("user", {}).get("role") != "admin":
                    return _refuse("Superadmin access required!", 403)
                return f(*args, **kwargs)
            except Exception as e:
                logger.debug(f"Error validating session token: {e}")
                return _refuse("Authentication failed due to an internal error.", 401)

        if "Authorization" in request.headers and not request.headers["Authorization"].startswith("Bearer "):
            return _refuse("Invalid Authorization header format!", 401)
        token = bearer_token()
        if not token:
            return _refuse("Authentication required!", 401)

        try:
            problem = _token_problem(token)
            if problem:
                return _refuse(*_HEADER_REFUSALS[problem])
            token_data = token_manager.decode_token(token)
            if not token_data:
                return _refuse("Invalid token data!", 401)

            # Every token issued at login carries discord_id; tokens without it are refused
            discord_id = token_data.get("discord_id")
            if not discord_id:
                return _refuse("Token missing user identification!", 401)

            officer_guilds = officer_guild_ids(str(discord_id))
            if officer_guilds is None:
                return _refuse("Bot not available for verification!", 503)
            if not officer_guilds and not is_superadmin(str(discord_id)):
                return _refuse("Superadmin access required!", 403)

            denial = superadmin_denial(str(discord_id))
            if denial:
                return _refuse(*denial)
            return f(*args, **kwargs)
        except Exception as e:
            logger.exception(f"General error in superadmin_required: {e}")
            return _refuse(str(e), 401)

    return wrapper


def member_required(f):
    """Require a Discord login session from a member of the active org named by org_prefix.

    The view also gets user_discord_id and organization as keyword arguments.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            org_prefix = kwargs.get("org_prefix") or (args[0] if args else None)
            if not org_prefix:
                return _refuse("Organization prefix is required", 400)

            user_discord_id = session.get("discord_id")
            if not user_discord_id:
                return _refuse("Discord authentication required", 401)

            try:
                with db_connect.SessionLocal() as db:
                    organization = organizations.find_by_prefix(db, org_prefix, active_only=True)
            except Exception as e:
                logger.error(f"Database error: {e}")
                return _refuse(f"Database error: {str(e)}", 500)
            if not organization:
                return _refuse("Organization not found", 404)

            try:
                directory = discord_directory()
                if directory is None or not directory.is_ready():
                    return _refuse("Discord bot not available", 503)
                if not directory.check_user_membership(int(user_discord_id), int(organization.guild_id)):
                    return _refuse("You must be a member of this organization to access this resource", 403)
                kwargs["user_discord_id"] = user_discord_id
                kwargs["organization"] = organization
                return f(*args, **kwargs)
            except Exception:
                logger.exception("Error checking guild membership")
                return _refuse("Error verifying membership", 500)

        except Exception:
            logger.exception("General error in member_required")
            return _refuse("Internal server error", 500)

    return wrapper


def machine_scope_required(scope: str):
    """For routes called by apps and agents with a machine token (Bearer plat_...).

    The token must hold scope, and when the route names an org it must be the token's org.
    The caller is available as flask.g.machine_caller.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            db = db_connect.SessionLocal()
            try:
                caller = machine_tokens.verify(db, bearer_token())
                if caller is None:
                    return jsonify({"error": "A valid machine token is required"}), 401
                if not caller.allows(scope):
                    return jsonify({"error": f"Token lacks scope {scope}"}), 403
                org_prefix = (request.view_args or {}).get("org_prefix")
                if org_prefix is not None:
                    org = organizations.find_by_prefix(db, org_prefix)
                    if org is None or org.id != caller.organization_id:
                        return jsonify({"error": "Token belongs to a different organization"}), 403
            finally:
                db.close()
            g.machine_caller = caller
            return f(*args, **kwargs)

        return wrapper

    return decorator
