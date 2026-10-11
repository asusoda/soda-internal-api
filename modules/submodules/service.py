"""Submodules for the knowledge module: add a submodule's pages to an org, and run its live queries. No Flask here.

sync() registers every page of a submodule as a crawled knowledge source of an org, under keys that start
with <submodule>/. A live query fetches one page or API with parameters, answers the caller, and then
indexes what it read, where the query allows it.
"""

import hashlib
from typing import Any

from sqlalchemy import func

from core import limits
from core.jobs import defer
from core.log import get_logger
from modules.knowledge import crawl, fetch
from modules.knowledge.embedder import Embedder
from modules.knowledge.models import KnowledgeSource, KnowledgeVersion
from modules.knowledge.service import SOURCES_LIMIT, KnowledgeError, can_publish, new_source
from modules.submodules import catalog, queries
from modules.submodules.search import query_scope, settings
from modules.submodules.types import QueryError, Submodule

logger = get_logger("submodules")


def _submodule(name: object) -> Submodule:
    submodule = catalog.get(name)
    if submodule is None:
        raise KnowledgeError(f"No submodule named {name}", 404)
    return submodule


def list_submodules(db, org_id: int) -> list[dict]:
    """Every submodule with the number of the org's enabled sources it owns."""
    result = []
    for submodule in catalog.SUBMODULES.values():
        count = (
            db.query(func.count(KnowledgeSource.id))
            .filter(
                KnowledgeSource.organization_id == org_id,
                KnowledgeSource.key.like(submodule.key_prefix + "%"),
                KnowledgeSource.enabled.is_(True),
            )
            .scalar()
        )
        result.append(
            {
                "name": submodule.name,
                "title": submodule.title,
                "description": submodule.description,
                "key_prefix": submodule.key_prefix,
                "pages": len(submodule.sources),
                "queries": [q.key for q in submodule.queries],
                "feeds": [f.key for f in submodule.feeds],
                "sources": int(count or 0),
            }
        )
    return result


def sync(db, org_id: int, org_prefix: str, name: object) -> dict:
    """Make the org's crawled sources of the submodule match its page list. Retired ones are disabled. Commits."""
    submodule = _submodule(name)
    public = can_publish(db, org_prefix)
    existing = {
        s.key: s
        for s in db.query(KnowledgeSource).filter(
            KnowledgeSource.organization_id == org_id, KnowledgeSource.key.like(submodule.key_prefix + "%")
        )
    }
    counts = {"added": 0, "updated": 0, "retired": 0}
    adding = sum(1 for spec in submodule.sources if submodule.key_prefix + spec.key not in existing)
    limits.check(db, org_id, SOURCES_LIMIT, add=adding)
    for spec in submodule.sources:
        key = submodule.key_prefix + spec.key
        source = existing.pop(key, None)
        if source is None:
            source = KnowledgeSource(organization_id=org_id, key=key, enabled=True)
            db.add(source)
            counts["added"] += 1
        else:
            counts["updated"] += 1
        if source.url != spec.url:
            source.last_attempt_at = None
        source.url, source.category, source.public = spec.url, spec.category, public
        source.fetch_every_hours = spec.fetch_every_hours
        source.extractor = submodule.extractor_name(spec)
    for source in existing.values():
        if source.enabled:
            source.enabled = False
            counts["retired"] += 1
    db.commit()
    return counts


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
    """Index a live result: under the submodule's crawled source with the same URL, else its own source. Commits."""
    owner = _submodule(submodule)
    spec = next((s for s in owner.sources if s.url == url), None)
    source = None
    if spec is not None:
        source = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=owner.key_prefix + spec.key).first()
    if source is None:
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
