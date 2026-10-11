"""HTTP routes for the officer dashboard: the overview, branding, CI runs, and officer control of apps and knowledge.

Apps and knowledge have machine-token routes in their own modules. The routes here call the same services for
officers who sign in to the dashboard.
"""

from functools import partial
from html import escape
from typing import cast

from flask import Blueprint, redirect, request

from core import hosting, secrets
from core.config import config
from core.db import db_connect
from core.http import audit_hook
from core.http.responses import json_body
from core.integrations import registry as integrations
from modules.auth import access
from modules.auth.routes import officer_route
from modules.integrations import oauth
from modules.knowledge import crawl, documents, embedder, reembed, runs, settings
from modules.knowledge import service as knowledge
from modules.knowledge.search import search as search_chunks
from modules.organizations import service as organizations
from modules.organizations.models import Organization
from modules.runpod import service as apps
from modules.runpod import templates as app_templates
from modules.submodules import service as submodules
from submodules.asu.signin import service as asu

from . import ci, errors, notices, service
from . import trends as trends_service

dashboard_blueprint = Blueprint("dashboard", __name__)
_route = partial(officer_route, dashboard_blueprint)

# Searches are reads sent as POST
audit_hook.SKIPPED_ROUTES.add("/api/dashboard/<string:org_prefix>/knowledge/search")
audit_hook.SKIPPED_ROUTES.add("/api/dashboard/<string:org_prefix>/integrations/<string:key>/test")
# Error reports from the dashboard are not officer changes
audit_hook.SKIPPED_ROUTES.add("/api/dashboard/<string:org_prefix>/errors/report")


def _org_id(org) -> int:
    return cast(int, org.id)


def _actor() -> str:
    principal = access.current_principal()
    return f"officer:{principal.discord_id}" if principal and principal.discord_id else "officer"


@_route("/overview", ["GET"])
def overview(db, org):
    return service.overview(db, org)


@_route("/trends", ["GET"])
def trends(db, org):
    days = request.args.get("days", type=int) or trends_service.DEFAULT_DAYS
    return trends_service.trends(db, org, days)


@_route("/notifications", ["GET"])
def list_notifications(db, org):
    return notices.listing(db, org)


@_route("/notifications/resolve", ["POST"])
def resolve_notifications(db, org):
    return notices.resolve(db, org, json_body().get("ids"), _actor())


@_route("/notifications/reopen", ["POST"])
def reopen_notifications(db, org):
    return notices.reopen(db, org, json_body().get("ids"))


@_route("/notifications/delete", ["POST"])
def delete_notifications(db, org):
    return notices.delete(db, org, json_body().get("ids"))


@_route("/modules", ["GET"])
def list_modules(db, org):
    return service.modules(db, org)


@_route("/integrations", ["GET"])
def list_integrations(db, org):
    unlocks = service.unlocks()
    return {
        "integrations": [i | {"unlocks": unlocks.get(i["key"], [])} for i in integrations.status(db, _org_id(org))],
        "oauth": oauth.status(db, _org_id(org)),
        "asu": asu.status(db, _org_id(org)),
        "secrets_key": secrets.configured(),
    }


@_route("/integrations/asu/signin", ["GET"])
def asu_signin(db, org):
    return asu.status(db, _org_id(org))


@_route("/integrations/asu/signin", ["POST"])
def start_asu_signin(db, org):
    body = json_body()
    return asu.start(db, _org_id(org), body.get("netid"), body.get("password"), _actor()), 202


@_route("/integrations/asu/signin", ["DELETE"])
def stop_asu_signin(db, org):
    return asu.sign_out(db, _org_id(org))


@_route("/integrations/<string:key>/oauth", ["POST"])
def start_oauth(db, org, key):
    return {"url": oauth.start(db, _org_id(org), key, _actor())}


@_route("/integrations/<string:key>/oauth", ["DELETE"])
def stop_oauth(db, org, key):
    oauth.disconnect(db, _org_id(org), key)
    return list_integrations(db, org)


