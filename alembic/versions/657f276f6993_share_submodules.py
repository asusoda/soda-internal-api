"""share submodules: submodules and submodule_subscriptions, and shared knowledge sources with no org

Revision ID: 657f276f6993
Revises: 055016fe0645
Create Date: 2026-10-11 14:02:57.130230

Each org that synced a submodule had its own copy of its pages. This keeps one copy as the submodule's shared
sources, subscribes every org that had a copy, and deletes the other copies. Live results (<name>-live/) stay
with their org. An org with a feed from a submodule's presets is subscribed to that submodule too, because feed
presets now come only from the submodules an org subscribes to.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "657f276f6993"
down_revision: str | Sequence[str] | None = "055016fe0645"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

# The submodules in submodules/ when this migration was written, with the keys of their feed presets
SUBMODULES = {"asu": (), "careers": ("internships", "new-grad", "hackathons")}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _drop_sources(bind, ids: list) -> None:
    """Delete sources with their chunks and versions. SQLite does not run ON DELETE CASCADE here."""
    for start in range(0, len(ids), 500):
        part = {"ids": ids[start : start + 500]}
        expand = sa.bindparam("ids", expanding=True)
        bind.execute(sa.text("DELETE FROM knowledge_chunks WHERE source_id IN :ids").bindparams(expand), part)
        bind.execute(sa.text("DELETE FROM knowledge_versions WHERE source_id IN :ids").bindparams(expand), part)
        bind.execute(sa.text("DELETE FROM knowledge_sources WHERE id IN :ids").bindparams(expand), part)


def _subscribe(bind, name: str, org_ids: list) -> int:
    """Make the submodule's row if needed and subscribe the orgs. Returns the row id."""
    now = _now()
    submodule_id = bind.execute(sa.text("SELECT id FROM submodules WHERE key = :k"), {"k": name}).scalar()
    if submodule_id is None:
        bind.execute(
            sa.text(
                "INSERT INTO submodules (key, title, origin, status, created_at, updated_at)"
                " VALUES (:k, :k, 'code', 'shared', :now, :now)"
            ),
            {"k": name, "now": now},
        )
        submodule_id = bind.execute(sa.text("SELECT id FROM submodules WHERE key = :k"), {"k": name}).scalar()
    have = {
        r[0]
        for r in bind.execute(
            sa.text("SELECT organization_id FROM submodule_subscriptions WHERE submodule_id = :s"), {"s": submodule_id}
        )
    }
    for org_id in org_ids:
        if org_id not in have:
            have.add(org_id)
            bind.execute(
                sa.text(
                    "INSERT INTO submodule_subscriptions (organization_id, submodule_id, created_by, created_at)"
                    " VALUES (:o, :s, 'migration', :now)"
                ),
                {"o": org_id, "s": submodule_id, "now": now},
            )
    return int(submodule_id)


def _share_copies(bind) -> None:
    for name, feed_keys in SUBMODULES.items():
        if feed_keys:
            users = bind.execute(
                sa.text("SELECT DISTINCT organization_id FROM alert_feeds WHERE key IN :keys").bindparams(
                    sa.bindparam("keys", expanding=True)
                ),
                {"keys": list(feed_keys)},
            ).all()
            if users:
                _subscribe(bind, name, [r[0] for r in users])
        pattern = f"{name}/%"
        orgs = bind.execute(
            sa.text(
                "SELECT organization_id, count(current_version_id) AS versions FROM knowledge_sources"
                " WHERE key LIKE :p AND organization_id IS NOT NULL GROUP BY organization_id"
                " ORDER BY versions DESC, organization_id"
            ),
            {"p": pattern},
        ).all()
        if not orgs:
            continue
        submodule_id = _subscribe(bind, name, [r[0] for r in orgs])
        keeper = orgs[0][0]
        kept = [
            r[0]
            for r in bind.execute(
                sa.text("SELECT id FROM knowledge_sources WHERE key LIKE :p AND organization_id = :o"),
                {"p": pattern, "o": keeper},
            )
        ]
        for start in range(0, len(kept), 500):
            part = {"ids": kept[start : start + 500], "s": submodule_id}
            expand = sa.bindparam("ids", expanding=True)
            for table, column in (("knowledge_sources", "id"), ("knowledge_chunks", "source_id")):
                bind.execute(
                    sa.text(
                        f"UPDATE {table} SET organization_id = NULL, submodule_id = :s, public = :f"  # nosec B608 - fixed names
                        f" WHERE {column} IN :ids"
                    ).bindparams(expand, sa.bindparam("f", False)),
                    part,
                )
        others = [
            r[0]
            for r in bind.execute(
                sa.text("SELECT id FROM knowledge_sources WHERE key LIKE :p AND organization_id IS NOT NULL"),
                {"p": pattern},
            )
        ]
        _drop_sources(bind, others)


