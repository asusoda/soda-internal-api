"""The migration that makes alerts a Core module and renames its limit."""

import json
import sqlite3

from .test_module_rename_migration import _alembic, _config

BEFORE = "58c6695dee24"
AFTER = "c6e8a0b2d4f6"
NOW = "2026-10-11 00:00:00"


def test_switch_goes_and_an_org_that_had_it_off_keeps_no_deliveries(tmp_path):
    db_path = tmp_path / "orgs.db"
    _alembic(db_path, "upgrade", BEFORE)
    db = sqlite3.connect(db_path)
    orgs = [
        (1, "SoDA", "soda", "1", json.dumps({"modules": {"event_webhook": True, "points": True}})),
        (2, "AIS", "ais", "2", json.dumps({"modules": {"event_webhook": False}})),
        (3, "New", "new", "3", None),
    ]
    db.executemany(
        "INSERT INTO organizations (id, name, prefix, guild_id, is_active, config) VALUES (?, ?, ?, ?, 1, ?)", orgs
    )
    for hook_id, org_id in [(1, 1), (2, 2)]:
        db.execute(
            "INSERT INTO webhooks (id, organization_id, name, kind, url_ciphertext, url_hint, events, enabled,"
            " created_at) VALUES (?, ?, 'Ops', 'discord', 'x', '...', '[]', 1, ?)",
            (hook_id, org_id, NOW),
        )
    db.execute(
        "INSERT INTO org_limits (organization_id, key, value, updated_at) VALUES (1, 'event_webhook.webhooks', 5, ?)",
        (NOW,),
    )
    db.commit()
    db.close()

    _alembic(db_path, "upgrade", AFTER)
    db = sqlite3.connect(db_path)
    assert _config(db, 1)["modules"] == {"points": True}
    assert _config(db, 2)["modules"] == {}
    assert _config(db, 3) == {}
    assert db.execute("SELECT id, enabled FROM webhooks ORDER BY id").fetchall() == [(1, 1), (2, 0)]
    assert db.execute("SELECT key FROM org_limits").fetchall() == [("alerts.destinations",)]
    db.close()

    _alembic(db_path, "downgrade", BEFORE)
    db = sqlite3.connect(db_path)
    assert db.execute("SELECT key FROM org_limits").fetchall() == [("event_webhook.webhooks",)]
    db.close()
