"""The This server runner: starts, stops and removes the app containers of orgs on this server for Platform.

It runs on the host as root, because podman runs the server's containers as root. The API reaches it over a
Unix socket in the Platform data folder. The runner is the security boundary: it checks each request against
/etc/platform-runner.json, so the API cannot run a container that the policy does not allow.

    python3 platform_runner.py --config /etc/platform-runner.json

Each app is one container named app-<org>-<app>, on a network of its org (platform-<org>), with a memory and
CPU cap. A shared app, which the deployment owns and every org uses, is shared-<app> on platform-shared, with the
policy's "shared" section in place of an org's. A port is published only on the bind addresses of the policy (localhost and the podman gateway, where
Nginx Proxy Manager reaches it), never on a public address. A volume is a folder under data_root, or a host
path that the policy allows for that org. Every container runs with no-new-privileges, except the apps that an
org's no_new_privileges_off lists: databases whose images drop privileges with gosu. The parts of one app share a
group network, where each answers to its
alias. The policy's host_control list names the other containers and systemd units that the superadmin may start,
stop, restart and read the logs of. Standard library only. See docs/operations.md, "This server runner".
"""

import argparse
import fnmatch
import json
import os
import re
import shutil
import socket
import socketserver
import subprocess  # nosec B404 - runs podman with fixed arguments
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
# An org prefix (modules/organizations PREFIX_PATTERN)
ORG = re.compile(r"^[a-z0-9_-]{2,20}$")
IMAGE = re.compile(r"^[a-z0-9][a-z0-9._/-]{0,250}(:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}|@sha256:[a-f0-9]{64})$")
ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
CONTAINER_PATH = re.compile(r"^/[A-Za-z0-9_./-]{0,250}$")
# A container or systemd unit that the policy lets the superadmin control
HOST_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
MAX_LOG_LINES = 1000
MAX_BODY = 200_000
MAX_ENV_VALUE = 20_000
LABEL = "platform.managed"
_lock = threading.Lock()


