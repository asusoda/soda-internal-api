import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from alembic import context
from core.db import Base
from modules.manifest import load_models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_models()

target_metadata = Base.metadata

# DATABASE_URL from the environment (Doppler) overrides sqlalchemy.url in alembic.ini
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


def _ensure_sqlite_parent_dir_exists() -> None:
    """Create the parent directory for SQLite databases before connecting."""
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        return

    try:
        parsed_url = make_url(url)
    except Exception:
        return

    if parsed_url.get_backend_name() != "sqlite":
        return

    database = parsed_url.database
    if not database or database == ":memory:":
        return

    db_path = database if os.path.isabs(database) else os.path.abspath(database)
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


# Postgres-only indexes created in migrations with raw SQL (pgvector HNSW, full-text GIN).
UNMODELED_INDEXES = {
    "ix_knowledge_chunks_embedding_hnsw",
    "ix_knowledge_chunks_content_fts",
    "ix_agent_profile_nodes_embedding_hnsw",
}


def include_object(obj, name, type_, reflected, compare_to):
    """Procrastinate's tables come from its own schema SQL, not from our models."""
    if type_ == "index" and reflected and compare_to is None and name in UNMODELED_INDEXES:
        return False
    return not (type_ == "table" and reflected and compare_to is None and name.startswith("procrastinate_"))


def run_migrations_offline() -> None:
    """Write the migration SQL for the configured URL without connecting."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run the migrations on a connection to the configured database."""
    _ensure_sqlite_parent_dir_exists()

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
