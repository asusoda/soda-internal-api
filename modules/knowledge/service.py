"""Knowledge sources, their versions and chunks. No Flask here.

Writers (a scraper, an import script) send a source as chunks, or crawl.py fetches a crawled source.
A source is replaced whole: when its content hash changes, a new version and its chunks replace the
old ones. Only publishers may write public sources: orgs the superadmin marks as publishers, and
orgs listed in KNOWLEDGE_PUBLISHERS. search.py
searches the chunks.
"""

import hashlib
import math
import os
import re
from typing import Any, cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm.attributes import flag_modified

from core import limits
from core.errors import ServiceError
from core.time import iso, utcnow
from modules.auth import scopes
from modules.knowledge.embedder import Embedder, EmbeddingError
from modules.knowledge.models import DIMENSIONS, KnowledgeChunk, KnowledgeSource, KnowledgeVersion
from modules.organizations.models import Organization
from modules.submodules.models import SubmoduleSubscription

scopes.declare(
    "knowledge:read", "Search the organization's knowledge and public sources", uses=("embeddings", "searxng")
)
scopes.declare(
    "knowledge:write", "Write and delete the organization's knowledge sources", uses=("embeddings", "firecrawl")
)

MAX_CHUNKS = 5000
MAX_CHUNK_CHARS = 20000
MAX_LEVEL = 10
KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")


class KnowledgeError(ServiceError, ValueError):
    pass


def source_count(db, org_id: int) -> int:
    return db.query(KnowledgeSource).filter_by(organization_id=org_id).count()


def passage_count(db, org_id: int) -> int:
    """The passages of the current versions of the org's sources."""
    total = (
        db.query(func.coalesce(func.sum(KnowledgeVersion.chunk_count), 0))
        .join(KnowledgeSource, KnowledgeSource.current_version_id == KnowledgeVersion.id)
        .filter(KnowledgeSource.organization_id == org_id)
        .scalar()
    )
    return int(total or 0)


SOURCES_LIMIT = "knowledge.sources"
PASSAGES_LIMIT = "knowledge.passages"
UPLOADS_LIMIT = "knowledge.uploads_per_day"
JOBS_LIMIT = "knowledge.jobs_per_day"
limits.declare(SOURCES_LIMIT, "knowledge", "Sources", 1000, unit="sources", usage=source_count)
limits.declare(PASSAGES_LIMIT, "knowledge", "Passages", 250_000, unit="passages", usage=passage_count)
limits.declare(UPLOADS_LIMIT, "knowledge", "Files uploaded a day", 500, window="day", unit="files")
limits.declare(
    JOBS_LIMIT, "knowledge", "Crawls, re-indexes and re-embeds started by hand a day", 200, window="day", unit="jobs"
)


def check_passages(db, source: KnowledgeSource, count: int) -> None:
    """Raise LimitError when count passages in place of the source's current ones take the org over its limit."""
    if source.organization_id is None:
        return  # a shared submodule's source counts against no org
    old = db.query(KnowledgeVersion.chunk_count).filter_by(id=source.current_version_id).scalar()
    limits.check(db, cast(int, source.organization_id), PASSAGES_LIMIT, add=count - int(old or 0))


def new_source(db, org_id: int, **fields) -> KnowledgeSource:
    """Add a source to the session, within the org's source limit. Flushes."""
    limits.check(db, org_id, SOURCES_LIMIT)
    source = KnowledgeSource(organization_id=org_id, **fields)
    db.add(source)
    db.flush()
    return source


# Org config key for rights only the superadmin sets
ACCESS_KEY = "access"


def env_publishers() -> set[str]:
    """The org prefixes listed in KNOWLEDGE_PUBLISHERS."""
    return {p.strip() for p in os.environ.get("KNOWLEDGE_PUBLISHERS", "").split(",") if p.strip()}


def can_publish(db, org_prefix: str) -> bool:
    """Whether the org may write sources that every org can search."""
    if org_prefix in env_publishers():
        return True
    org = db.query(Organization).filter_by(prefix=org_prefix).first()
    return org is not None and bool(((cast(dict, org.config) or {}).get(ACCESS_KEY) or {}).get("knowledge_publisher"))


