"""Crawled sources: the platform fetches a URL on a schedule, extracts, chunks, embeds and indexes it.

A run is skipped after
the fetch when the page hash is unchanged, and refused when the extracted text shrank below half
of the last indexed version, so a broken page cannot wipe a good index. No Flask here.
"""

import datetime
import hashlib
import os
from collections.abc import Callable
from typing import Any, cast

from sqlalchemy import or_, select

from core import limits
from core.log import get_logger
from core.time import utcnow
from modules.knowledge import extract, fetch, runs, settings
from modules.knowledge.embedder import Embedder
from modules.knowledge.models import KnowledgeSource, KnowledgeVersion
from modules.knowledge.service import (
    JOBS_LIMIT,
    KEY_PATTERN,
    MAX_CHUNKS,
    KnowledgeError,
    _embed,
    _find,
    _source_dict,
    _text,
    _write_version,
    can_publish,
    check_passages,
    new_source,
)
from modules.organizations import service as organizations
from modules.organizations.models import Organization
from modules.submodules.models import SubmoduleSubscription

logger = get_logger("knowledge.crawl")

MAX_EVERY_HOURS = 24 * 30
QUALITY_FLOOR_RATIO = 0.5
QUALITY_FLOOR_MIN_CHARS = 500


def _setting(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        return default
    return value if value > 0 else default


def schedule(db, org_id: int, org_prefix: str, key: str, data: dict) -> dict:
    """Create or update a crawled source from untrusted input. Commits."""
    if not isinstance(key, str) or not KEY_PATTERN.match(key):
        raise KnowledgeError("key must be 1 to 255 letters, digits or ._:/- and start with a letter or digit")
    url = _text(data.get("url"), "url", 2000) or ""
    if not url.startswith(("https://", "http://")):
        raise KnowledgeError("url must start with http:// or https://")
    category = _text(data.get("category"), "category", 100)
    title = _text(data.get("title"), "title", 500, required=False)
    every = data.get("fetch_every_hours", 24)
    if not isinstance(every, int) or isinstance(every, bool) or not 1 <= every <= MAX_EVERY_HOURS:
        raise KnowledgeError(f"fetch_every_hours must be an integer from 1 to {MAX_EVERY_HOURS}")
    public, enabled = data.get("public", False), data.get("enabled", True)
    if not isinstance(public, bool) or not isinstance(enabled, bool):
        raise KnowledgeError("public and enabled must be true or false")
    if public and not can_publish(db, org_prefix):
        raise KnowledgeError("This organization may not write public sources", 403)

    source = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=key).first()
    if source is None:
        source = new_source(db, org_id, key=key, url=url, category=category)
    if source.url != url:
        source.last_attempt_at = None  # a new URL is due at once
    source.url, source.category, source.public, source.enabled = url, category, public, enabled
    source.title = title or source.title
    source.fetch_every_hours = every
    source.updated_at = utcnow()
    db.commit()
    return _source_dict(source, db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first())


def run(db, org_id: int, key: str, embedder: Embedder | None, force: bool = False) -> dict:
    """Crawl one source of the org now. Commits."""
    source = _find(db, org_id, key)
    if source.fetch_every_hours is None:
        raise KnowledgeError("This source is written by a client, not crawled", 409)
    return crawl(db, source, embedder, force=force)


def queue(db, org_id: int, org_prefix: str, key: str, force: bool = False) -> None:
    """Start the crawl job for one source of the org. The result shows on the source as last_attempt_at and last_error.

    It counts against the org's knowledge.jobs_per_day limit. Commits.
    """
    from core.jobs import defer

    source = _find(db, org_id, key)
    if source.fetch_every_hours is None:
        raise KnowledgeError("This source is written by a client, not crawled", 409)
    limits.consume(db, org_id, JOBS_LIMIT)
    defer("knowledge.crawl_source", org_id=org_id, key=key, force=force, org_prefix=org_prefix)
    db.commit()


def start_crawl_due() -> None:
    """Start the crawl of due sources now, unless a run is already queued or running."""
    from core.jobs import JobBusy, defer

    try:
        defer("knowledge.crawl_due")
    except JobBusy:
        logger.info("crawl of due sources already queued")


