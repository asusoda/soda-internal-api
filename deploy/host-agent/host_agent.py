"""Write a snapshot of the server's services to a JSON file that the API reads.

The agent runs on the host as root, because only root sees every container and process. It only reads: podman
ps and stats, the proxy hosts of Nginx Proxy Manager, the listening ports and the cgroups of host processes. It
writes one file, data/host.json in the Platform checkout, which the containers see as /app/data/host.json.

    python3 host_agent.py --root /var/www/soda-internal-api --port 8080

A service is a container, or a host process that listens on a port that a proxy host forwards to or that --port
names. Each service has the domains whose proxy host forwards to one of its ports. Standard library only.
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess  # nosec B404 - runs podman and ss with fixed arguments
import time
from pathlib import Path

VERSION = 1
NPM_DATABASE = "/var/www/nginx-proxy-manager/data/database.sqlite"
UNITS = {"k": 10**3, "m": 10**6, "g": 10**9, "t": 10**12}


def _run(*args: str) -> str:
    """The output of a command, or an empty string when it fails."""
    path = shutil.which(args[0])
    if path is None:
        return ""
    try:
        result = subprocess.run(  # nosec B603 - fixed arguments, no shell
            [path, *args[1:]], capture_output=True, text=True, timeout=20, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout


def size(text: str) -> int | None:
    """Bytes from a podman size such as 9.421MB or 512kB (powers of 1000)."""
    found = re.fullmatch(r"\s*([\d.]+)\s*([kKmMgGtT]?)i?B\s*", text or "")
    if not found:
        return None
    return int(float(found.group(1)) * UNITS.get(found.group(2).lower(), 1))


def percent(text: str) -> float | None:
    try:
        return round(float((text or "").rstrip("%")), 2)
    except ValueError:
        return None


def memory_total() -> int | None:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) * 1024
    return None


def proxy_hosts(path: str) -> dict[int, list[str]]:
    """The domains of each forwarded port, from the proxy hosts of Nginx Proxy Manager. Opened read-only."""
    if not os.path.exists(path):
        return {}
    by_port: dict[int, list[str]] = {}
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT domain_names, forward_port FROM proxy_host WHERE enabled = 1 AND is_deleted = 0")
        for names, port in rows:
            by_port.setdefault(int(port), []).extend(json.loads(names or "[]"))
    except sqlite3.Error:
        return {}
    finally:
        db.close()
    return by_port


def containers(root: str, total: int | None, domains: dict[int, list[str]]) -> list[dict]:
    listed = json.loads(_run("podman", "ps", "-a", "--format", "json") or "[]")
    stats = {s["name"]: s for s in json.loads(_run("podman", "stats", "--no-stream", "--format", "json") or "[]")}
    found = []
    for c in listed:
        name = c["Names"][0]
        labels = c.get("Labels") or {}
        ports = sorted({int(p["host_port"]) for p in c.get("Ports") or [] if p.get("host_port")})
        used, _, limit = stats.get(name, {}).get("mem_usage", "").partition("/")
        limit_bytes = size(limit)
        found.append(
            {
                "id": c.get("Id"),
                "name": name,
                "kind": "container",
                "state": c.get("State"),
                "status": c.get("Status"),
                "image": c.get("Image"),
                "project": labels.get("com.docker.compose.project"),
                # Platform's own compose containers, and the shared apps that the runner starts for the deployment
                "platform": labels.get("com.docker.compose.project.working_dir") == root
                or labels.get("platform.shared") == "1",
                # The org of a container that Platform starts for an app
                "org": labels.get("platform.org"),
                "memory_used": size(used),
                # podman shows the host's memory when the container has no cap
                "memory_limit": limit_bytes if limit_bytes and total and limit_bytes < total * 0.98 else None,
                "cpu_percent": percent(stats.get(name, {}).get("cpu_percent", "")),
                "ports": ports,
                "domains": sorted({d for p in ports for d in domains.get(p, [])}),
            }
        )
    return found


def _cgroup(pid: str) -> str:
    """The cgroup of a process, such as /system.slice/wayfinder.service."""
    try:
        return Path(f"/proc/{pid}/cgroup").read_text().strip().split("::")[-1]
    except OSError:
        return ""


def _cgroup_number(cgroup: str, name: str) -> int | None:
    try:
        raw = Path("/sys/fs/cgroup", cgroup.lstrip("/"), name).read_text().strip()
    except OSError:
        return None
    return int(raw) if raw.isdigit() else None


def processes(ports: set[int], found: list[dict], domains: dict[int, list[str]]) -> list[dict]:
    """Host processes that listen on one of the ports, grouped by systemd unit. A port of a container on the host
    network goes on that container."""
    taken = {p for c in found for p in c["ports"]}
    by_id = {c["id"]: c for c in found if c.get("id")}
    by_unit: dict[str, dict] = {}
    for line in _run("ss", "-ltnpH").splitlines():
        parts = line.split()
        if len(parts) < 6:
            continue
        port = int(parts[3].rsplit(":", 1)[-1]) if parts[3].rsplit(":", 1)[-1].isdigit() else None
        pid = re.search(r"pid=(\d+)", parts[-1])
        if port is None or port not in ports or port in taken or pid is None:
            continue
        cgroup = _cgroup(pid.group(1))
        libpod = re.search(r"libpod-([0-9a-f]{64})", cgroup)
        if libpod and libpod.group(1) in by_id:
            container = by_id[libpod.group(1)]
            container["ports"] = sorted({*container["ports"], port})
            container["domains"] = sorted({*container["domains"], *domains.get(port, [])})
            continue
        if not cgroup.endswith(".service"):
            cgroup = ""
        name = cgroup.rsplit("/", 1)[-1].removesuffix(".service") if cgroup else f"pid {pid.group(1)}"
        entry = by_unit.setdefault(
            name,
            {
                "name": name,
                "kind": "process",
                "state": "running",
                "status": f"systemd {name}.service" if cgroup else "not in a systemd unit",
                "image": None,
                "project": None,
                "platform": False,
                "org": None,
                "memory_used": _cgroup_number(cgroup, "memory.current") if cgroup else None,
                "memory_limit": _cgroup_number(cgroup, "memory.max") if cgroup else None,
                "cpu_percent": None,
                "ports": [],
                "domains": [],
            },
        )
        entry["ports"] = sorted({*entry["ports"], port})
        entry["domains"] = sorted({*entry["domains"], *domains.get(port, [])})
    return list(by_unit.values())


def snapshot(root: str, extra_ports: list[int], npm_database: str) -> dict:
    domains = proxy_hosts(npm_database)
    found = containers(root, memory_total(), domains)
    found += processes({*domains, *extra_ports}, found, domains)
    for service in found:
        service.pop("id", None)
    return {"version": VERSION, "generated_at": int(time.time()), "services": found}


def write(path: Path, data: dict) -> None:
    """Write the file in one step, so the API never reads half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data))
    temporary.chmod(0o644)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a snapshot of the server's services for the API.")
    parser.add_argument("--root", default="/var/www/soda-internal-api", help="the Platform checkout")
    parser.add_argument("--port", type=int, action="append", default=[], help="a host port to list, again for more")
    parser.add_argument("--npm-database", default=NPM_DATABASE)
    parser.add_argument("--interval", type=int, default=30, help="seconds between snapshots; 0 writes one and stops")
    args = parser.parse_args()
    out = Path(args.root, "data", "host.json")
    while True:
        write(out, snapshot(args.root, args.port, args.npm_database))
        if args.interval <= 0:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
