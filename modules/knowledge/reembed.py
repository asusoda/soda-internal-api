"""Vectors of stored passages: how many match the org's embedding model, and re-embedding the rest. No Flask here.

A passage keeps the text it was embedded from, so a new model or a first embedding service needs no new fetch.
Search compares only vectors of the org's current model; until a passage is embedded again, only text search finds it.
"""

from typing import cast

from sqlalchemy import func

from core import limits
from core.log import get_logger
from modules.knowledge.embedder import Embedder, EmbeddingError
from modules.knowledge.models import KnowledgeChunk, KnowledgeSource, KnowledgeVersion
from modules.knowledge.service import JOBS_LIMIT, KnowledgeError, _vector

logger = get_logger("knowledge.reembed")


def status(db, org_id: int, embedder: Embedder | None) -> dict:
    """Passages of the org's sources by embedding model, and how many do not match the current model."""
    rows = (
        db.query(KnowledgeVersion.embedding_model, func.coalesce(func.sum(KnowledgeVersion.chunk_count), 0))
        .join(KnowledgeSource, KnowledgeSource.current_version_id == KnowledgeVersion.id)
        .filter(KnowledgeSource.organization_id == org_id)
        .group_by(KnowledgeVersion.embedding_model)
        .all()
    )
    models = {str(model) if model else "": int(count) for model, count in rows}
    total = sum(models.values())
    current = embedder.model if embedder else None
    matching = models.get(current, 0) if current else 0
    return {
        "model": current,
        "passages": total,
        "embedded": matching,
        "stale": total - matching if current else 0,
        "models": [{"model": m or None, "passages": n} for m, n in sorted(models.items())],
    }


def _stale_versions(db, org_id: int, model: str) -> list[KnowledgeVersion]:
    return (
        db.query(KnowledgeVersion)
        .join(KnowledgeSource, KnowledgeSource.current_version_id == KnowledgeVersion.id)
        .filter(KnowledgeSource.organization_id == org_id)
        .filter((KnowledgeVersion.embedding_model.is_(None)) | (KnowledgeVersion.embedding_model != model))
        .order_by(KnowledgeSource.key)
        .all()
    )


def run(db, org_id: int, embedder: Embedder | None) -> dict:
    """Embed every passage of the org whose source is not on the current model. Commits once per source.

    A source that fails keeps its old vectors, and the run goes on with the next source.
    """
    if embedder is None:
        raise KnowledgeError("Set an embedding service first")
    done = failed = passages = 0
    for version in _stale_versions(db, org_id, embedder.model):
        chunks = db.query(KnowledgeChunk).filter_by(version_id=version.id).order_by(KnowledgeChunk.ordinal).all()
        try:
            vectors = embedder.embed([cast(str, c.content) for c in chunks]) if chunks else []
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk.embedding = _vector(vector, "embedding from the embedding service")
            version.embedding_model = embedder.model
            db.commit()
            done += 1
            passages += len(chunks)
        except (EmbeddingError, KnowledgeError, ValueError) as e:
            db.rollback()
            failed += 1
            logger.warning("re-embed failed org=%s version=%s: %s", org_id, version.id, e)
    return {"sources": done, "failed": failed, "passages": passages, "model": embedder.model}


def queue(db, org_id: int) -> dict:
    """Start the re-embed job for the org. Raises KnowledgeError without an embedding service."""
    from core.jobs import defer
    from modules.knowledge import embedder

    if embedder.for_org(db, org_id) is None:
        raise KnowledgeError("Set an embedding service first")
    limits.consume(db, org_id, JOBS_LIMIT)
    defer("knowledge.reembed", org_id=org_id)
    db.commit()
    return {"queued": True}
