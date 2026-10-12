"""The This server runner (deploy/runner/platform_runner.py) with podman replaced by an in-memory fake."""

import importlib.util
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("platform_runner", ROOT / "deploy" / "runner" / "platform_runner.py")
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

POLICY = {
    "registries": ["ghcr.io/", "docker.io/"],
    "bind_ips": ["127.0.0.1", "10.88.0.1"],
    "memory_mb_total": 1536,
    "memory_mb_max": 1024,
    "cpus_max": 1.0,
    "port_range": [20000, 20999],
    "orgs": {"soda": {"host_paths": ["/var/www/vaultwarden/data"], "host_ports": [8081]}},
    "shared": {"host_paths": ["/srv/shared/vault"], "host_ports": [8082]},
    "host_control": {"containers": ["twenty_*"], "units": ["react-website"]},
}


class FakePodman:
    """podman as the runner calls it: run, rm, start, stop, inspect, with containers kept in memory."""

    def __init__(self):
        self.containers: dict[str, dict] = {}
        self.calls: list[tuple] = []
        self.up = True
        self.server = None

    def podman(self, *args, check=True, timeout=300):
        self.calls.append(args)
        if args[0] == "run":
            self._run(list(args[1:]))
        elif args[0] == "rm":
            self.containers.pop(args[-1], None)
        elif args[0] in ("start", "stop", "restart"):
            self.containers[args[-1]]["State"]["Status"] = "exited" if args[0] == "stop" else "running"
        return ""

    def _run(self, args: list[str]) -> None:
        name, memory, nano = "", 0, 0
        labels: dict[str, str] = {}
        bindings: dict[str, list[dict]] = {}
        env: list[str] = []
        mounts: list[str] = []
        extra: dict[str, str] = {}
        i = 0
        while i < len(args) and args[i].startswith("-"):
            flag = args[i]
            if flag in ("-d", "--replace"):
                i += 1
                continue
            value = args[i + 1]
            if flag == "--name":
                name = value
            elif flag == "--label":
                key, _, val = value.partition("=")
                labels[key] = val
            elif flag == "--memory":
                memory = int(value.rstrip("m")) * 1024 * 1024
            elif flag == "--cpus":
                nano = int(float(value) * 1e9)
            elif flag == "--publish":
                ip, host, container = value.split(":")
                bindings.setdefault(f"{container}/tcp", []).append({"HostIp": ip, "HostPort": host})
            elif flag == "--env":
                env.append(value)
            elif flag == "--volume":
                mounts.append(value)
            else:
                extra[flag] = value
            i += 2
        image, command = args[i], args[i + 1 :]
        self.containers[name] = {
            "Name": name,
            "Id": name,
            "Config": {"Labels": labels, "Image": image, "Env": env, "Cmd": command},
            "State": {"Status": "running", "StartedAt": "2026-10-12T00:00:00Z"},
            "HostConfig": {"PortBindings": bindings, "Memory": memory, "NanoCpus": nano},
            "NetworkSettings": {"Networks": {extra.get("--network", "platform"): {"IPAddress": "10.89.9.2"}}},
            "Mounts": mounts,
            "Extra": extra,
        }

    def output(self, *args):
        self.calls.append(args)
        return f"log of {args[-1]}\n"

    def exists(self, *args):
        return True

    def inspect(self, name):
        return self.containers.get(name)

    def managed(self):
        return list(self.containers.values())

    def health(self, org, app, port, path):
        self.calls.append(("health", org, app, port, path))
        return {"ok": self.up, "status": 200 if self.up else 503}


def start(socket_path: str, monkeypatch) -> FakePodman:
    """Serve the runner on socket_path with a fake podman. The server stops when the test ends."""
    fake = FakePodman()
    monkeypatch.setattr(runner, "podman", fake.podman)
    monkeypatch.setattr(runner, "exists", fake.exists)
    monkeypatch.setattr(runner, "_inspect", fake.inspect)
    monkeypatch.setattr(runner, "managed", fake.managed)
    monkeypatch.setattr(runner, "health", fake.health)
    monkeypatch.setattr(runner, "_output", fake.output)
    runner.Handler.policy = runner.load_policy_dict(dict(POLICY))
    server = runner.Server(socket_path, runner.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fake.server = server
    return fake