class Refused(Exception):
    """A request the policy does not allow, or a podman failure. status is the HTTP status to answer."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def podman(*args: str, check: bool = True, timeout: int = 300) -> str:
    path = shutil.which("podman")
    if path is None:
        raise Refused("podman is not installed on this server", 500)
    result = subprocess.run(  # nosec B603 - fixed command, arguments checked against the policy
        [path, *args], capture_output=True, text=True, timeout=timeout, check=False
    )
    if check and result.returncode != 0:
        raise Refused(f"podman {args[0]} failed: {result.stderr.strip()[:500]}", 502)
    return result.stdout


def exists(*args: str) -> bool:
    """Whether a podman exists check (image exists, network exists) answers yes."""
    path = shutil.which("podman")
    if path is None:
        raise Refused("podman is not installed on this server", 500)
    result = subprocess.run(
        [
            path,
            *args,
        ],
        capture_output=True,
        timeout=60,
        check=False,
    )  # nosec B603 - fixed command
    return result.returncode == 0


def load_policy(path: str) -> dict:
    return load_policy_dict(json.loads(Path(path).read_text()))


def load_policy_dict(policy: dict) -> dict:
    """The policy with a default for each key it leaves out."""
    policy.setdefault("data_root", "/var/lib/platform-apps")
    policy.setdefault("bind_ips", ["127.0.0.1"])
    policy.setdefault("registries", ["ghcr.io/"])
    policy.setdefault("memory_mb_total", 1536)
    policy.setdefault("memory_mb_max", 1024)
    policy.setdefault("cpus_max", 1.0)
    policy.setdefault("port_range", [20000, 20999])
    policy.setdefault("orgs", {})
    policy.setdefault("host_control", {"containers": [], "units": []})
    # A container on podman's default network keeps the bridge, and so the 10.88.0.1 bind address, in place
    policy.setdefault("bridge_image", "docker.io/library/nginx:alpine")
    return policy


def container_name(org: str | None, app: str) -> str:
    """app-<org>-<app>, or shared-<app> for a shared app (org None)."""
    return f"shared-{app}" if org is None else f"app-{org}-{app}"


def _section(policy: dict, org: str | None) -> dict:
    """The policy entry of an org, or the shared section for a shared app."""
    return (policy.get("shared") if org is None else policy["orgs"].get(org)) or {}


def _inspect(name: str) -> dict | None:
    out = podman("container", "inspect", name, check=False)
    try:
        found = json.loads(out or "[]")
    except ValueError:
        return None
    return found[0] if found else None


def _memory_mb(info: dict) -> int:
    return int((info.get("HostConfig") or {}).get("Memory") or 0) // (1024 * 1024)


def managed() -> list[dict]:
    """Every container the runner made, as podman inspect shows it."""
    names = [n for n in podman("ps", "-a", "--filter", f"label={LABEL}=1", "--format", "{{.Names}}").split() if n]
    return [info for info in (_inspect(n) for n in names) if info]


def describe(info: dict) -> dict:
    """The container as the API sees it: state, image, cap and ports."""
    labels = (info.get("Config") or {}).get("Labels") or {}
    state = info.get("State") or {}
    bindings = (info.get("HostConfig") or {}).get("PortBindings") or {}
    ports = sorted(
        {
            (int(key.split("/")[0]), int(b["HostPort"]))
            for key, binds in bindings.items()
            for b in binds or []
            if b.get("HostPort")
        }
    )
    return {
        "id": info["Name"].lstrip("/"),
        "org": labels.get("platform.org"),
        "shared": labels.get("platform.shared") == "1",
        "app": labels.get("platform.app"),
        "image": (info.get("Config") or {}).get("Image"),
        "state": str(state.get("Status") or "unknown"),
        "started_at": state.get("StartedAt"),
        "group": labels.get("platform.group"),
        "memory_mb": _memory_mb(info),
        "cpus": round(int((info.get("HostConfig") or {}).get("NanoCpus") or 0) / 1e9, 2),
        "ports": [{"container": c, "host": h} for c, h in ports],
    }


def _allowed_host_path(policy: dict, org: str | None, path: str) -> bool:
    real = os.path.realpath(path)
    for allowed in _section(policy, org).get("host_paths") or []:
        base = os.path.realpath(allowed)
        if real == base or real.startswith(base.rstrip("/") + "/"):
            return True
    return False


def check(policy: dict, org: str | None, app: str, body: dict) -> dict:
    """The run request after the policy checks, with each volume's host path. org None is a shared app. Raises
    Refused."""
    if (org is not None and not ORG.match(org)) or not NAME.match(app):
        raise Refused("org is an org prefix, and app is lowercase letters, digits and dashes")
    image = body.get("image")
    if not isinstance(image, str) or not IMAGE.match(image):
        raise Refused("image must be a name with a tag or a sha256 digest")
    if not any(image.startswith(prefix) for prefix in policy["registries"]):
        raise Refused(f"image must come from one of: {', '.join(policy['registries'])}")

    env = body.get("env") or {}
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and ENV_KEY.match(k) and isinstance(v, str) and len(v) <= MAX_ENV_VALUE
        for k, v in env.items()
    ):
        raise Refused("env must map variable names to text")

    memory = body.get("memory_mb")
    if not isinstance(memory, int) or isinstance(memory, bool) or not 16 <= memory <= policy["memory_mb_max"]:
        raise Refused(f"memory_mb must be a whole number from 16 to {policy['memory_mb_max']}")
    others = sum(_memory_mb(i) for i in managed() if i["Name"].lstrip("/") != container_name(org, app))
    if others + memory > policy["memory_mb_total"]:
        raise Refused(
            f"This server has {policy['memory_mb_total'] - others} MB left for apps; the app asks for {memory} MB",
            409,
        )
    cpus = body.get("cpus", 0.5)
    if not isinstance(cpus, (int, float)) or isinstance(cpus, bool) or not 0.05 <= cpus <= policy["cpus_max"]:
        raise Refused(f"cpus must be from 0.05 to {policy['cpus_max']}")

    org_ports = set(_section(policy, org).get("host_ports") or [])
    low, high = policy["port_range"]
    ports = []
    for port in body.get("ports") or []:
        if not isinstance(port, dict) or not isinstance(port.get("container"), int):
            raise Refused("each port needs a container port number")
        host = port.get("host")
        if host is not None and (not isinstance(host, int) or not (host in org_ports or low <= host <= high)):
            raise Refused(f"host port {host} is not allowed for {org}: use {low} to {high}")
        if not 1 <= port["container"] <= 65535:
            raise Refused("a container port is from 1 to 65535")
        public = host is not None and host in set(_section(policy, org).get("public_ports") or [])
        ports.append({"container": port["container"], "host": host, "public": public})

    volumes = []
    for volume in body.get("volumes") or []:
        if not isinstance(volume, dict) or not isinstance(volume.get("path"), str):
            raise Refused("each volume needs a path in the container")
        if not CONTAINER_PATH.match(volume["path"]) or ".." in volume["path"]:
            raise Refused("a volume path must be an absolute path in the container")
        if volume.get("name"):
            if not NAME.match(str(volume["name"])):
                raise Refused("a volume name is lowercase letters, digits and dashes")
            # .shared cannot be an org prefix, which has no dots
            host = str(Path(policy["data_root"], org or ".shared", app, str(volume["name"])))
        elif volume.get("host"):
            host = str(volume["host"])
            if not _allowed_host_path(policy, org, host):
                raise Refused(f"the host path {host} is not allowed for {org}", 403)
        else:
            raise Refused("a volume needs a name or an allowed host path")
        volumes.append({"host": host, "path": volume["path"], "read_only": bool(volume.get("read_only"))})
    command = body.get("command") or []
    if (
        not isinstance(command, list)
        or len(command) > 32
        or not all(isinstance(a, str) and len(a) <= 500 for a in command)
    ):
        raise Refused("command must be a list of up to 32 arguments")
    workdir = body.get("workdir")
    if workdir is not None and (not isinstance(workdir, str) or not CONTAINER_PATH.match(workdir) or ".." in workdir):
        raise Refused("workdir must be an absolute path in the container")
    group, alias = body.get("group"), body.get("alias")
    for value, label in ((group, "group"), (alias, "alias")):
        if value is not None and (not isinstance(value, str) or not NAME.match(value)):
            raise Refused(f"{label} is lowercase letters, digits and dashes")
    # Postgres and Redis drop to their own user with gosu, which no-new-privileges stops on this kernel
    no_new_privileges = app not in (_section(policy, org).get("no_new_privileges_off") or [])
    return {
        "image": image,
        "no_new_privileges": no_new_privileges,
        "env": env,
        "memory_mb": memory,
        "cpus": float(cpus),
        "ports": ports,
        "volumes": volumes,
        "command": command,
        "workdir": workdir,
        "group": group,
        "alias": alias,
    }


BRIDGE = "platform-bridge"


def ensure_bridge(policy: dict) -> None:
    """Keep one small container on podman's default network. Without one, podman removes the podman0 bridge and its
    address 10.88.0.1, which the policy's bind_ips and Nginx Proxy Manager use."""
    if "10.88.0.1" not in policy["bind_ips"]:
        return
    if exists("container", "exists", BRIDGE):
        podman("start", BRIDGE, check=False)
        return
    podman(
        "run",
        "-d",
        "--name",
        BRIDGE,
        "--network",
        "podman",
        "--restart",
        "always",
        "--memory",
        "16m",
        "--entrypoint",
        "sleep",
        policy["bridge_image"],
        "infinity",
    )


