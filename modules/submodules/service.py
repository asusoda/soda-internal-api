"""Submodules: domains such as a campus or careers that an org subscribes to, and their live queries. No Flask here.

A submodule brings its parts to each module that reads it: pages to knowledge, feeds to the webhook modules,
live queries to agents. Its pages are crawled sources of the submodule itself (knowledge_sources.submodule_id,
no org), under keys that start with <submodule>/. The deployment crawls and embeds them once, with its own
embedder, Firecrawl and chunk settings, while one or more orgs subscribe. A subscribed org's search reads them,
and its feed presets come from the submodules it subscribes to. A live query fetches one page or API with
parameters, answers the caller, and then indexes what it read as a source of the org.
"""

import hashlib
from typing import Any, cast

from sqlalchemy import func

from core import limits
from core.jobs import defer
from core.log import get_logger
from core.time import utcnow
from modules.auth import scopes
from modules.knowledge import crawl, fetch
from modules.knowledge.embedder import Embedder
from modules.knowledge.models import KnowledgeSource, KnowledgeVersion
from modules.knowledge.service import KnowledgeError, can_publish, new_source
from modules.submodules import catalog, queries
from modules.submodules.models import Submodule as SubmoduleRow
from modules.submodules.models import SubmoduleSubscription
from modules.submodules.search import query_scope, settings
from modules.submodules.types import QueryError, Submodule

logger = get_logger("submodules")


def subscription_count(db, org_id: int) -> int:
    return db.query(SubmoduleSubscription).filter_by(organization_id=org_id).count()


scopes.declare("submodules:read", "List the submodules and which ones the org subscribes to")
scopes.declare("submodules:manage", "Subscribe the org to a submodule, or end a subscription")

SUBSCRIPTIONS_LIMIT = "submodules.subscriptions"
limits.declare(
    SUBSCRIPTIONS_LIMIT, "submodules", "Submodule subscriptions", 20, unit="submodules", usage=subscription_count
)


def _submodule(name: object) -> Submodule:
    submodule = catalog.get(name)
    if submodule is None:
        raise KnowledgeError(f"No submodule named {name}", 404)
    return submodule


def row_for(db, submodule: Submodule) -> SubmoduleRow:
    """The submodule's row, made or brought up to date from the code in submodules/. Flushes."""
    row = db.query(SubmoduleRow).filter_by(key=submodule.name).first()
    if row is None:
        row = SubmoduleRow(key=submodule.name, origin="code", status="shared")
        db.add(row)
    row.title, row.description = submodule.title, submodule.description
    db.flush()
    return row


def _subscribed_ids(db, org_id: int) -> set[int]:
    rows = db.query(SubmoduleSubscription.submodule_id).filter_by(organization_id=org_id).all()
    return {int(r[0]) for r in rows}


def subscribed_names(db, org_id: int) -> set[str]:
    """The keys of the submodules the org subscribes to."""
    rows = (
        db.query(SubmoduleRow.key)
        .join(SubmoduleSubscription, SubmoduleSubscription.submodule_id == SubmoduleRow.id)
        .filter(SubmoduleSubscription.organization_id == org_id)
        .all()
    )
    return {str(r[0]) for r in rows}


def _users(name: str) -> list[str]:
    """The modules that read the submodule, from the catalog in modules/manifest.py."""
    from modules.manifest import CATALOG

    return sorted(module for module, info in CATALOG.items() if name in info.submodules and module != "submodules")