def queue_job(db, org_id: int, name: str, /, **kwargs) -> None:
    """Start knowledge.reindex or knowledge.crawl_due for the org, within its jobs_per_day limit. Commits."""
    from core.jobs import defer

    limits.consume(db, org_id, JOBS_LIMIT)
    defer(name, **kwargs)
    db.commit()


def _record(db, source: KnowledgeSource, started: runs.Timer, **outcome: Any) -> None:
    """Add a crawl run to the org's run log. A shared submodule's source has no org: its result stays on the source."""
    if source.organization_id is not None:
        runs.record(db, source.organization_id, str(source.key), "crawl", started, **outcome)


def crawl(db, source: KnowledgeSource, embedder: Embedder | None, *, force: bool = False, pacer: Any = None) -> dict:
    """Fetch, extract, chunk, embed and index one crawled source. Commits; records any error on the source."""
    started = runs.Timer()
    source.last_attempt_at = utcnow()
    db.commit()
    try:
        result = _crawl(db, source, embedder, force=force, pacer=pacer)
    except (fetch.FetchError, fetch.FetchRejected, KnowledgeError, limits.LimitError) as e:
        db.rollback()
        source.last_error = str(e.message if isinstance(e, KnowledgeError | limits.LimitError) else e)[:1000]
        _record(db, source, started, error=source.last_error)
        db.commit()
        logger.warning("crawl failed source=%s error=%s", source.key, source.last_error)
        return {"key": source.key, "changed": False, "error": source.last_error}
    source.last_error = None
    _record(db, source, started, changed=result["changed"], chunks=result["chunks"])
    db.commit()
    logger.info("crawled source=%s changed=%s chunks=%s", source.key, result["changed"], result["chunks"])
    return result


def _crawl(db, source: KnowledgeSource, embedder: Embedder | None, *, force: bool, pacer: Any) -> dict:
    url = str(source.url)
    if pacer is not None:
        pacer.wait(url)
    org_id = source.organization_id
    firecrawl = fetch.firecrawl_for(db, org_id) if org_id is not None else fetch.deployment_firecrawl()
    with fetch.firecrawl_scope(firecrawl):
        page = fetch.fetch(url)
    content_hash = hashlib.sha256(page.body).hexdigest()
    previous = db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first()
    if previous is not None and previous.content_hash == content_hash and not force:
        return {"key": source.key, "changed": False, "chunks": int(previous.chunk_count or 0)}

    custom = extract.extractor(source.extractor)
    if custom is not None:
        text = custom(page)
        title = page.title or (extract.title_of(page.body) if page.text is None else None)
    elif page.text is not None:
        text, title = page.text, page.title
    else:
        text, title = extract.extract_text(page.body), extract.title_of(page.body)
    return index_text(db, source, text, title, content_hash, embedder, previous=previous, force=force)


def index_text(
    db,
    source: KnowledgeSource,
    text: str,
    title: str | None,
    content_hash: str,
    embedder: Embedder | None,
    *,
    previous: KnowledgeVersion | None = None,
    force: bool = False,
) -> dict:
    """Chunk, embed and store text as the source's new version. Commits."""
    label: str = title or source.title or str(source.key)
    tuning = settings.for_org(db, source.organization_id)
    pieces = extract.chunk_text(text, max_chars=tuning["chunk_chars"], overlap_chars=tuning["chunk_overlap"])
    if not pieces:
        raise KnowledgeError("No text was extracted; the index is kept")
    if len(pieces) > MAX_CHUNKS:
        raise KnowledgeError(f"The text makes {len(pieces)} passages, more than {MAX_CHUNKS}; the index is kept")
    floor = previous.text_chars if previous is not None else None
    if not force and floor is not None and floor >= QUALITY_FLOOR_MIN_CHARS:
        if len(text) < int(floor * QUALITY_FLOOR_RATIO):
            raise KnowledgeError(
                f"Extracted {len(text)} characters against {floor} last time; the index is kept. Run with force to accept"
            )

    # Each chunk carries the page title
    rows: list[dict] = [
        {"ordinal": i, "level": 0, "parent_ordinal": None, "content": f"{label}\n{piece}", "embedding": None}
        for i, piece in enumerate(pieces)
    ]
    check_passages(db, source, len(rows))
    model = _embed(rows, embedder)
    source.title = label[:500]
    _write_version(db, source, rows, content_hash, model, text_chars=len(text))
    db.commit()
    return {"key": source.key, "changed": True, "chunks": len(rows)}


