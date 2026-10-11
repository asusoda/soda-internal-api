"""Hybrid search over knowledge chunks. No Flask here.

Search fuses a vector leg and a text leg with reciprocal rank fusion over the caller's organization
plus public sources. On Postgres with pgvector, both legs run in SQL. Elsewhere, including Postgres
without pgvector, the vector leg runs in Python over the stored vectors, and on SQLite so does the
text leg.
"""

import math
import re
from typing import Any

from sqlalchemy import or_, text

from core import limits
from core.log import get_logger
from core.time import iso
from modules.knowledge import settings
from modules.knowledge.embedder import Embedder, EmbeddingError
from modules.knowledge.models import Embedding, KnowledgeChunk, KnowledgeSource, KnowledgeVersion, vector_sql
from modules.knowledge.service import KnowledgeError, _text, _vector

logger = get_logger("knowledge")

MAX_TOP_K = 50
MAX_WINDOW = 5
CANDIDATES = 50
TEXT_CONFIG = "english"


def _dialect(db) -> str:
    return db.get_bind().dialect.name


def _scope(query, org_id: int, category: str | None):
    query = query.filter(or_(KnowledgeChunk.organization_id == org_id, KnowledgeChunk.public.is_(True)))
    return query.filter(KnowledgeChunk.category == category) if category else query


def _dense_sql(db, org_id: int, category: str | None, vector: list[float], model: str, limit: float) -> list[str]:
    params: dict[str, Any] = {
        "org": org_id,
        "vec": Embedding().process_bind_param(vector, None),
        "model": model,
        "n": CANDIDATES,
        "max": limit,
    }
    where = "(c.organization_id = :org OR c.public) AND c.embedding IS NOT NULL AND v.embedding_model = :model"
    if category:
        where += " AND c.category = :category"
        params["category"] = category
    sql = (
        "SELECT id FROM ("  # nosec B608 - only fixed fragments are formatted
        " SELECT c.id, c.embedding <=> CAST(:vec AS vector) AS distance"
        " FROM knowledge_chunks c JOIN knowledge_versions v ON v.id = c.version_id"
        f" WHERE {where} ORDER BY distance LIMIT :n"
        ") nearest WHERE distance <= :max"
    )
    return [row[0] for row in db.execute(text(sql), params)]


def _dense_python(db, org_id: int, category: str | None, vector: list[float], model: str, limit: float) -> list[str]:
    query = db.query(KnowledgeChunk.id, KnowledgeChunk.embedding).join(
        KnowledgeVersion, KnowledgeVersion.id == KnowledgeChunk.version_id
    )
    query = _scope(query, org_id, category).filter(
        KnowledgeVersion.embedding_model == model, KnowledgeChunk.embedding.isnot(None)
    )
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    scored = []
    for chunk_id, embedding in query.all():
        other = math.sqrt(sum(x * x for x in embedding)) or 1.0
        distance = 1.0 - sum(a * b for a, b in zip(vector, embedding, strict=False)) / (norm * other)
        if distance <= limit:
            scored.append((distance, chunk_id))
    scored.sort()
    return [chunk_id for _, chunk_id in scored[:CANDIDATES]]


def _lexical_sql(db, org_id: int, category: str | None, query_text: str) -> list[str]:
    params: dict[str, Any] = {"org": org_id, "q": query_text, "n": CANDIDATES}
    where = "(c.organization_id = :org OR c.public)"
    if category:
        where += " AND c.category = :category"
        params["category"] = category
    tsv = f"to_tsvector('{TEXT_CONFIG}', c.content)"
    tsq = f"websearch_to_tsquery('{TEXT_CONFIG}', :q)"
    sql = (
        f"SELECT c.id FROM knowledge_chunks c WHERE {where} AND {tsv} @@ {tsq}"  # nosec B608 - fixed fragments
        f" ORDER BY ts_rank_cd({tsv}, {tsq}) DESC LIMIT :n"
    )
    return [row[0] for row in db.execute(text(sql), params)]