def publishers(db) -> list[dict]:
    """Every publisher: org id, prefix and where the right comes from (env or superadmin)."""
    listed = env_publishers()
    result = []
    for org in db.query(Organization).order_by(Organization.id).all():
        prefix = str(org.prefix)
        flagged = bool(((cast(dict, org.config) or {}).get(ACCESS_KEY) or {}).get("knowledge_publisher"))
        if prefix in listed or flagged:
            result.append({"org_id": org.id, "prefix": prefix, "source": "env" if prefix in listed else "superadmin"})
    return result


def set_publisher(db, org_id: int, on: object) -> list[dict]:
    """Mark or unmark the org as a publisher. Commits. Returns publishers()."""
    if not isinstance(on, bool):
        raise KnowledgeError("publisher must be true or false")
    org = db.query(Organization).filter_by(id=org_id).first()
    if org is None:
        raise KnowledgeError("No such organization", 404)
    config = dict(cast(dict, org.config) or {})
    access = {k: v for k, v in (config.get(ACCESS_KEY) or {}).items() if k != "knowledge_publisher"}
    config[ACCESS_KEY] = access | ({"knowledge_publisher": True} if on else {})
    org.config = config
    flag_modified(org, "config")
    db.commit()
    return publishers(db)


def _vector(value: Any, field: str) -> list[float]:
    if not isinstance(value, list) or len(value) != DIMENSIONS:
        raise KnowledgeError(f"{field} must be a list of {DIMENSIONS} numbers")
    try:
        vector = [float(x) for x in value]
    except (TypeError, ValueError):
        raise KnowledgeError(f"{field} must be a list of {DIMENSIONS} numbers") from None
    if not all(math.isfinite(x) for x in vector):
        raise KnowledgeError(f"{field} must hold finite numbers")
    return vector


def _text(value: Any, field: str, limit: int, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise KnowledgeError(f"{field} must be a non-empty string of at most {limit} characters")
    return value.strip()


def _source_dict(source: KnowledgeSource, version: KnowledgeVersion | None = None) -> dict:
    return {
        "id": source.id,
        "key": source.key,
        "url": source.url,
        "title": source.title,
        "category": source.category,
        "public": bool(source.public),
        "version_id": source.current_version_id,
        "content_hash": version.content_hash if version else None,
        "embedding_model": version.embedding_model if version else None,
        "chunk_count": version.chunk_count if version else 0,
        "fetched_at": iso(version.fetched_at) if version else None,
        "updated_at": iso(source.updated_at),
        "crawl": None
        if source.fetch_every_hours is None
        else {
            "fetch_every_hours": source.fetch_every_hours,
            "extractor": source.extractor,
            "enabled": bool(source.enabled),
            "last_attempt_at": iso(source.last_attempt_at),
            "last_error": source.last_error,
        },
    }


def _validate_chunks(chunks: Any) -> list[dict]:
    if not isinstance(chunks, list) or not chunks or len(chunks) > MAX_CHUNKS:
        raise KnowledgeError(f"chunks must be a list of 1 to {MAX_CHUNKS} items")
    rows: list[dict] = []
    ordinals: set[int] = set()
    for i, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise KnowledgeError(f"chunks[{i}] must be an object")
        ordinal = chunk.get("ordinal", i)
        level = chunk.get("level", 0)
        parent = chunk.get("parent_ordinal")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0 or ordinal in ordinals:
            raise KnowledgeError(f"chunks[{i}].ordinal must be a unique non-negative integer")
        if not isinstance(level, int) or isinstance(level, bool) or not 0 <= level <= MAX_LEVEL:
            raise KnowledgeError(f"chunks[{i}].level must be an integer from 0 to {MAX_LEVEL}")
        if parent is not None and (not isinstance(parent, int) or isinstance(parent, bool)):
            raise KnowledgeError(f"chunks[{i}].parent_ordinal must be an integer")
        ordinals.add(ordinal)
        embedding = chunk.get("embedding")
        rows.append(
            {
                "ordinal": ordinal,
                "level": level,
                "parent_ordinal": parent,
                "content": _text(chunk.get("content"), f"chunks[{i}].content", MAX_CHUNK_CHARS),
                "embedding": None if embedding is None else _vector(embedding, f"chunks[{i}].embedding"),
            }
        )
    for i, row in enumerate(rows):
        if row["parent_ordinal"] is not None and row["parent_ordinal"] not in ordinals:
            raise KnowledgeError(f"chunks[{i}].parent_ordinal names no chunk")
    with_vectors = sum(row["embedding"] is not None for row in rows)
    if with_vectors not in (0, len(rows)):
        raise KnowledgeError("Either every chunk has an embedding or none does")
    return rows


def _content_hash(rows: list[dict]) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda r: r["ordinal"]):
        digest.update(f"{row['ordinal']}:{row['level']}:{row['parent_ordinal']}:".encode())
        digest.update(row["content"].encode())
        digest.update(b"\0")
    return digest.hexdigest()