def due(
    db, now: datetime.datetime | None = None, limit: int = 20, skip: set[int] | None = None
) -> list[KnowledgeSource]:
    """Enabled crawled sources whose schedule has come round, never-tried ones first, of orgs not in skip.

    A shared submodule's sources are due only while an org subscribes to it. The batch takes one source of
    each org, and of each submodule, in turn, so one with many due sources does not fill it.
    """
    now = now or utcnow()
    query = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.fetch_every_hours.isnot(None), KnowledgeSource.enabled.is_(True))
        .filter(or_(KnowledgeSource.last_attempt_at.is_(None), KnowledgeSource.last_attempt_at < now))
        .filter(
            or_(
                KnowledgeSource.submodule_id.is_(None),
                KnowledgeSource.submodule_id.in_(select(SubmoduleSubscription.submodule_id)),
            )
        )
    )
    skip = {org_id for org_id in skip or () if org_id is not None}  # NOT IN with a NULL matches no row
    if skip:
        query = query.filter(
            or_(KnowledgeSource.organization_id.is_(None), KnowledgeSource.organization_id.notin_(skip))
        )
    candidates = query.order_by(
        KnowledgeSource.last_attempt_at.is_(None).desc(), KnowledgeSource.last_attempt_at, KnowledgeSource.id
    ).all()
    by_org: dict[tuple[str, int], list[KnowledgeSource]] = {}
    for s in candidates:
        if s.last_attempt_at is None or s.last_attempt_at + datetime.timedelta(hours=int(s.fetch_every_hours)) <= now:
            owner = ("org", s.organization_id) if s.organization_id is not None else ("submodule", s.submodule_id)
            by_org.setdefault(cast(tuple[str, int], owner), []).append(s)
    batch: list[KnowledgeSource] = []
    queues = list(by_org.values())
    while queues and len(batch) < limit:
        for queue in queues:
            if len(batch) < limit:
                batch.append(queue.pop(0))
        queues = [queue for queue in queues if queue]
    return batch


def crawl_due(db, embedder_for: Callable[[int | None], Embedder | None], now: datetime.datetime | None = None) -> dict:
    """Crawl every due source with its org's embedder, one host at a time per KNOWLEDGE_CRAWL_GAP_SECONDS. Commits.

    embedder_for(None) gives the embedder of a shared submodule's sources: the deployment's.
    """
    pacer = fetch.HostPacer(_setting("KNOWLEDGE_CRAWL_GAP_SECONDS", 2))
    results = []
    off = {
        cast(int, o.id)
        for o in db.query(Organization).all()
        if not o.is_active or not organizations.module_enabled(o, "knowledge")
    }
    for source in due(db, now, limit=_setting("KNOWLEDGE_CRAWL_BATCH", 20), skip=off):
        started = runs.Timer()
        try:
            results.append(crawl(db, source, embedder_for(source.organization_id), pacer=pacer))
        except Exception:
            # One broken source must not stop the rest of the batch
            db.rollback()
            logger.exception("crawl crashed source=%s", source.key)
            _record(db, source, started, error="The crawl crashed. The server log has the details")
            db.commit()
            results.append({"key": source.key, "error": "crashed"})
    return {
        "crawled": len(results),
        "changed": sum(1 for r in results if r.get("changed")),
        "failed": sum(1 for r in results if r.get("error")),
    }


def reindex(db, org_id: int, embedder: Embedder | None) -> dict:
    """Crawl every crawled source of the org with force, one host at a time. Commits."""
    pacer = fetch.HostPacer(_setting("KNOWLEDGE_CRAWL_GAP_SECONDS", 2))
    sources = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.organization_id == org_id, KnowledgeSource.fetch_every_hours.isnot(None))
        .order_by(KnowledgeSource.key)
        .all()
    )
    results = [crawl(db, source, embedder, force=True, pacer=pacer) for source in sources]
    return {"crawled": len(results), "failed": sum(1 for r in results if r.get("error"))}
