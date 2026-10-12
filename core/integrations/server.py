"""The This server hosting provider: org apps as capped containers on the deployment's own server. No Flask here.

The runner (deploy/runner/platform_runner.py) runs on the host as root and listens on a Unix socket in the data
folder. This module only talks to that socket. The runner checks each request against its policy file, so the
memory cap, the published ports and the host paths an org may use are decided on the server, not here.

An app's pod id is its container name, app-<org>-<app>. A shared app has no org (org_id None): the deployment owns
it, and its container is shared-<app>. Godfather does not use this provider: its pods need SSH.
"""

import http.client
import json
import socket
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from sqlalchemy import column, select
from sqlalchemy import table as sql_table

from core import hosting
from core.log import get_logger

logger = get_logger(__name__)

# The runner's socket, in the data folder that the containers mount at /app/data
SOCKET = "data/runner.sock"
TIMEOUT_SECONDS = 900  # a deploy can pull an image first
# The host address that a Platform container reaches a published port on
HOST_ADDRESS = "host.containers.internal"
RUNPOD_ONLY = ("gpu", "cpu", "cloud", "dataCenterIds", "mounts", "disk", "registry", "args")
_organizations = sql_table("organizations", column("id"), column("prefix"))


class RunnerError(hosting.HostingError):
    pass


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float):
        super().__init__("runner", timeout=timeout)
        self._path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._path)


def call(method: str, path: str, body: dict | None = None, socket_path: str | None = None) -> Any:
    """One request to the runner. Raises RunnerError with the runner's message."""
    connection = _UnixConnection(socket_path or SOCKET, TIMEOUT_SECONDS)
    try:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        connection.request(method, path, body=data, headers=headers)
        response = connection.getresponse()
        raw = response.read()
    except OSError as e:
        raise RunnerError(f"The This server runner is not reachable: {type(e).__name__}", 503) from e
    finally:
        connection.close()
    try:
        answer = json.loads(raw or b"{}")
    except ValueError as e:
        raise RunnerError("The runner sent an answer that is not JSON", 502) from e
    if response.status >= 400:
        raise RunnerError(str(answer.get("error") or f"The runner answered {response.status}"), response.status)
    return answer


def _base(org: str | None) -> str:
    """The runner path of an org's apps, or of the shared apps (org None)."""
    return "/shared" if org is None else f"/apps/{quote(org, safe='')}"


def _app_path(pod_id: str, org: str | None) -> str:
    prefix = "shared-" if org is None else f"app-{org}-"
    if not pod_id.startswith(prefix):
        raise RunnerError("This container is not an app of this org", 404)
    return f"{_base(org)}/{quote(pod_id[len(prefix) :], safe='')}"


class ServerClient:
    """The runner calls for one org, or for the shared apps when org is None. A pod is the dict that the runner
    returns for a container."""

    def __init__(self, org: str | None):
        self.org = org

    def list_pods(self) -> list[dict]:
        apps = call("GET", "/apps")["apps"]
        if self.org is None:
            return [a for a in apps if a.get("shared")]
        return [a for a in apps if a.get("org") == self.org]

    def get_pod(self, pod_id: str) -> dict | None:
        try:
            return call("GET", _app_path(pod_id, self.org))
        except RunnerError as e:
            if e.status == 404:
                return None
            raise

    def create_pod(self, body: dict) -> dict:
        app = str(body.pop("name"))
        return call("PUT", f"{_base(self.org)}/{quote(app, safe='')}", body)

    def update_pod(self, pod_id: str, body: dict) -> dict:
        return call("PUT", _app_path(pod_id, self.org), body)

    def start_pod(self, pod_id: str) -> Any:
        return call("POST", _app_path(pod_id, self.org) + "/start")

    def stop_pod(self, pod_id: str) -> Any:
        return call("POST", _app_path(pod_id, self.org) + "/stop")

    def delete_pod(self, pod_id: str) -> Any:
        return call("DELETE", _app_path(pod_id, self.org))

    def restart_pod(self, pod_id: str) -> Any:
        return call("POST", _app_path(pod_id, self.org) + "/restart")

    def logs(self, pod_id: str, lines: int) -> str:
        return str(call("GET", _app_path(pod_id, self.org) + f"/logs?lines={int(lines)}")["logs"])


def _prefix(db, org_id: int | None) -> str | None:
    """The org's prefix, or None for the shared apps."""
    if org_id is None:
        return None
    prefix = db.execute(select(_organizations.c.prefix).where(_organizations.c.id == org_id)).scalar()
    if prefix is None:
        raise hosting.ProviderError("No such organization", 404)
    return str(prefix)