@dashboard_blueprint.route("/integrations/oauth/callback", methods=["GET"])
def oauth_callback():
    """Where a service sends the officer back after the sign-in. The state proves the sign-in started here."""
    state, code = request.args.get("state", ""), request.args.get("code", "")
    if not state or not code:
        return _oauth_page("The sign-in was cancelled. Start it again on the Integrations page.", 400)
    db = db_connect.SessionLocal()
    try:
        org_id, key = oauth.finish(db, state, code)
        org = db.query(Organization).filter_by(id=org_id).first()
        prefix = str(org.prefix) if org else ""
    except oauth.OAuthError as e:
        return _oauth_page(e.message, e.status)
    finally:
        db.close()
    if config.DASHBOARD_URL and prefix:
        return redirect(f"{config.DASHBOARD_URL}/{prefix}/explore?tab=integrations&connected={key}")
    return _oauth_page(f"{oauth.SERVICES[key].title} is connected. You can close this page.", 200)


def _oauth_page(message: str, status: int):
    body = f"<!doctype html><meta charset=utf-8><title>Platform</title><p style='font-family:sans-serif'>{escape(message)}</p>"
    return body, status, {"Content-Type": "text/html; charset=utf-8"}


@_route("/integrations/<string:key>", ["PUT"])
def save_integration(db, org, key):
    integrations.save(db, _org_id(org), key, json_body().get("fields"), _actor())
    return list_integrations(db, org)


@_route("/integrations/<string:key>/test", ["POST"])
def test_integration(db, org, key):
    try:
        return {"ok": True, "message": integrations.test(db, _org_id(org), key)}
    except integrations.IntegrationError as e:
        return {"ok": False, "message": e.message}


@_route("/branding", ["GET"])
def get_branding(db, org):
    return organizations.branding(org)


@_route("/branding", ["PUT"])
def set_branding(db, org):
    return organizations.set_branding(db, org, json_body())


@_route("/ci", ["GET"])
def ci_runs(db, org):
    return ci.runs(db, org)


@_route("/errors", ["GET"])
def list_errors(db, org):
    status = request.args.get("status", "open")
    return errors.listing(db, org, status, request.args.get("limit", 50, type=int))


@_route("/errors/resolve", ["POST"])
def resolve_errors(db, org):
    return errors.resolve(db, org, json_body().get("ids"), _actor())


@_route("/errors/reopen", ["POST"])
def reopen_errors(db, org):
    return errors.reopen(db, org, json_body().get("ids"))


@_route("/errors/delete", ["POST"])
def delete_errors(db, org):
    return errors.delete(db, org, json_body().get("ids"))


@_route("/errors/report", ["POST"])
def report_error(db, org):
    return errors.report(org, json_body())


@_route("/ci/repos", ["PUT"])
def set_ci_repos(db, org):
    return {"repos": ci.set_repos(db, org, json_body().get("repos"))}


# Hosting providers and the apps that run on them


@_route("/hosting/providers", ["GET"])
def hosting_providers(db, org):
    return {"providers": hosting.listing(db, _org_id(org))}


@_route("/apps", ["GET"], module="runpod")
def list_apps(db, org):
    return {"apps": apps.list_apps(db, _org_id(org))}


@_route("/apps/templates", ["GET"], module="runpod")
def list_app_templates(db, org):
    return {"templates": app_templates.list_templates()}


