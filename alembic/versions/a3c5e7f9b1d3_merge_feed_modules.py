"""merge the job_webhook and hackathon_webhook switches into one feeds switch

Revision ID: a3c5e7f9b1d3
Revises: 657f276f6993
Create Date: 2026-10-11 15:00:00.000000

The feeds module now holds both kinds of feed. An org gets feeds on when it had either module on, so no feed
stops. An unset switch is on, so an org with neither switch keeps none.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3c5e7f9b1d3"
down_revision: str | Sequence[str] | None = "657f276f6993"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

OLD = ("job_webhook", "hackathon_webhook")
NEW = "feeds"

organizations = sa.table("organizations", sa.column("id", sa.Integer), sa.column("config", sa.JSON))


def _rows(bind):
    return bind.execute(sa.select(organizations.c.id, organizations.c.config)).all()


def _save(bind, org_id, config: dict, modules: dict) -> None:
    config["modules"] = modules
    bind.execute(organizations.update().where(organizations.c.id == org_id).values(config=config))


def upgrade() -> None:
    bind = op.get_bind()
    for org_id, config in _rows(bind):
        config = dict(config or {})
        modules = dict(config.get("modules") or {})
        if not any(name in modules for name in OLD):
            continue
        modules[NEW] = any(modules.get(name, True) is not False for name in OLD)
        for name in OLD:
            modules.pop(name, None)
        _save(bind, org_id, config, modules)


def downgrade() -> None:
    bind = op.get_bind()
    for org_id, config in _rows(bind):
        config = dict(config or {})
        modules = dict(config.get("modules") or {})
        if NEW not in modules:
            continue
        on = modules.pop(NEW) is not False
        for name in OLD:
            modules[name] = on
        _save(bind, org_id, config, modules)