def run(policy: dict, org: str | None, app: str, body: dict) -> dict:
    """Pull the image, then replace the app's container with one from the request. Returns the new container."""
    request = check(policy, org, app, body)
    name = container_name(org, app)
    ensure_bridge(policy)
    # The apps of one group (the parts of one app) share a network, where each part answers to its alias
    network = f"platform-{org or 'shared'}" + (f"-{request['group']}" if request["group"] else "")
    with _lock:
        if not exists("image", "exists", request["image"]):
            podman("pull", "--quiet", request["image"], timeout=900)
        if not exists("network", "exists", network):
            podman("network", "create", network)
        for volume in request["volumes"]:
            if volume["host"].startswith(policy["data_root"].rstrip("/") + "/"):
                Path(volume["host"]).mkdir(parents=True, exist_ok=True, mode=0o750)
        args = [
            "run",
            "-d",
            "--replace",
            "--name",
            name,
            "--network",
            network,
            "--restart",
            "always",
            "--memory",
            f"{request['memory_mb']}m",
            "--cpus",
            str(request["cpus"]),
            "--pids-limit",
            "512",
            "--label",
            f"{LABEL}=1",
            "--label",
            f"platform.org={org}" if org is not None else "platform.shared=1",
            "--label",
            f"platform.app={app}",
        ]
        if request["no_new_privileges"]:
            args += ["--security-opt", "no-new-privileges"]
        if request["group"]:
            args += ["--label", f"platform.group={request['group']}"]
        if request["alias"]:
            args += ["--network-alias", request["alias"]]
        if request["workdir"]:
            args += ["--workdir", request["workdir"]]
        for key, value in sorted(request["env"].items()):
            args += ["--env", f"{key}={value}"]
        for port in request["ports"]:
            if port["host"] is None:
                continue
            # A public port binds every address, as a service that clients reach by the server's IP needs
            for ip in ["0.0.0.0"] if port["public"] else policy["bind_ips"]:  # nosec B104 - only the policy's public_ports
                args += ["--publish", f"{ip}:{port['host']}:{port['container']}"]
        for volume in request["volumes"]:
            args += ["--volume", f"{volume['host']}:{volume['path']}:{'ro' if volume['read_only'] else 'rw'}"]
        podman(*args, request["image"], *request["command"])
        info = _inspect(name)
    if info is None:
        raise Refused("the container did not start", 502)
    return describe(info)