@_route("/apps/templates/<string:template>", ["POST"], module="runpod")
def create_app_from_template(db, org, template):
    data = json_body()
    app = app_templates.create(
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


@_route("/apps/<string:name>", ["GET"], module="runpod")
def get_app(db, org, name):
    return apps.get_app(db, _org_id(org), name) | {"deployments": apps.deployments(db, _org_id(org), name)}


@_route("/apps/<string:name>", ["PUT"], module="runpod")
def put_app(db, org, name):
    data = json_body()
    return apps.put_app(
        db, _org_id(org), name, data.get("manifest"), data.get("repo"), data.get("manifest_path"), data.get("provider")
    )


@_route("/apps/<string:name>", ["DELETE"], module="runpod")
def delete_app(db, org, name):
    return apps.delete_app(db, _org_id(org), name)


@_route("/apps/<string:name>/pod", ["GET"], module="runpod")
def get_app_pod(db, org, name):
    return {"pod": apps.pod(db, _org_id(org), name)}


@_route("/apps/<string:name>/deploy", ["POST"], module="runpod")
def deploy_app(db, org, name):
    data = json_body()
    dry_run = data.get("dry_run") is True
    result = apps.deploy(
        db, _org_id(org), str(org.prefix), name, data.get("tag"), _actor(), dry_run=dry_run, ref=data.get("ref")
    )
    return result, 200 if dry_run else 202


@_route("/apps/<string:name>/rollback", ["POST"], module="runpod")
def rollback_app(db, org, name):
    dry_run = json_body().get("dry_run") is True
    result = apps.rollback(db, _org_id(org), str(org.prefix), name, _actor(), dry_run=dry_run)
    return result, 200 if dry_run else 202


# Knowledge sources


@_route("/knowledge/sources", ["GET"], module="knowledge")
def list_sources(db, org):
    sources = knowledge.list_sources(db, _org_id(org), request.args.get("category"))
    return {"sources": sources, "can_publish": knowledge.can_publish(db, str(org.prefix))}


@_route("/knowledge/sources/<path:key>", ["GET"], module="knowledge")
def read_source(db, org, key):
    """One page of a source's full text. Query: chunk (a search result's chunk_id), offset."""
    offset = request.args.get("offset")
    return knowledge.read_source(
        db,
        _org_id(org),
        key,
        chunk_id=request.args.get("chunk") or None,
        offset=int(offset) if offset is not None and offset.isdigit() else offset,
    )


@_route("/knowledge/sources/<path:key>", ["DELETE"], module="knowledge")
def delete_source(db, org, key):
    knowledge.delete_source(db, _org_id(org), key)
    return {"deleted": True}


@_route("/knowledge/crawls/<path:key>", ["PUT"], module="knowledge")
def schedule_crawl(db, org, key):
    return crawl.schedule(db, _org_id(org), str(org.prefix), key, json_body())


@_route("/knowledge/crawls/<path:key>/run", ["POST"], module="knowledge")
def run_crawl(db, org, key):
    """Queue a crawl of one source now."""
    crawl.queue(db, _org_id(org), str(org.prefix), key, force=json_body().get("force") is True)
    return {"queued": True}, 202


@_route("/knowledge/submodules", ["GET"], module="knowledge")
def list_submodules(db, org):
    return {"submodules": submodules.list_submodules(db, _org_id(org))}


@_route("/knowledge/submodules/<string:name>/sync", ["POST"], module="knowledge")
def sync_submodule(db, org, name):
    """Add or update the submodule's sources, then start the crawl job for the sources that are due."""
    counts = submodules.sync(db, _org_id(org), str(org.prefix), name)
    crawl.start_crawl_due()
    return counts


@_route("/knowledge/search", ["POST"], module="knowledge")
def search(db, org):
    data = json_body()
    return search_chunks(
        db,
        _org_id(org),
        data.get("query"),
        category=data.get("category"),
        top_k=data.get("top_k"),
        embedder=embedder.for_org(db, _org_id(org)),
    )


@_route("/knowledge/documents", ["POST"], module="knowledge")
def upload_documents(db, org):
    """Index uploaded files. Form fields: files (one or more), category, folder, public."""
    uploads = [documents.Upload(f.filename or "document", f.read()) for f in request.files.getlist("files")]
    form = {"category": request.form.get("category"), "folder": request.form.get("folder")}
    form["public"] = request.form.get("public") == "true"
    return documents.upload(db, _org_id(org), str(org.prefix), uploads, form, embedder.for_org(db, _org_id(org)))


@_route("/knowledge/settings", ["GET"], module="knowledge")
def get_knowledge_settings(db, org):
    return _settings_body(db, _org_id(org), settings.for_org(db, _org_id(org)))


@_route("/knowledge/settings", ["PUT"], module="knowledge")
def set_knowledge_settings(db, org):
    return _settings_body(db, _org_id(org), settings.update(db, _org_id(org), json_body()))


def _settings_body(db, org_id: int, values: dict) -> dict:
    model = embedder.for_org(db, org_id)
    return {
        "settings": values,
        "defaults": settings.defaults(),
        "embeddings": {"configured": model is not None, "model": model.model if model else None}
        | {"status": reembed.status(db, org_id, model)},
    }


@_route("/knowledge/reindex", ["POST"], module="knowledge")
def reindex(db, org):
    """Start a job that crawls every crawled source again, so new chunk settings apply."""
    crawl.queue_job(db, _org_id(org), "knowledge.reindex", org_id=_org_id(org))
    return {"queued": True}, 202


@_route("/knowledge/reembed", ["POST"], module="knowledge")
def reembed_passages(db, org):
    """Start a job that embeds every passage that is not on the org's current embedding model."""
    return reembed.queue(db, _org_id(org)), 202


@_route("/knowledge/runs", ["GET"], module="knowledge")
def knowledge_runs(db, org):
    limit = request.args.get("limit", type=int)
    return {"runs": runs.recent(db, _org_id(org), limit, failed_only=request.args.get("failed") == "1")}