def _org_of(pod_id: str) -> str | None:
    """The org of an app container, from its platform.org label, or None for a shared app. A prefix can hold
    dashes, so the name alone is not enough."""
    for item in call("GET", "/apps")["apps"]:
        if item.get("id") == pod_id:
            return None if item.get("shared") else str(item["org"])
    raise RunnerError("No such app container", 404)


class ServerProvider:
    """The server hosting provider: capped containers on this server, through the runner."""

    name = "server"
    title = "This server"
    # No org keys: the deployment provides the server
    integration = ""
    godfather = False

    def configured(self, db, org_id: int | None) -> bool:
        return Path(SOCKET).exists()

    def client(self, db, org_id: int | None) -> ServerClient:
        if not Path(SOCKET).exists():
            raise hosting.ProviderError("This server has no runner. See docs/operations.md, This server runner", 400)
        return ServerClient(_prefix(db, org_id))

    def status(self, pod: dict | None) -> str:
        if pod is None:
            return "GONE"
        state = str(pod.get("state") or "unknown").lower()
        return {"running": "RUNNING", "exited": "EXITED", "stopped": "EXITED", "created": "EXITED"}.get(
            state, state.upper()
        )

    def machine(self, pod: dict | None) -> dict | None:
        if not pod:
            return None
        return {"memoryMb": pod.get("memory_mb"), "cpus": pod.get("cpus")}

    def ssh_address(self, pod: dict) -> tuple[str, int] | None:
        return None

    def proxy_url(self, pod_id: str, port: int, path: str) -> str:
        """The address of a published port from a Platform container. Raises RunnerError when it is not published."""
        pod = call("GET", _app_path(pod_id, _org_of(pod_id)))
        host = next((p["host"] for p in pod.get("ports") or [] if p.get("container") == port), None)
        if host is None:
            raise RunnerError(f"Port {port} of {pod_id} is not published on this server", 409)
        return f"http://{HOST_ADDRESS}:{host}{path}"

    def healthy(self, pod_id: str, port: int, path: str) -> bool:
        """Whether the container answers path on port, asked by the runner on the host."""
        try:
            org = _org_of(pod_id)
            answer = call("GET", _app_path(pod_id, org) + "/health?" + urlencode({"port": port, "path": path}))
        except RunnerError as e:
            logger.info("health check failed pod=%s error=%s", pod_id, e.message)
            return False
        return bool(answer.get("ok"))

    def validate(self, manifest: dict) -> None:
        """Raise HostingError for a manifest this provider cannot run."""
        used = [field for field in RUNPOD_ONLY if field in manifest]
        if used:
            raise hosting.HostingError(f"This server does not take {', '.join(used)}; those fields are for RunPod")
        if "memory" not in manifest:
            raise hosting.HostingError("An app on This server needs memory, in MB")

    def request(self, app_name: str, org_prefix: str | None, pod_id: str | None, manifest: dict, image: str, env: dict):
        """The runner request a deploy makes, as (method, path, body)."""
        container_ports = [int(p.split("/")[0]) for p in manifest.get("ports") or []]
        published = {int(k): int(v) for k, v in (manifest.get("publish") or {}).items()}
        ports = [{"container": c, "host": published.get(c)} for c in sorted({*container_ports, *published})]
        body: dict[str, Any] = {
            "image": image,
            "env": env,
            "memory_mb": int(manifest["memory"]),
            "ports": ports,
            "volumes": manifest.get("volumes") or [],
        }
        for field in ("cpus", "command", "workdir", "group", "alias"):
            if field in manifest:
                body[field] = manifest[field]
        path = f"{_base(org_prefix)}/{app_name}"
        return ("PUT", path, body) if pod_id else ("PUT", path, {**body, "name": app_name})


hosting.register(ServerProvider())


def host_action(kind: str, name: str, action: str) -> dict:
    """Start, stop or restart a container or systemd unit that is not an app, if the runner's policy lists it."""
    return call("POST", f"/host/{quote(kind, safe='')}/{quote(name, safe='')}/{quote(action, safe='')}")


def host_logs(kind: str, name: str, lines: int) -> str:
    path = f"/host/{quote(kind, safe='')}/{quote(name, safe='')}/logs?lines={int(lines)}"
    return str(call("GET", path)["logs"])
