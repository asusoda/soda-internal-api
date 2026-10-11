"""The server's health as this process sees it: load, memory, disk, the database and this container. No Flask here.

In a container, /proc/loadavg, /proc/meminfo and /proc/uptime show the host, and the disk of the data folder
is the host's disk. The cgroup files show the memory and CPU limits of this container only. Each value that
cannot be read is None, so the page shows what it can on any host.
"""

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from sqlalchemy import text

from core.log import get_logger

logger = get_logger("host")

CGROUP = Path("/sys/fs/cgroup")
# deploy/host-agent writes this file every 30 seconds. An older file means the agent stopped.
AGENT_FILE = "host.json"
DATA_DIR = "data"
AGENT_VERSION = 1
STALE_SECONDS = 120
STARTED = time.time()


def _read(path: Path | str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def _meminfo() -> dict[str, int]:
    """/proc/meminfo in bytes."""
    found: dict[str, int] = {}
    for line in (_read("/proc/meminfo") or "").splitlines():
        name, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            found[name] = int(parts[0]) * 1024
    return found


def _load() -> list[float] | None:
    raw = _read("/proc/loadavg")
    try:
        return [float(x) for x in raw.split()[:3]] if raw else None
    except ValueError:
        return None


def _uptime() -> int | None:
    raw = _read("/proc/uptime")
    try:
        return int(float(raw.split()[0])) if raw else None
    except ValueError:
        return None


def _number(raw: str | None) -> int | None:
    return int(raw) if raw and raw.isdigit() else None


def container() -> dict[str, Any]:
    """Memory use and limits of this process's container (cgroup v2). None where there is no limit or no file."""
    cpu_max = (_read(CGROUP / "cpu.max") or "").split()
    cpus = None
    if len(cpu_max) == 2 and cpu_max[0].isdigit() and cpu_max[1].isdigit() and int(cpu_max[1]):
        cpus = round(int(cpu_max[0]) / int(cpu_max[1]), 2)
    return {
        "memory_used": _number(_read(CGROUP / "memory.current")),
        "memory_limit": _number(_read(CGROUP / "memory.max")),
        "cpu_limit": cpus,
        "process_uptime_seconds": int(time.time() - STARTED),
    }


def disk(path: str) -> dict[str, int] | None:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return {"total": usage.total, "used": usage.used, "free": usage.free}


def database_size(db) -> int | None:
    """The database size in bytes: the SQLite file, or pg_database_size on Postgres."""
    bind = db.get_bind()
    try:
        if bind.dialect.name == "postgresql":
            return int(db.execute(text("SELECT pg_database_size(current_database())")).scalar() or 0)
        path = bind.url.database
        return os.path.getsize(path) if path and os.path.exists(path) else None
    except Exception:
        logger.warning("database size not readable", exc_info=True)
        return None


def stats(db, data_dir: str = "data") -> dict[str, Any]:
    """The server's health now."""
    memory = _meminfo()
    return {
        "cpus": os.cpu_count(),
        "load": _load(),
        "uptime_seconds": _uptime(),
        "memory": {"total": memory.get("MemTotal"), "available": memory.get("MemAvailable")}
        if memory.get("MemTotal")
        else None,
        "disk": disk(data_dir),
        "database_bytes": database_size(db),
        "database": db.get_bind().dialect.name,
        "container": container(),
    }


def agent_snapshot(data_dir: str | None = None) -> dict[str, Any] | None:
    """The services that the host agent last saw, with the age of the snapshot. None when there is no snapshot.

    The agent (deploy/host-agent) runs on the host and writes data/host.json. The API only reads it.
    """
    raw = _read(Path(data_dir or DATA_DIR) / AGENT_FILE)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        logger.warning("host agent file is not JSON")
        return None
    if not isinstance(data, dict) or data.get("version") != AGENT_VERSION or not isinstance(data.get("services"), list):
        logger.warning("host agent file has an unknown format")
        return None
    age = max(0, int(time.time()) - int(data.get("generated_at") or 0))
    return {"age_seconds": age, "stale": age > STALE_SECONDS, "services": data["services"]}