def _drop_versions(db, source_id: Any, keep: Any = None) -> None:
    """Delete a source's versions and their chunks, except `keep`. Explicit, since SQLite may not cascade."""
    versions = db.query(KnowledgeVersion.id).filter(KnowledgeVersion.source_id == source_id)
    if keep is not None:
        versions = versions.filter(KnowledgeVersion.id != keep)
    ids = [row[0] for row in versions.all()]
    if ids:
        db.query(KnowledgeChunk).filter(KnowledgeChunk.version_id.in_(ids)).delete(synchronize_session=False)
        db.query(KnowledgeVersion).filter(KnowledgeVersion.id.in_(ids)).delete(synchronize_session=False)


def put_source(db, org_id: int, org_prefix: str, key: str, data: dict, embedder: Embedder | None) -> dict:
    """Create or replace a source from untrusted input. Commits. Returns the source and whether it changed."""
    if not isinstance(key, str) or not KEY_PATTERN.match(key):
        raise KnowledgeError("key must be 1 to 255 letters, digits or ._:/- and start with a letter or digit")
    category = _text(data.get("category"), "category", 100)
    title = _text(data.get("title"), "title", 500, required=False)
    url = _text(data.get("url"), "url", 2000, required=False)
    public = data.get("public", False)
    if not isinstance(public, bool):
        raise KnowledgeError("public must be true or false")
    if public and not can_publish(db, org_prefix):
        raise KnowledgeError("This organization may not write public sources", 403)
    rows = _validate_chunks(data.get("chunks"))
    content_hash = data.get("content_hash")
    if content_hash is None:
        content_hash = _content_hash(rows)
    elif not isinstance(content_hash, str) or not 0 < len(content_hash) <= 64:
        raise KnowledgeError("content_hash must be a string of at most 64 characters")

    source = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=key).first()
    if source is None:
        source = new_source(db, org_id, key=key, category=category)
    current = db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first()
    source.title, source.url, source.category, source.public = title, url, category, public
    source.updated_at = utcnow()

    if current is not None and current.content_hash == content_hash:
        db.query(KnowledgeChunk).filter_by(version_id=current.id).update(
            {"category": category, "public": public}, synchronize_session=False
        )
        db.commit()
        return {"source": _source_dict(source, current), "changed": False}

    check_passages(db, source, len(rows))
    model = None
    if rows[0]["embedding"] is not None:
        model = _text(data.get("embedding_model"), "embedding_model", 200)
    else:
        model = _embed(rows, embedder)
    version = _write_version(db, source, rows, content_hash, model)
    db.commit()
    return {"source": _source_dict(source, version), "changed": True}


def _embed(rows: list[dict], embedder: Embedder | None) -> str | None:
    """Fill each row's embedding from the embedder. Returns the model name, or None without one."""
    if embedder is None:
        return None
    try:
        vectors = embedder.embed([row["content"] for row in rows])
    except EmbeddingError as e:
        raise KnowledgeError(str(e), 502) from e
    for row, vector in zip(rows, vectors, strict=True):
        row["embedding"] = _vector(vector, "embedding from the embedding service")
    return embedder.model


