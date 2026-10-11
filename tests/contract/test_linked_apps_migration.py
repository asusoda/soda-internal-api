"""The migration that removes linked apps and turns their Uptime monitors into url monitors."""

import json
import sqlite3

from .test_module_rename_migration import _alembic

BEFORE = "a3c5e7f9b1d3"
AFTER = "b4d6f8a0c2e4"
NOW = "2026-10-11 00:00:00"


def _app(db, app_id, name, provider, manifest):
    db.execute(
        "INSERT INTO runpod_apps (id, organization_id, name, manifest, provider, created_at, updated_at)"
        " VALUES (?, 1, ?, ?, ?, ?, ?)",
        (app_id, name, json.dumps(manifest), provider, NOW, NOW),
    )


def _monitor(db, monitor_id, name, kind, target):
    db.execute(
        "INSERT INTO uptime_monitors (id, organization_id, name, target_kind, target, expected_status,"
        " timeout_seconds, interval_minutes, enabled, created_at, updated_at)"
        " VALUES (?, 1, ?, ?, ?, '2xx', 10, 5, 1, ?, ?)",
        (monitor_id, name, kind, target, NOW, NOW),
    )
    db.execute("INSERT INTO uptime_checks (monitor_id, checked_at, up) VALUES (?, ?, 1)", (monitor_id, NOW))


def test_linked_app_monitors_check_the_url_and_linked_apps_go(tmp_path):
    db_path = tmp_path / "apps.db"
    _alembic(db_path, "upgrade", BEFORE)
    db = sqlite3.connect(db_path)
    db.execute("INSERT INTO organizations (id, name, prefix, guild_id, is_active) VALUES (1, 'SoDA', 'soda', '1', 1)")
    _app(db, "a1", "vault", "linked", {"kind": "service", "url": "https://vault.example.org"})
    _app(db, "a2", "wayfinder", "linked", {"kind": "service"})
    _app(db, "a3", "bot", "runpod", {"kind": "bot", "image": "a/b"})
    _monitor(db, 1, "vault", "app", "vault")
    _monitor(db, 2, "wayfinder", "app", "wayfinder")
    _monitor(db, 3, "bot", "app", "bot")
    db.commit()
    db.close()

    _alembic(db_path, "upgrade", AFTER)
    db = sqlite3.connect(db_path)
    assert db.execute("SELECT name FROM runpod_apps").fetchall() == [("bot",)]
    rows = db.execute("SELECT id, target_kind, target FROM uptime_monitors ORDER BY id").fetchall()
    assert rows == [(1, "url", "https://vault.example.org"), (3, "app", "bot")]
    # The url monitor keeps its history; the monitor with nothing to check goes with its checks
    assert db.execute("SELECT monitor_id FROM uptime_checks ORDER BY monitor_id").fetchall() == [(1,), (3,)]
    db.close()
