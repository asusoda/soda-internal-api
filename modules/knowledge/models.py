"""Sources, their versions, and the chunks search runs over.

On Postgres, chunk embeddings are pgvector columns with an HNSW index and the text has a full-text
GIN index (both created in the migration, named pg_*). On SQLite, embeddings are JSON text and
search runs in Python, which is enough for development and tests.
"""

import json
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, UserDefinedType

from core.db import Base, new_uuid
from core.time import utcnow

DIMENSIONS = 1024  # Qwen3-Embedding-0.6B


_PGVECTOR: dict[tuple[str, str], bool] = {}


def vector_sql(db, table: str) -> bool:
    """Whether the embedding column of table is pgvector, so nearest rows come from SQL."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    key = (str(bind.url), table)
    if key not in _PGVECTOR:
        row = db.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = 'embedding'"
            ),
            {"table": table},
        ).first()
        _PGVECTOR[key] = row is not None and row[0] == "USER-DEFINED"
    return _PGVECTOR[key]


class _PgVector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def get_col_spec(self, **kw) -> str:
        return f"vector({self.dimensions})"


class Embedding(TypeDecorator):
    """A float vector: pgvector on Postgres, JSON text elsewhere. Both use the [a,b,c] literal."""

    impl = Text
    cache_ok = True

    def __init__(self, dimensions: int = DIMENSIONS):
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PgVector(self.dimensions))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return "[" + ",".join(repr(float(x)) for x in value) + "]"

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return [float(x) for x in json.loads(value)]


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    # Null for a shared submodule's source, which submodule_id names instead
    organization_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True)
    submodule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("submodules.id", ondelete="CASCADE"), nullable=True, index=True
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)  # stable name the writer chooses
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # readable by every org
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Crawled sources: the platform fetches url on this schedule. None means a writer sends chunks.
    fetch_every_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # a name registered in modules/knowledge/extract.py
    extractor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_knowledge_source_key"),
        UniqueConstraint("submodule_id", "key", name="uq_knowledge_source_submodule_key"),
        CheckConstraint("organization_id IS NOT NULL OR submodule_id IS NOT NULL", name="ck_knowledge_source_owner"),
    )


class KnowledgeVersion(Base):
    __tablename__ = "knowledge_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)  # extracted text length, for crawled sources
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    # null: a shared submodule's
    organization_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True)
    submodule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("submodules.id", ondelete="CASCADE"), nullable=True
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_versions.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0 page text, 1+ summaries of rows below
    parent_ordinal: Mapped[int | None] = mapped_column(Integer, nullable=True)  # the summary row that covers this one
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Embedding(), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("version_id", "ordinal", name="uq_knowledge_chunk_ordinal"),
        Index("ix_knowledge_chunks_scope", "organization_id", "category", "level"),
        Index("ix_knowledge_chunks_public", "public", "category"),
        Index("ix_knowledge_chunks_submodule", "submodule_id", "category"),
    )


class KnowledgeRun(Base):
    """One crawl or upload of a source: whether the index changed, how many passages it holds, and any error."""

    __tablename__ = "knowledge_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # crawl or upload
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    changed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