def _write_version(
    db, source: KnowledgeSource, rows: list[dict], content_hash: str, model: str | None, text_chars: int | None = None
) -> KnowledgeVersion:
    """Store rows as the source's new current version and drop the old ones. Flushes, does not commit.

    Raises LimitError when the new version would take the org over its passage limit.
    """
    check_passages(db, source, len(rows))
    version = KnowledgeVersion(
        source_id=source.id,
        content_hash=content_hash,
        embedding_model=model,
        chunk_count=len(rows),
        text_chars=text_chars,
    )
    db.add(version)
    db.flush()
    db.add_all(
        KnowledgeChunk(
            organization_id=source.organization_id,
            submodule_id=source.submodule_id,
            source_id=source.id,
            version_id=version.id,
            category=source.category,
            public=source.public,
            fetched_at=version.fetched_at,
            **row,
        )
        for row in rows
    )
    source.current_version_id = version.id
    db.flush()
    _drop_versions(db, source.id, keep=version.id)
    return version


def _find(db, org_id: int, key: str) -> KnowledgeSource:
    source = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=key).first()
    if source is None:
        raise KnowledgeError("No source with this key", 404)
    return source


def get_source(db, org_id: int, key: str) -> dict:
    source = _find(db, org_id, key)
    return _source_dict(source, db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first())


def list_sources(db, org_id: int, category: str | None = None) -> list[dict]:
    query = db.query(KnowledgeSource, KnowledgeVersion).outerjoin(
        KnowledgeVersion, KnowledgeVersion.id == KnowledgeSource.current_version_id
    )
    query = query.filter(KnowledgeSource.organization_id == org_id)
    if category:
        query = query.filter(KnowledgeSource.category == category)
    return [_source_dict(s, v) for s, v in query.order_by(KnowledgeSource.key).all()]


def delete_source(db, org_id: int, key: str) -> None:
    source = _find(db, org_id, key)
    _drop_versions(db, source.id)
    db.delete(source)
    db.commit()


# Reading a source in full

PAGE_CHARS = 200_000
PAGE_PASSAGES = 500
MIN_OVERLAP = 40


def _readable(db, org_id: int, key: str, chunk_id: str | None) -> KnowledgeSource:
    """The source the org may read: the one that holds chunk_id, else its own source, else one of a submodule it
    subscribes to, else the oldest public one."""
    subscribed = select(SubmoduleSubscription.submodule_id).where(SubmoduleSubscription.organization_id == org_id)
    visible = or_(
        KnowledgeSource.organization_id == org_id,
        KnowledgeSource.public.is_(True),
        KnowledgeSource.submodule_id.in_(subscribed),
    )
    if chunk_id:
        held = (
            db.query(KnowledgeSource)
            .join(KnowledgeChunk, KnowledgeChunk.source_id == KnowledgeSource.id)
            .filter(KnowledgeChunk.id == chunk_id, KnowledgeSource.key == key, visible)
            .first()
        )
        if held is not None:
            return held
    own = db.query(KnowledgeSource).filter_by(organization_id=org_id, key=key).first()
    if own is not None:
        return own
    shared = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.key == key, KnowledgeSource.submodule_id.in_(subscribed))
        .order_by(KnowledgeSource.submodule_id)
        .first()
    )
    if shared is not None:
        return shared
    public = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.key == key, KnowledgeSource.public.is_(True))
        .order_by(KnowledgeSource.created_at, KnowledgeSource.id)
        .first()
    )
    if public is None:
        raise KnowledgeError("No source with this key", 404)
    return public