def _terms(value: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", value.lower()) if len(t) > 1}


def _lexical_python(db, org_id: int, category: str | None, query_text: str) -> list[str]:
    terms = _terms(query_text)
    if not terms:
        return []
    query = _scope(db.query(KnowledgeChunk.id, KnowledgeChunk.content), org_id, category)
    scored = []
    for chunk_id, content in query.all():
        score = len(terms & _terms(content))
        if score:
            scored.append((-score, chunk_id))
    scored.sort()
    return [chunk_id for _, chunk_id in scored[:CANDIDATES]]


def rrf(lists: list[list[str]], k: float = 60.0) -> list[tuple[str, float]]:
    """Reciprocal rank fusion. Each ranked list contributes 1 / (k + rank)."""
    scores: dict[str, float] = {}
    for ranked in lists:
        for rank, item in enumerate(ranked):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


def _int(value: Any, field: str, default: int, low: int, high: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise KnowledgeError(f"{field} must be an integer from {low} to {high}")
    return value


def search(
    db,
    org_id: int,
    query: Any,
    *,
    category: Any = None,
    top_k: Any = None,
    window: Any = None,
    embedding: Any = None,
    embedding_model: Any = None,
    embedder: Embedder | None = None,
) -> dict:
    """Ranked passages for a query from the org's sources and public ones. Arguments come from callers.

    The org's knowledge settings give the mode, the defaults of top_k and window, the distance limit and
    the fusion constant.
    """
    tuning = settings.for_org(db, org_id)
    query_text = _text(query, "query", 1000) or ""
    category = _text(category, "category", 100, required=False)
    top_k = _int(top_k, "top_k", tuning["top_k"], 1, MAX_TOP_K)
    window = _int(window, "window", tuning["window"], 0, MAX_WINDOW)

    vector, model = None, None
    if embedding is not None:
        vector = _vector(embedding, "embedding")
        model = _text(embedding_model, "embedding_model", 200)
    elif embedder is not None and tuning["mode"] != "text":
        try:
            vector, model = _vector(embedder.embed_query(query_text), "query embedding"), embedder.model
            db.commit()  # keeps the count of the embedded query
        except (EmbeddingError, KnowledgeError, limits.LimitError):
            logger.warning("query embedding failed or is over the org's limit, searching on text only")

    # Mode text drops the vector leg. Mode vector drops the text leg when a vector is at hand.
    if tuning["mode"] == "text":
        vector = None
    legs: list[list[str]] = []
    if vector is not None and model is not None:
        dense = _dense_sql if vector_sql(db, "knowledge_chunks") else _dense_python
        legs.append(dense(db, org_id, category, vector, model, tuning["max_distance"]))
    if not legs or tuning["mode"] != "vector":
        lexical = _lexical_sql if _dialect(db) == "postgresql" else _lexical_python
        legs.append(lexical(db, org_id, category, query_text))

    fused = rrf(legs, float(tuning["rrf_k"]))
    if not fused:
        return {"results": [], "dense": vector is not None}
    rows = {
        chunk.id: (chunk, source)
        for chunk, source in db.query(KnowledgeChunk, KnowledgeSource)
        .join(KnowledgeSource, KnowledgeSource.id == KnowledgeChunk.source_id)
        .filter(KnowledgeChunk.id.in_([chunk_id for chunk_id, _ in fused]))
        .all()
    }

    # A row whose summary already ranked higher adds nothing.
    seen: set[tuple[str, int]] = set()
    ordered = []
    for chunk_id, score in fused:
        if chunk_id not in rows:
            continue
        chunk, source = rows[chunk_id]
        if chunk.parent_ordinal is not None and (chunk.version_id, chunk.parent_ordinal) in seen:
            continue
        seen.add((chunk.version_id, chunk.ordinal))
        ordered.append((chunk, source, score))
        if len(ordered) == top_k:
            break

    return {"results": _widen(db, ordered, window), "dense": vector is not None}


def _widen(db, ordered: list, window: int) -> list[dict]:
    """Each hit as evidence; page text hits carry `window` neighbors on each side, without repeats."""
    covered: dict[str, list[tuple[int, int]]] = {}
    results = []
    for chunk, source, score in ordered:
        content = chunk.content
        if window and chunk.level == 0:
            spans = covered.setdefault(chunk.version_id, [])
            if any(lo <= chunk.ordinal <= hi for lo, hi in spans):
                continue
            lo, hi = chunk.ordinal - window, chunk.ordinal + window
            spans.append((lo, hi))
            neighbors = (
                db.query(KnowledgeChunk.content)
                .filter(
                    KnowledgeChunk.version_id == chunk.version_id,
                    KnowledgeChunk.level == 0,
                    KnowledgeChunk.ordinal.between(lo, hi),
                )
                .order_by(KnowledgeChunk.ordinal)
                .all()
            )
            content = "\n".join(row[0] for row in neighbors) or content
        results.append(
            {
                "chunk_id": chunk.id,
                "source_key": source.key,
                "title": source.title,
                "url": source.url,
                "category": chunk.category,
                "public": bool(chunk.public),
                "content": content,
                "score": round(score, 6),
                "fetched_at": iso(chunk.fetched_at),
            }
        )
    return results