def _output(*args: str) -> str:
    """stdout and stderr of a read-only command, such as podman logs, which writes the container's stderr to its
    own."""
    path = shutil.which(args[0])
    if path is None:
        raise Refused(f"{args[0]} is not installed on this server", 500)
    result = subprocess.run(  # nosec B603 - fixed command, checked names
        [path, *args[1:]], capture_output=True, text=True, timeout=30, check=False
    )
    return (result.stdout + result.stderr)[-200_000:]


def _lines(query: dict) -> str:
    lines = int((query.get("lines") or ["200"])[0])
    return str(max(1, min(lines, MAX_LOG_LINES)))


def _container_id(name: str) -> str:
    """podman's own id of a container, so that no name from a request reaches a command line."""
    info = _inspect(name)
    if info is None:
        raise Refused("No such container", 404)
    return str(info["Id"])


def app_logs(name: str, query: dict) -> dict:
    return {"logs": _output("podman", "logs", "--tail", _lines(query), _container_id(name))}


def _controlled(policy: dict, kind: str, name: str) -> bool:
    """Whether the policy lets the superadmin control this container (names may use * patterns) or unit."""
    patterns = (policy.get("host_control") or {}).get(kind) or []
    return bool(HOST_NAME.match(name)) and any(fnmatch.fnmatchcase(name, p) for p in patterns)


def _policy_unit(policy: dict, name: str) -> str | None:
    """The unit as the policy writes it. Units are exact names, so the command line takes the policy's text."""
    return next((u for u in (policy.get("host_control") or {}).get("units") or [] if u == name), None)


def host_control(policy: dict, kind: str, name: str, action: str, query: dict) -> dict:
    """Start, stop, restart or read the logs of a container or systemd unit that the policy lists."""
    if kind == "containers" and _controlled(policy, kind, name):
        info = _inspect(name)
        if info is None:
            raise Refused("No such container", 404)
        if ((info.get("Config") or {}).get("Labels") or {}).get(LABEL) == "1":
            raise Refused("This is an app container. Control it through its app", 409)
        container = str(info["Id"])
        if action == "logs":
            return {"logs": _output("podman", "logs", "--tail", _lines(query), container)}
        podman(action, container)
        return {"name": name, "state": str(((_inspect(container) or {}).get("State") or {}).get("Status"))}
    known = _policy_unit(policy, name) if kind == "units" else None
    if known is None:
        raise Refused(f"{name} is not in the host_control list of the policy", 403)
    unit = f"{known}.service"
    if action == "logs":
        return {"logs": _output("journalctl", "-u", unit, "-n", _lines(query), "--no-pager", "-o", "short-iso")}
    path = shutil.which("systemctl")
    if path is None:
        raise Refused("systemctl is not installed on this server", 500)
    subprocess.run([path, action, unit], capture_output=True, timeout=60, check=False)  # nosec B603 - checked name
    state = _output("systemctl", "is-active", unit).strip()
    return {"name": name, "state": state}


def health(org: str | None, app: str, port: int, path: str | None) -> dict:
    """GET path on the container's port, from the host: on 127.0.0.1 when the port is published, else on the
    container's own address. With path None, only check that the port accepts a connection."""
    info = _inspect(container_name(org, app))
    if info is None:
        return {"ok": False, "error": "No container"}
    if path is not None and not CONTAINER_PATH.match(path):
        return {"ok": False, "error": "The path is not valid"}
    published = next((p["host"] for p in describe(info)["ports"] if p["container"] == int(port)), None)
    networks = ((info.get("NetworkSettings") or {}).get("Networks") or {}).values()
    ip = next((n.get("IPAddress") for n in networks if n.get("IPAddress")), None)
    targets = ([("127.0.0.1", published)] if published else []) + ([(ip, int(port))] if ip else [])
    if not targets:
        return {"ok": False, "error": "The container has no address"}
    error = "No answer"
    for address, target_port in targets:
        if path is None:
            try:
                with socket.create_connection((address, target_port), timeout=5):
                    return {"ok": True}
            except OSError as e:
                error = type(e).__name__
            continue
        try:
            url = f"http://{address}:{target_port}{path}"
            with urllib.request.urlopen(url, timeout=5) as response:  # nosec B310 - http to a container
                return {"ok": response.status < 400, "status": response.status}
        except urllib.error.HTTPError as e:
            return {"ok": False, "status": e.code}
        except (OSError, ValueError) as e:
            error = type(e).__name__
    return {"ok": False, "error": error}


