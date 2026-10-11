"""make alerts a Core module; feeds post to an alert destination

Revision ID: c6e8a0b2d4f6
Revises: 58c6695dee24
Create Date: 2026-10-11 19:00:00.000000

The event_webhook module becomes alerts, which is always on. An org that had the switch off keeps no
deliveries: its webhooks are turned off. The limit key event_webhook.webhooks becomes alerts.destinations.
A feed gets destination_id, the alert destination it posts to.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c6e8a0b2d4f6"
down_revision: str | Sequence[str] | None = "58c6695dee24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
# Export Alembic metadata names so static analyzers treat them as intentionally used.
__all__ = ("revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade")

OLD = "event_webhook"
OLD_LIMIT, NEW_LIMIT = "event_webhook.webhooks", "alerts.destinations"

organizations = sa.table("organizations", sa.column("id", sa.Integer), sa.column("config", sa.JSON))
webhooks = sa.table("webhooks", sa.column("organization_id", sa.Integer), sa.column("enabled", sa.Boolean))
org_limits = sa.table("org_limits", sa.column("key", sa.String))


def upgrade() -> None:
    bind = op.get_bind()
    for org_id, config in bind.execute(sa.select(organizations.c.id, organizations.c.config)).all():
        config = dict(config or {})
        modules = dict(config.get("modules") or {})
        if OLD not in modules:
            continue
        if modules.pop(OLD) is False:
            bind.execute(webhooks.update().where(webhooks.c.organization_id == org_id).values(enabled=False))
        config["modules"] = modules
        bind.execute(organizations.update().where(organizations.c.id == org_id).values(config=config))
    bind.execute(org_limits.update().where(org_limits.c.key == OLD_LIMIT).values(key=NEW_LIMIT))
    with op.batch_alter_table("alert_feeds") as batch:
        batch.add_column(sa.Column("destination_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_alert_feeds_destination", "webhooks", ["destination_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("alert_feeds") as batch:
        batch.drop_constraint("fk_alert_feeds_destination", type_="foreignkey")
        batch.drop_column("destination_id")
    op.get_bind().execute(org_limits.update().where(org_limits.c.key == NEW_LIMIT).values(key=OLD_LIMIT))
