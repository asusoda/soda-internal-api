"""Route registration for officer, member and machine-token views.

Each view gets a database session and the org and returns a JSON-able value, a (body, status)
tuple or a response. A ServiceError becomes {"error": message} with its status and rolls the
session back.
"""

from flask import Blueprint, Response, g, jsonify

from core.db import db_connect
from core.errors import ServiceError
from core.http.responses import error
from modules.auth.decorators import auth_required, machine_scope_required, member_required
from modules.organizations import service as organizations
from modules.organizations.models import Organization

INACTIVE_ORG = "The token's organization is inactive or gone"


def module_off(org: Organization, module: str | None):
    """A 404 response when the optional module is off for the org, else None."""
    if module and not organizations.module_enabled(org, module):
        return error(f"The {module} feature is turned off for this organization", 404)
    return None


def token_org(db) -> Organization | None:
    """The active organization of the calling machine token."""
    return db.query(Organization).filter_by(id=g.machine_caller.organization_id, is_active=True).first()


def respond(db, view, *args, **kwargs):
    """Call view(db, *args, **kwargs) and make its result or ServiceError a response."""
    try:
        result = view(db, *args, **kwargs)
        return result if isinstance(result, tuple | Response) else jsonify(result)
    except ServiceError as e:
        db.rollback()
        return error(e.message, e.status)


def machine_route(blueprint: Blueprint, rule: str, scope: str, methods: list[str], *, module: str | None = None):
    """Register a route for machine tokens holding scope. The view gets (db, org, **path args).

    With module set, the route returns 404 when that optional module is off for the token's org.
    """

    def decorator(view):
        def wrapper(**kwargs):
            db = db_connect.SessionLocal()
            try:
                org = token_org(db)
                if org is None:
                    return error(INACTIVE_ORG, 403)
                return module_off(org, module) or respond(db, view, org, **kwargs)
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        blueprint.route(rule, methods=methods)(machine_scope_required(scope)(wrapper))
        return view

    return decorator


def officer_route(blueprint: Blueprint, rule: str, methods: list[str], *, module: str | None = None):
    """Register a route under /<org_prefix> for officers of that active org. The view gets (db, org, **path args).

    With module set, the route returns 404 when that optional module is off for the org.
    """

    def decorator(view):
        def wrapper(org_prefix, **kwargs):
            db = db_connect.SessionLocal()
            try:
                org = organizations.find_by_prefix(db, org_prefix, active_only=True)
                if org is None:
                    return error("Organization not found", 404)
                return module_off(org, module) or respond(db, view, org, **kwargs)
            finally:
                db.close()

        wrapper.__name__ = view.__name__
        blueprint.route(f"/<string:org_prefix>{rule}", methods=methods)(auth_required(wrapper))
        return view

    return decorator


def member_view(view):
    """Wrap a view for members signed in with Discord (member_required). It gets (db, org, discord_id, **path args)."""

    def wrapper(org_prefix, user_discord_id=None, organization=None, **kwargs):
        db = db_connect.SessionLocal()
        try:
            return respond(db, view, organization, str(user_discord_id), **kwargs)
        finally:
            db.close()

    wrapper.__name__ = view.__name__
    return member_required(wrapper)