def list_submodules(db, org_id: int) -> list[dict]:
    """Every submodule, whether the org subscribes, how many orgs do, its shared pages and its last crawl."""
    rows = {r.key: r for r in db.query(SubmoduleRow).all()}
    mine = _subscribed_ids(db, org_id)
    result = []
    for submodule in catalog.SUBMODULES.values():
        row = rows.get(submodule.name)
        stats = (0, None)
        subscribers = 0
        if row is not None:
            stats = (
                db.query(func.count(KnowledgeSource.id), func.max(KnowledgeSource.last_attempt_at))
                .filter(KnowledgeSource.submodule_id == row.id, KnowledgeSource.enabled.is_(True))
                .one()
            )
            subscribers = db.query(SubmoduleSubscription).filter_by(submodule_id=row.id).count()
        result.append(
            {
                "name": submodule.name,
                "title": submodule.title,
                "description": submodule.description,
                "key_prefix": submodule.key_prefix,
                "pages": len(submodule.sources),
                "queries": [q.key for q in submodule.queries],
                "feeds": [f.key for f in submodule.feeds],
                "sources": int(stats[0] or 0),
                "last_crawl": stats[1].isoformat() if stats[1] else None,
                "subscribed": row is not None and int(cast(int, row.id)) in mine,
                "subscribers": subscribers,
                "modules": _users(submodule.name),
            }
        )
    return result


def sync_shared(db, submodule: Submodule) -> dict:
    """Make the submodule's shared crawled sources match its page list. Retired ones are disabled. Flushes."""
    row = row_for(db, submodule)
    existing = {s.key: s for s in db.query(KnowledgeSource).filter(KnowledgeSource.submodule_id == row.id)}
    counts = {"added": 0, "updated": 0, "retired": 0}
    for spec in submodule.sources:
        key = submodule.key_prefix + spec.key
        source = existing.pop(key, None)
        if source is None:
            source = KnowledgeSource(organization_id=None, submodule_id=row.id, key=key, enabled=True)
            db.add(source)
            counts["added"] += 1
        else:
            counts["updated"] += 1
        if source.url != spec.url:
            source.last_attempt_at = None
        source.url, source.category, source.public = spec.url, spec.category, False
        source.fetch_every_hours = spec.fetch_every_hours
        source.extractor = submodule.extractor_name(spec)
        source.enabled = True
        source.updated_at = utcnow()
    for source in existing.values():
        if source.enabled:
            source.enabled = False
            counts["retired"] += 1
    db.flush()
    return counts


def subscribe(db, org_id: int, name: object, actor: str | None = None) -> dict:
    """Subscribe the org to the submodule and bring its shared sources up to date. Commits.

    Returns the counts of the sync (added, updated, retired) and subscribed: true.
    """
    submodule = _submodule(name)
    row = row_for(db, submodule)
    if row.status != "shared":
        raise KnowledgeError(f"The submodule {submodule.name} is not shared", 409)
    current = db.query(SubmoduleSubscription).filter_by(organization_id=org_id, submodule_id=row.id).first()
    if current is None:
        limits.check(db, org_id, SUBSCRIPTIONS_LIMIT)
        db.add(SubmoduleSubscription(organization_id=org_id, submodule_id=row.id, created_by=actor))
    counts = sync_shared(db, submodule)
    db.commit()
    logger.info("submodule subscribed org=%s submodule=%s %s", org_id, submodule.name, counts)
    return counts | {"subscribed": True}


def unsubscribe(db, org_id: int, name: object) -> dict:
    """End the org's subscription. The shared sources stay for the other subscribers. Commits."""
    submodule = _submodule(name)
    row = db.query(SubmoduleRow).filter_by(key=submodule.name).first()
    if row is not None:
        db.query(SubmoduleSubscription).filter_by(organization_id=org_id, submodule_id=row.id).delete()
    db.commit()
    return {"subscribed": False}


def sync(db, org_id: int, org_prefix: str, name: object) -> dict:
    """Older name of subscribe(), for the sync routes and tools that clients still call."""
    return subscribe(db, org_id, name)


