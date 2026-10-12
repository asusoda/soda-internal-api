"""Every module's blueprint, where it is mounted, and which optional module gates it.

Model, job and tool modules are listed in modules/manifest.py. docs/writing-a-module.md lists every
place to register a new module, and tests/test_module_layout.py checks them.
"""

from dataclasses import dataclass, field

from flask import Blueprint, Flask, jsonify, request

from core.db import db_connect
from modules.accounts.api import accounts_blueprint
from modules.agents.api import agents_blueprint
from modules.alerts.api import alerts_blueprint
from modules.auth.api import auth_blueprint
from modules.calendar.api import calendar_blueprint
from modules.dashboard.api import dashboard_blueprint
from modules.feeds.api import feeds_blueprint
from modules.games.api import game_blueprint
from modules.godfather.api import godfather_blueprint
from modules.knowledge.api import knowledge_blueprint
from modules.mcp.api import tools_blueprint
from modules.organizations import service as organizations
from modules.organizations.api import organizations_blueprint
from modules.points.api import points_blueprint
from modules.public.api import public_blueprint
from modules.runpod.api import apps_blueprint
from modules.storefront.member_api import storefront_blueprint
from modules.submodules.api import asu_blueprint, submodules_blueprint
from modules.superadmin.api import superadmin_blueprint
from modules.uptime.api import uptime_blueprint
from modules.users.api import users_blueprint


@dataclass(frozen=True)
class Mount:
    blueprint: Blueprint
    url_prefix: str
    # Optional module that gates every org-scoped route of this blueprint.
    module: str | None = None
    # Optional modules that gate single endpoints, for blueprints that mix features.
    endpoint_modules: dict[str, str] = field(default_factory=dict)


MOUNTS = [
    Mount(public_blueprint, "/api/public", endpoint_modules={"get_leaderboard": "points"}),
    Mount(points_blueprint, "/api/points", module="points"),
    Mount(users_blueprint, "/api/users"),
    Mount(auth_blueprint, "/api/auth"),
    Mount(calendar_blueprint, "/api/calendar", module="calendar"),
    Mount(game_blueprint, "/api/bot"),
    Mount(organizations_blueprint, "/api/organizations"),
    Mount(superadmin_blueprint, "/api/superadmin"),
    Mount(storefront_blueprint, "/api/storefront", module="storefront"),
    Mount(tools_blueprint, "/api/tools"),
    Mount(agents_blueprint, "/api/agents", module="agents"),
    Mount(knowledge_blueprint, "/api/knowledge"),
    Mount(accounts_blueprint, "/api/accounts", module="accounts"),
    Mount(apps_blueprint, "/api/apps"),
    Mount(submodules_blueprint, "/api/submodules"),
    Mount(asu_blueprint, "/api/asu"),
    Mount(godfather_blueprint, "/api/compute", module="godfather"),
    Mount(feeds_blueprint, "/api/feeds"),
    Mount(uptime_blueprint, "/api/uptime", module="uptime"),
    Mount(dashboard_blueprint, "/api/dashboard"),
    Mount(alerts_blueprint, "/api/dashboard"),
]


def _gate(mount: Mount):
    def check_module_enabled():
        org_prefix = (request.view_args or {}).get("org_prefix")
        endpoint = (request.endpoint or "").rpartition(".")[2]
        module = mount.endpoint_modules.get(endpoint, mount.module)
        if not org_prefix or not module:
            return None
        db = db_connect.SessionLocal()
        try:
            org = organizations.find_by_prefix(db, org_prefix)
            if org is not None and not organizations.module_enabled(org, module):
                return jsonify({"error": f"The {module} feature is turned off for this organization"}), 404
        finally:
            db.close()
        return None

    return check_module_enabled


def register_modules(app: Flask) -> None:
    for mount in MOUNTS:
        if mount.module or mount.endpoint_modules:
            mount.blueprint.before_request(_gate(mount))
        app.register_blueprint(mount.blueprint, url_prefix=mount.url_prefix)