class Handler(BaseHTTPRequestHandler):
    policy: dict = {}

    def log_message(self, format, *args):
        sys.stderr.write("runner: " + (format % args) + "\n")

    def _answer(self, status: int, body: object) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise Refused("The request is too large", 413)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw)
        except ValueError as e:
            raise Refused("The body must be JSON") from e
        if not isinstance(body, dict):
            raise Refused("The body must be a JSON object")
        return body

    def _route(self, method: str) -> None:
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        try:
            if method == "GET" and parts == ["health"]:
                used = sum(_memory_mb(i) for i in managed())
                return self._answer(
                    200, {"ok": True, "memory_mb_total": self.policy["memory_mb_total"], "memory_mb_used": used}
                )
            if method == "GET" and parts == ["apps"]:
                return self._answer(200, {"apps": [describe(i) for i in managed()]})
            if len(parts) == 4 and parts[0] == "host":
                kind, host_name, action = parts[1], parts[2], parts[3]
                allowed = (method == "GET" and action == "logs") or (
                    method == "POST" and action in ("start", "stop", "restart")
                )
                if not allowed:
                    return self._answer(404, {"error": "Not found"})
                result = host_control(self.policy, kind, host_name, action, parse_qs(url.query))
                return self._answer(200, result)
            if len(parts) >= 2 and parts[0] == "shared" and NAME.match(parts[1]):
                org, app, action = None, parts[1], (parts[2] if len(parts) > 2 else None)
            elif len(parts) >= 3 and parts[0] == "apps" and ORG.match(parts[1]) and NAME.match(parts[2]):
                org, app, action = parts[1], parts[2], (parts[3] if len(parts) > 3 else None)
            else:
                return self._answer(404, {"error": "Not found"})
            name = container_name(org, app)
            if method == "PUT" and action is None:
                return self._answer(200, run(self.policy, org, app, self._body()))
            if method == "GET" and action == "health":
                query = parse_qs(url.query)
                port = int((query.get("port") or ["0"])[0])
                path = None if query.get("tcp") else (query.get("path") or ["/"])[0]
                return self._answer(200, health(org, app, port, path))
            info = _inspect(name)
            if info is None or ((info.get("Config") or {}).get("Labels") or {}).get(LABEL) != "1":
                return self._answer(404, {"error": "No app container"})
            if method == "GET" and action is None:
                return self._answer(200, describe(info))
            if method == "GET" and action == "logs":
                return self._answer(200, app_logs(name, parse_qs(url.query)))
            if method == "POST" and action in ("start", "stop", "restart"):
                podman(action, name)
                return self._answer(200, describe(_inspect(name) or info))
            if method == "DELETE" and action is None:
                podman("rm", "--force", name)
                return self._answer(200, {"deleted": name})
            return self._answer(404, {"error": "Not found"})
        except Refused as e:
            return self._answer(e.status, {"error": e.message})
        except (ValueError, subprocess.SubprocessError) as e:
            return self._answer(400, {"error": f"Bad request: {type(e).__name__}"})

    def do_GET(self):
        self._route("GET")

    def do_PUT(self):
        self._route("PUT")

    def do_POST(self):
        self._route("POST")

    def do_DELETE(self):
        self._route("DELETE")


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def serve(policy: dict) -> None:
    path = policy.get("socket", "/var/www/soda-internal-api/data/runner.sock")
    if os.path.exists(path):
        os.unlink(path)
    Handler.policy = policy
    ensure_bridge(policy)
    server = Server(path, Handler)
    if os.geteuid() == 0:
        os.chown(path, 0, int(policy.get("socket_gid", 0)))
    os.chmod(path, 0o660)  # nosec B103 - group write lets only socket_gid, the Platform containers, connect
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run org app containers on this server for Platform.")
    parser.add_argument("--config", default="/etc/platform-runner.json")
    serve(load_policy(parser.parse_args().config))


if __name__ == "__main__":
    main()
