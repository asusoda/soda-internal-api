"""RunPod REST client (api.runpod.io/v2) and the runpod hosting provider.

Each org uses its own API key, stored as an org secret.
"""

from typing import Any
from urllib.parse import quote

import requests

from core import hosting, secrets
from core.integrations.registry import Field, Integration, IntegrationError, register
from core.log import get_logger

logger = get_logger("runpod")

BASE_URL = "https://api.runpod.io/v2"
TIMEOUT_SECONDS = 30
SECRET_NAME = "runpod_api_key"  # nosec B105 - the name of an org secret, not its value
# Manifest fields that only This server reads
SERVER_ONLY = ("memory", "cpus", "publish", "volumes", "command", "workdir", "group", "alias")


class RunPodError(hosting.HostingError):
    """RunPod refused or failed a request."""


def _detail(response: requests.Response) -> str:
    """RunPod's reason for a refused request, from its error JSON or else the start of the body."""
    try:
        body = response.json()
    except ValueError:
        return response.text.strip()[:300]
    if isinstance(body, dict):
        found = body.get("error") or body.get("message") or body.get("detail") or body.get("errors")
    else:
        found = body
    if isinstance(found, list):
        found = "; ".join(str(item.get("message", item)) if isinstance(item, dict) else str(item) for item in found)
    return str(found or "")[:300]


class RunPodClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        try:
            response = requests.request(
                method,
                self._base_url + path,
                json=body,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            raise RunPodError("RunPod could not be reached") from e
        if response.status_code >= 400:
            detail = _detail(response)
            logger.warning("runpod %s %s failed status=%s %s", method, path, response.status_code, detail)
            raise RunPodError(f"RunPod answered {response.status_code}: {detail}".rstrip(": "), response.status_code)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as e:
            raise RunPodError("RunPod sent a response that is not JSON") from e

    def list_pods(self) -> list[dict]:
        return self._request("GET", "/pods") or []

    def get_pod(self, pod_id: str) -> dict | None:
        try:
            return self._request("GET", f"/pods/{quote(pod_id, safe='')}")
        except RunPodError as e:
            if e.status == 404:
                return None
            raise

    def create_pod(self, body: dict) -> dict:
        return self._request("POST", "/pods", body)

    def update_pod(self, pod_id: str, body: dict) -> dict:
        return self._request("PATCH", f"/pods/{quote(pod_id, safe='')}", body)

    def start_pod(self, pod_id: str) -> Any:
        return self._request("POST", f"/pods/{quote(pod_id, safe='')}/start")

    def stop_pod(self, pod_id: str) -> Any:
        return self._request("POST", f"/pods/{quote(pod_id, safe='')}/stop")

    def delete_pod(self, pod_id: str) -> Any:
        return self._request("DELETE", f"/pods/{quote(pod_id, safe='')}")


def proxy_url(pod_id: str, port: int, path: str) -> str:
    """The public HTTPS address RunPod gives an http port of a pod."""
    return f"https://{pod_id}-{port}.proxy.runpod.net{path}"


class RunPodProvider:
    """The runpod hosting provider: pods on the org's RunPod account, with the org secret runpod_api_key."""

    name = "runpod"
    title = "RunPod"
    integration = "runpod"
    godfather = True

    def configured(self, db, org_id: int | None) -> bool:
        return org_id is not None and bool(secrets.get_secret(db, org_id, SECRET_NAME))

    def client(self, db, org_id: int | None) -> RunPodClient:
        key = secrets.get_secret(db, org_id, SECRET_NAME) if org_id is not None else None
        if not key:
            raise hosting.ProviderError(f"This organization has no RunPod API key (org secret {SECRET_NAME})", 400)
        return RunPodClient(key)

    def status(self, pod: dict | None) -> str:
        if pod is None:
            return "GONE"
        return str(pod.get("status") or pod.get("desiredStatus") or "UNKNOWN")

    def machine(self, pod: dict | None) -> dict | None:
        """The pod's hardware and data center, from the v2 pod fields."""
        if not pod:
            return None
        if isinstance(pod.get("machine"), dict):
            return pod["machine"]
        gpu, cpu = pod.get("gpu") or {}, pod.get("cpu") or {}
        machine = {
            "gpuTypeId": gpu.get("id") if isinstance(gpu, dict) else None,
            "cpuTypeId": cpu.get("id") if isinstance(cpu, dict) else None,
            "dataCenterId": pod.get("dataCenterId"),
        }
        return {k: v for k, v in machine.items() if v} or None

    def ssh_address(self, pod: dict) -> tuple[str, int] | None:
        """(host, port) of a running pod's SSH port, from either shape RunPod reports."""
        mappings = pod.get("portMappings")
        if isinstance(mappings, dict) and pod.get("publicIp") and mappings.get("22"):
            return str(pod["publicIp"]), int(mappings["22"])
        direct = (pod.get("ssh") or {}).get("direct")
        if isinstance(direct, dict) and direct.get("host") and direct.get("port"):
            return str(direct["host"]), int(direct["port"])
        runtime = pod.get("runtime") or {}
        for port in runtime.get("ports") or []:
            private = port.get("private", port.get("privatePort"))
            if private == 22 and port.get("ip") and port.get("isIpPublic", True):
                return str(port["ip"]), int(port.get("public") or port.get("publicPort") or 22)
        return None

    def proxy_url(self, pod_id: str, port: int, path: str) -> str:
        return proxy_url(pod_id, port, path)

    def healthy(self, pod_id: str, port: int, path: str | None) -> bool:
        if path is None:
            return False
        try:
            return requests.get(proxy_url(pod_id, port, path), timeout=10).status_code < 400
        except requests.RequestException:
            return False

    def validate(self, manifest: dict) -> None:
        if ("gpu" in manifest) == ("cpu" in manifest):
            raise hosting.HostingError("A RunPod app needs gpu or cpu, not both")
        if "path" not in manifest.get("health", {}):
            raise hosting.HostingError("A RunPod app needs a health path; tcp checks are for This server")
        used = [field for field in SERVER_ONLY if field in manifest]
        if used:
            raise hosting.HostingError(f"RunPod does not take {', '.join(used)}; those fields are for This server")

    def request(self, app_name: str, org_prefix: str | None, pod_id: str | None, manifest: dict, image: str, env: dict):
        """The RunPod v2 call: POST /pods for a new pod, PATCH /pods/<id> to change one."""
        body: dict[str, Any] = {"image": image, "env": env}
        for field in ("disk", "ports", "args", "registry"):
            if field in manifest:
                body[field] = manifest[field]
        if pod_id:
            return "PATCH", f"/pods/{pod_id}", body
        body["name"] = f"{org_prefix}-{app_name}"
        for field in ("gpu", "cpu", "cloud", "dataCenterIds", "mounts"):
            if field in manifest:
                body[field] = manifest[field]
        return "POST", "/pods", body


hosting.register(RunPodProvider())


def _test(db, org_id: int) -> str:
    key = secrets.get_secret(db, org_id, SECRET_NAME)
    if not key:
        raise IntegrationError("Set the RunPod API key first")
    try:
        pods = RunPodClient(key).list_pods()
    except RunPodError as e:
        raise IntegrationError(e.args[0]) from e
    return f"Connected. {len(pods)} pods on the account."


register(
    Integration(
        key="runpod",
        title="RunPod",
        description="Connect the org's RunPod account.",
        fields=(Field(SECRET_NAME, "API key", "RunPod > Settings > API Keys, with read and write access."),),
        docs="modules/godfather",
        test=_test,
    )
)