def _focus(db, version_id: Any, chunk_id: str | None) -> list[str]:
    """The ids of the page text rows that chunk_id covers: itself, or the rows below a summary."""
    if not chunk_id:
        return []
    chunk = db.query(KnowledgeChunk).filter_by(id=chunk_id, version_id=version_id).first()
    if chunk is None:
        return []
    if chunk.level == 0:
        return [str(chunk.id)]
    found: list[str] = []
    frontier = {chunk.ordinal}
    for _ in range(MAX_LEVEL):
        if not frontier:
            break
        rows = (
            db.query(KnowledgeChunk.id, KnowledgeChunk.ordinal, KnowledgeChunk.level)
            .filter(KnowledgeChunk.version_id == version_id, KnowledgeChunk.parent_ordinal.in_(frontier))
            .all()
        )
        found.extend(str(row.id) for row in rows if row.level == 0)
        frontier = {row.ordinal for row in rows if row.level > 0}
    return found


def strip_overlap(previous: str, current: str) -> str:
    """current without the lines it repeats from the end of previous. The chunker repeats them as overlap."""
    probe = current[:MIN_OVERLAP]
    if len(probe) == MIN_OVERLAP:
        start = previous.find(probe)
        while start != -1:
            if current.startswith(previous[start:]):
                return current[len(previous) - start :].lstrip("\n")
            start = previous.find(probe, start + 1)
    for size in range(min(MIN_OVERLAP, len(previous), len(current)), 0, -1):
        if current[size : size + 1] == "\n" and previous.endswith(current[:size]):
            return current[size:].lstrip("\n")
    return current


def read_source(db, org_id: int, key: str, *, chunk_id: Any = None, offset: Any = None) -> dict:
    """One page of a source's full text: its page text rows in order, with the repeated overlap removed.

    The org reads its own sources and public ones. chunk_id picks the source that holds that chunk and marks the
    rows it covers as focus. Without an offset, the page starts at the focus.
    """
    if chunk_id is not None and (not isinstance(chunk_id, str) or len(chunk_id) > 36):
        raise KnowledgeError("chunk must be a chunk id")
    if offset is not None and (not isinstance(offset, int) or isinstance(offset, bool) or offset < 0):
        raise KnowledgeError("offset must be a non-negative integer")
    source = _readable(db, org_id, key, chunk_id)
    version = db.query(KnowledgeVersion).filter_by(id=source.current_version_id).first()
    own = source.organization_id == org_id
    body = _source_dict(source, version) | {"own": own, "text_chars": version.text_chars if version else None}
    if not own:
        body["crawl"] = None
    empty = {"source": body, "passages": [], "focus": [], "offset": 0, "next_offset": None, "total": 0}
    if version is None:
        return empty

    rows = (
        db.query(KnowledgeChunk.id, func.length(KnowledgeChunk.content))
        .filter(KnowledgeChunk.version_id == version.id, KnowledgeChunk.level == 0)
        .order_by(KnowledgeChunk.ordinal)
        .all()
    )
    ids = [str(row[0]) for row in rows]
    sizes = [int(row[1] or 0) for row in rows]
    focus = _focus(db, version.id, chunk_id)

    def page(start: int) -> int:
        end, chars = start, 0
        while end < len(ids) and end - start < PAGE_PASSAGES and (end == start or chars + sizes[end] <= PAGE_CHARS):
            chars += sizes[end]
            end += 1
        return end

    if offset is None:
        offset = 0
        first = min((ids.index(i) for i in focus if i in ids), default=0)
        if first >= page(0):
            offset = max(0, first - 2)
    offset = min(offset, len(ids))
    end = page(offset)
    stored = {
        str(row.id): (row.ordinal, row.content)
        for row in db.query(KnowledgeChunk.id, KnowledgeChunk.ordinal, KnowledgeChunk.content)
        .filter(KnowledgeChunk.id.in_(ids[max(0, offset - 1) : end]))
        .all()
    }
    passages = []
    previous = stored[ids[offset - 1]][1] if offset > 0 else None
    for chunk in ids[offset:end]:
        ordinal, text = stored[chunk]
        passages.append({"id": chunk, "ordinal": ordinal, "text": strip_overlap(previous, text) if previous else text})
        previous = text
    return empty | {
        "passages": passages,
        "focus": focus,
        "offset": offset,
        "next_offset": end if end < len(ids) else None,
        "total": len(ids),
    }