def upgrade() -> None:
    op.create_table(
        "submodules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=True),
        sa.Column("owner_org_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_org_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_table(
        "submodule_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("submodule_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submodule_id"], ["submodules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "submodule_id", name="uq_submodule_subscription"),
    )
    with op.batch_alter_table("submodule_subscriptions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_submodule_subscriptions_organization_id"), ["organization_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_submodule_subscriptions_submodule_id"), ["submodule_id"], unique=False)

    with op.batch_alter_table("knowledge_chunks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("submodule_id", sa.Integer(), nullable=True))
        batch_op.alter_column("organization_id", existing_type=sa.INTEGER(), nullable=True)
        batch_op.create_index("ix_knowledge_chunks_submodule", ["submodule_id", "category"], unique=False)
        batch_op.create_foreign_key(
            "fk_knowledge_chunks_submodule_id", "submodules", ["submodule_id"], ["id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("knowledge_sources", schema=None) as batch_op:
        batch_op.add_column(sa.Column("submodule_id", sa.Integer(), nullable=True))
        batch_op.alter_column("organization_id", existing_type=sa.INTEGER(), nullable=True)
        batch_op.create_index(batch_op.f("ix_knowledge_sources_submodule_id"), ["submodule_id"], unique=False)
        batch_op.create_unique_constraint("uq_knowledge_source_submodule_key", ["submodule_id", "key"])
        batch_op.create_foreign_key(
            "fk_knowledge_sources_submodule_id", "submodules", ["submodule_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_check_constraint(
            "ck_knowledge_source_owner", "organization_id IS NOT NULL OR submodule_id IS NOT NULL"
        )

    _share_copies(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    # Each shared submodule's sources go back to its first subscriber; with no subscriber they are deleted
    for submodule_id, org_id in bind.execute(
        sa.text(
            "SELECT s.id, (SELECT min(organization_id) FROM submodule_subscriptions WHERE submodule_id = s.id)"
            " FROM submodules s"
        )
    ).all():
        if org_id is None:
            ids = [
                r[0]
                for r in bind.execute(
                    sa.text("SELECT id FROM knowledge_sources WHERE submodule_id = :s"), {"s": submodule_id}
                )
            ]
            _drop_sources(bind, ids)
            continue
        for table in ("knowledge_sources", "knowledge_chunks"):
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET organization_id = :o, submodule_id = NULL"  # nosec B608 - fixed names
                    " WHERE submodule_id = :s"
                ),
                {"o": org_id, "s": submodule_id},
            )

    with op.batch_alter_table("knowledge_sources", schema=None) as batch_op:
        batch_op.drop_constraint("ck_knowledge_source_owner", type_="check")
        batch_op.drop_constraint("fk_knowledge_sources_submodule_id", type_="foreignkey")
        batch_op.drop_constraint("uq_knowledge_source_submodule_key", type_="unique")
        batch_op.drop_index(batch_op.f("ix_knowledge_sources_submodule_id"))
        batch_op.alter_column("organization_id", existing_type=sa.INTEGER(), nullable=False)
        batch_op.drop_column("submodule_id")

    with op.batch_alter_table("knowledge_chunks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_knowledge_chunks_submodule_id", type_="foreignkey")
        batch_op.drop_index("ix_knowledge_chunks_submodule")
        batch_op.alter_column("organization_id", existing_type=sa.INTEGER(), nullable=False)
        batch_op.drop_column("submodule_id")

    with op.batch_alter_table("submodule_subscriptions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_submodule_subscriptions_submodule_id"))
        batch_op.drop_index(batch_op.f("ix_submodule_subscriptions_organization_id"))

    op.drop_table("submodule_subscriptions")
    op.drop_table("submodules")
