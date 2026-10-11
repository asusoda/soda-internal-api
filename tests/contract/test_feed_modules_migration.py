"""The migration that merges the job_webhook and hackathon_webhook switches into one feeds switch."""

import json
import sqlite3

from .test_module_rename_migration import _alembic, _config

BEFORE = "657f276f6993"
AFTER = "a3c5e7f9b1d3"


def test_either_webhook_module_on_turns_feeds_on_and_comes_back(tmp_path):
    db_path = tmp_path / "orgs.db"
    _alembic(db_path, "upgrade", BEFORE)
    db = sqlite3.connect(db_path)
    orgs = [
        (
            1,
            "SoDA",
            "soda",
            "1",
            json.dumps({"modules": {"job_webhook": False, "hackathon_webhook": True, "points": True}}),
        ),
        (2, "AIS", "ais", "2", json.dumps({"modules": {"job_webhook": False, "hackathon_webhook": False}})),
        (3, "Club", "club", "3", json.dumps({"modules": {"job_webhook": True}})),
        (4, "New", "new", "4", None),
    ]
    db.executemany(
        "INSERT INTO organizations (id, name, prefix, guild_id, is_active, config) VALUES (?, ?, ?, ?, 1, ?)", orgs
    )
    db.commit()
    db.close()

    _alembic(db_path, "upgrade", AFTER)
    db = sqlite3.connect(db_path)
    assert _config(db, 1)["modules"] == {"points": True, "feeds": True}
    assert _config(db, 2)["modules"] == {"feeds": False}
    # A switch that was not set counts as on
    assert _config(db, 3)["modules"] == {"feeds": True}
    assert _config(db, 4) == {}
    db.close()

    _alembic(db_path, "downgrade", BEFORE)
    db = sqlite3.connect(db_path)
    assert _config(db, 1)["modules"] == {"points": True, "job_webhook": True, "hackathon_webhook": True}
    assert _config(db, 2)["modules"] == {"job_webhook": False, "hackathon_webhook": False}
    db.close()
