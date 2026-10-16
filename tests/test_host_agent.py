"""The host agent's parsing of podman and Nginx Proxy Manager output (deploy/host-agent/host_agent.py)."""

import importlib.util
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("host_agent", ROOT / "deploy" / "host-agent" / "host_agent.py")
assert spec is not None and spec.loader is not None
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)

PS = [
    {
        "Id": "a" * 64,
        "Names": ["soda-mcp"],
        "Image": "localhost/soda-mcp:latest",
        "State": "running",
        "Status": "Up 2 days",
        "Labels": {
            "com.docker.compose.project": "soda-internal-api",
            "com.docker.compose.project.working_dir": "/srv/platform",
        },
        "Ports": [{"host_port": 8001, "container_port": 8001}],
    },
    {"Id": "b" * 64, "Names": ["vaultwarden"], "State": "running", "Labels": None, "Ports": [{"host_port": 8081}]},
    {"Id": "c" * 64, "Names": ["tle_tle_1"], "State": "created", "Labels": {"platform.org": "ais"}, "Ports": None},
]
STATS = [
    {"name": "soda-mcp", "cpu_percent": "0.81%", "mem_usage": "143.9MB / 805.3MB"},
    {"name": "vaultwarden", "cpu_percent": "0.01%", "mem_usage": "37.63MB / 8.327GB"},
]


def test_size_reads_podman_sizes():
    assert agent.size("9.421MB") == 9_421_000
    assert agent.size(" 512kB ") == 512_000
    assert agent.size("2GiB") == 2_000_000_000
    assert agent.size("0B") == 0
    assert agent.size("--") is None


def test_containers_with_owner_labels_caps_and_domains(monkeypatch):
    outputs = {"ps": json.dumps(PS), "stats": json.dumps(STATS)}
    monkeypatch.setattr(agent, "_run", lambda *args: outputs[args[1]])
    found = {c["name"]: c for c in agent.containers("/srv/platform", 8_327_000_000, {8081: ["vault.example.org"]})}
    assert found["soda-mcp"]["platform"] is True and found["soda-mcp"]["memory_limit"] == 805_300_000
    assert found["soda-mcp"]["cpu_percent"] == 0.81
    # The host's memory is no cap
    assert found["vaultwarden"]["memory_limit"] is None and found["vaultwarden"]["domains"] == ["vault.example.org"]
    assert found["tle_tle_1"]["org"] == "ais" and found["tle_tle_1"]["memory_used"] is None


def test_proxy_hosts_reads_enabled_hosts_only(tmp_path):
    path = tmp_path / "database.sqlite"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE proxy_host (domain_names TEXT, forward_port INT, enabled INT, is_deleted INT)")
    db.executemany(
        "INSERT INTO proxy_host VALUES (?, ?, ?, ?)",
        [
            ('["a.example.org", "www.a.example.org"]', 3002, 1, 0),
            ('["old.example.org"]', 3002, 0, 0),
            ('["b.example.org"]', 81, 1, 1),
        ],
    )
    db.commit()
    db.close()
    assert agent.proxy_hosts(str(path)) == {3002: ["a.example.org", "www.a.example.org"]}
    assert agent.proxy_hosts(str(tmp_path / "none.sqlite")) == {}


def test_write_does_not_follow_a_planted_symlink(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    victim = tmp_path / "victim"
    victim.write_text("keep")
    (data / "host.tmp").symlink_to(victim)
    (data / "host.json").symlink_to(victim)
    agent.write(data / "host.json", {"version": 1})
    assert victim.read_text() == "keep"
    assert not (data / "host.json").is_symlink()
    assert json.loads((data / "host.json").read_text()) == {"version": 1}
    assert (data / "host.json").stat().st_mode & 0o777 == 0o644
    assert sorted(p.name for p in data.iterdir()) == ["host.json", "host.tmp"]