def overview(db) -> list[dict]:
    """Every submodule row with its subscribers, shared pages, passages and failing pages, for the superadmin."""
    result = []
    for row in db.query(SubmoduleRow).order_by(SubmoduleRow.key).all():
        sources = db.query(KnowledgeSource).filter(KnowledgeSource.submodule_id == row.id)
        passages = (
            db.query(func.coalesce(func.sum(KnowledgeVersion.chunk_count), 0))
            .join(KnowledgeSource, KnowledgeSource.current_version_id == KnowledgeVersion.id)
            .filter(KnowledgeSource.submodule_id == row.id)
            .scalar()
        )
        failing = [
            {"key": s.key, "error": s.last_error} for s in sources.filter(KnowledgeSource.last_error.isnot(None))
        ]
        result.append(
            {
                "key": row.key,
                "title": row.title,
                "origin": row.origin,
                "status": row.status,
                "subscribers": db.query(SubmoduleSubscription).filter_by(submodule_id=row.id).count(),
                "sources": sources.filter(KnowledgeSource.enabled.is_(True)).count(),
                "passages": int(passages or 0),
                "failing": failing[:50],
            }
        )
    return result


def query_sources(name: object) -> list[dict]:
    return [
        {
            "key": q.key,
            "description": q.description,
            "params": [
                {
                    "name": p.name,
                    "description": p.description,
                    "required": p.required,
                    "example": p.example,
                    "choices": list(p.choices),
                    "many": p.many,
                }
                for p in q.params
            ],
        }
        for q in _submodule(name).queries
    ]


def _params(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise KnowledgeError("params must be an object of strings")
    out = {}
    for k, v in value.items():
        if isinstance(v, list):
            v = ",".join(str(x) for x in v)
        if not isinstance(v, str | int | float) or isinstance(v, bool) or len(str(v)) > 500:
            raise KnowledgeError(f"params.{k} must be a string of at most 500 characters")
        out[k] = str(v)
    return out


def query(db, org_id: int, org_prefix: str, name: object, source_key: Any, params: Any) -> dict:
    """Run a live query and return the cited URL and text. Queues indexing of the result when allowed."""
    submodule = _submodule(name)
    source = next((q for q in submodule.queries if q.key == source_key), None)
    if source is None:
        raise KnowledgeError(f"Submodule {submodule.name} has no live source named {source_key}", 404)
    try:
        with query_scope(db, org_id):
            if source.needs_search and not settings().search.base_url:
                raise KnowledgeError("Web search needs a SearXNG server. Set one on the Integrations page", 503)
            url, text = queries.run(source, _params(params))
    except QueryError as e:
        raise KnowledgeError(str(e), 422) from e
    except fetch.FetchRejected as e:
        raise KnowledgeError(str(e), 422) from e
    except fetch.FetchError as e:
        raise KnowledgeError(str(e), 502) from e
    limit = settings().scraper.query_max_chars
    text = text if len(text) <= limit else text[:limit].rsplit("\n", 1)[0]
    if source.index and text.strip():
        defer(
            "submodules.index_result",
            org_id=org_id,
            org_prefix=org_prefix,
            submodule=submodule.name,
            query_key=source.key,
            url=url,
            text=text,
        )
    return {"submodule": submodule.name, "source": source.key, "url": url, "text": text}


def index_result(
    db, org_id: int, org_prefix: str, submodule: str, query_key: str, url: str, text: str, embedder: Embedder | None
) -> dict:
    """Index a live result as a source of the org, under <submodule>-live/. Commits.

    It never writes into a submodule's shared crawled source, which other orgs read.
    """
    owner = _submodule(submodule)
    digest = hashlib.sha256(url.encode()).hexdigest()[:10]
    key = f"{owner.live_prefix}{query_key}-{digest}"
    source = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=key).first()
    if source is None:
        category = next((q.category for q in owner.queries if q.key == query_key), "live")
        source = new_source(db, org_id, key=key, url=url, category=category, public=can_publish(db, org_prefix))
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    previous = db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first()
    if previous is not None and previous.content_hash == content_hash:
        db.commit()
        return {"key": source.key, "changed": False}
    title = f"{query_key.replace('_', ' ')}: {url}"
    result = crawl.index_text(db, source, text, title, content_hash, embedder, previous=previous, force=True)
    logger.info("live result indexed source=%s chunks=%s", source.key, result["chunks"])
    return result
