"""Test setup shared by every test.

The app reads its database location and signing keys from the working directory at
import time, so the tests run from a fresh temporary directory with their own SQLite file.
Set TEST_DATABASE_URL to run them against Postgres instead; its schema is dropped and recreated.
"""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_HOME = Path(tempfile.mkdtemp(prefix="platform-tests-"))
atexit.register(shutil.rmtree, TEST_HOME, ignore_errors=True)

sys.path.insert(0, str(REPO_ROOT))
os.chdir(TEST_HOME)
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{TEST_HOME / 'data' / 'user.db'}"
os.environ.setdefault("IS_PROD", "false")
os.environ.setdefault("JOBS_BACKEND", "inline")
# Periodic jobs in a background thread would change rows between the steps of a test
os.environ.setdefault("JOBS_SCHEDULER", "false")


def create_schema():
    """Create every table on a fresh test database. Production uses Alembic migrations instead."""
    from sqlalchemy import text

    from core.db import Base, db_connect
    from modules.manifest import load_models

    load_models()

    if db_connect.engine.dialect.name == "postgresql":
        with db_connect.engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=db_connect.engine)
