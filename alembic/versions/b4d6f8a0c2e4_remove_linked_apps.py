"""remove linked apps; their Uptime monitors check the URL

Revision ID: b4d6f8a0c2e4
Revises: a3c5e7f9b1d3
Create Date: 2026-10-11 18:00:00.000000

The Hosting page shows only the apps that Platform deploys. A monitor of a linked app becomes a url monitor of the
app's manifest url, so its checks and history stay. A linked app with no url has a monitor that has nothing to check,
so that monitor is deleted. Then the linked app rows are deleted. The downgrade does not make them again.
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b4d6f8a0c2e4"
down_revision: str | Sequence[str] | None = "a3c5e7f9b1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

apps = sa.table(
    "runpod_apps",
    sa.column("id", sa.String),
    sa.column("organization_id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("provider", sa.String),
    sa.column("manifest", sa.Text),
)
monitors = sa.table(
    "uptime_monitors",
    sa.column("id", sa.Integer),
    sa.column("organization_id", sa.Integer),
    sa.column("target_kind", sa.String),
    sa.column("target", sa.String),
)
checks = sa.table("uptime_checks", sa.column("monitor_id", sa.Integer))
deployments = sa.table("runpod_deployments", sa.column("app_id", sa.String))


def upgrade() -> None:
    bind = op.get_bind()
    linked = bind.execute(
        sa.select(apps.c.id, apps.c.organization_id, apps.c.name, apps.c.manifest).where(apps.c.provider == "linked")
    ).all()
    for app_id, org_id, name, manifest in linked:
        url = (json.loads(manifest or "{}") or {}).get("url")
        app_monitors = (
            (monitors.c.organization_id == org_id) & (monitors.c.target_kind == "app") & (monitors.c.target == name)
        )
        if url:
            bind.execute(monitors.update().where(app_monitors).values(target_kind="url", target=url))
        else:
            ids = [i for (i,) in bind.execute(sa.select(monitors.c.id).where(app_monitors)).all()]
            if ids:
                bind.execute(checks.delete().where(checks.c.monitor_id.in_(ids)))
                bind.execute(monitors.delete().where(monitors.c.id.in_(ids)))
        bind.execute(deployments.delete().where(deployments.c.app_id == app_id))
        bind.execute(apps.delete().where(apps.c.id == app_id))


def downgrade() -> None:
    pass
