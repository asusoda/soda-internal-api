"""Pods an org runs on its own hosting provider account for members to SSH into. No Flask here.

Officers create, share, start, stop and terminate pods. Members list the
running pods shared with them and get a short-lived certificate for their own SSH key. Each pod
keeps the name of its provider (core.hosting). Only RunPod gives pods an SSH address, with the org secret
runpod_api_key, shared with the runpod apps module. The default pod image is an org setting;
without one, GODFATHER_POD_IMAGE in Doppler gives it.
"""

import datetime
import secrets as random
from collections.abc import Callable
from typing import Any, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified

from core import hosting, limits, secrets, webhooks
from core.errors import ServiceError
from core.integrations import registry
from core.log import get_logger
from core.time import utcnow
from modules.auth import scopes
from modules.godfather import ssh
from modules.godfather.models import ComputeConnection, ComputeKey, ComputePod
from modules.organizations.models import Organization

hosting.load()
registry.use("runpod", "godfather")

logger = get_logger("godfather")

BACKEND_KEY = "backend"
USER_CA_KEY = "user_ca"
# Env name prefix the pod image reads its SSH keys and setup flag from; part of the pod image contract.
POD_ENV_PREFIX = "GODFATHER_"
DEFAULT_GPU = "NVIDIA RTX A4000"
DEFAULT_CPU_FLAVOR = "cpu3c"
scopes.declare(
    "godfather:manage",
    "Create, list and change the org's Godfather pods, their sessions, files and settings; start, stop, restart or "
    "terminate them",
    uses=("runpod",),
)
webhooks.declare(
    "pod.started", "Pods started", "A pod starts or restarts, by an officer, a tool or its schedule.", "godfather"
)
webhooks.declare(
    "pod.stopped", "Pods stopped", "A pod stops or is terminated, by an officer, a tool or its schedule.", "godfather"
)

ACTIONS = ("start", "stop", "restart", "terminate")
CLOUD_TYPES = ("COMMUNITY", "SECURE")
# RunPod v2 gives a GPU pod a persistent volume of at least this size. A CPU pod has none.
MIN_VOLUME_GB = 10
MAX_ALLOWED_USERS = 500
CONFIG_KEY = "godfather"
# Connections older than this are deleted when a new one is recorded.
CONNECTION_KEEP_DAYS = 90
RECENT_CONNECTIONS = 100
# The most names one request looks up in the member directory.
NAME_LOOKUPS = 50


PODS_LIMIT = "godfather.pods"
limits.declare(
    PODS_LIMIT,
    "godfather",
    "Pods",
    10,
    unit="pods",
    usage=lambda db, org_id: db.query(ComputePod).filter_by(organization_id=org_id).count(),
)


class GodfatherError(ServiceError):
    pass


def announce(org_id: int, name: str, pod_id: str, action: str, by: str) -> None:
    """Send the pod.started or pod.stopped webhook event for an action on a pod."""
    started = action in ("start", "restart")
    verb = {"start": "started", "stop": "stopped", "restart": "restarted", "terminate": "terminated"}[action]
    message = webhooks.Message(
        title=f"Pod {name} {verb}",
        fields=(("Pod", pod_id), ("By", by)),
        color=webhooks.GREEN if started else webhooks.AMBER,
    )
    webhooks.emit(org_id, "pod.started" if started else "pod.stopped", message)


def _provider(name: object) -> hosting.HostingProvider:
    try:
        provider = hosting.get(name)
    except hosting.ProviderError as e:
        raise GodfatherError(e.message, e.status) from e
    if not provider.godfather:
        raise GodfatherError(f"{provider.title} cannot run Godfather pods: they need an SSH address", 400)
    return provider


def _provider_of(row: ComputePod) -> hosting.HostingProvider:
    return _provider(str(row.provider or hosting.DEFAULT))


def _client(db, org_id: int, provider: str = hosting.DEFAULT) -> hosting.HostingClient:
    try:
        return _provider(provider).client(db, org_id)
    except hosting.ProviderError as e:
        raise GodfatherError(e.message, e.status) from e


def _error(e: hosting.HostingError) -> GodfatherError:
    # 400 when the provider refused the request, 424 when the provider failed
    status = 400 if e.status is not None and 400 <= e.status < 500 else 424
    return GodfatherError(e.message, status)


def _call(fn, *args):
    try:
        return fn(*args)
    except hosting.HostingError as e:
        raise _error(e) from e


class _Clients:
    """One client for each provider of an org, made on first use. A given client serves every provider."""

    def __init__(self, db, org_id: int, client: hosting.HostingClient | None = None):
        self._db, self._org_id, self._client = db, org_id, client
        self._made: dict[str, hosting.HostingClient] = {}

    def __call__(self, row: ComputePod) -> hosting.HostingClient:
        if self._client is not None:
            return self._client
        name = str(row.provider or hosting.DEFAULT)
        if name not in self._made:
            self._made[name] = _client(self._db, self._org_id, name)
        return self._made[name]


def keypair(db, org_id: int, kind: str) -> tuple[str, str]:
    """The org's (public, private) key pair of this kind, created on first use. Commits when created."""
    row = db.query(ComputeKey).filter_by(organization_id=org_id, kind=kind).first()
    if row is None:
        public, private = ssh.generate_keypair(f"platform-{kind}-{org_id}")
        encrypted = secrets.encrypt(private)
        if encrypted is None:
            raise GodfatherError("SECRETS_KEY is not configured on this server", 503)
        db.add(ComputeKey(organization_id=org_id, kind=kind, public_key=public, private_key=encrypted))
        try:
            db.commit()
        except IntegrityError:
            # Another request created it first; use that one
            db.rollback()
        row = db.query(ComputeKey).filter_by(organization_id=org_id, kind=kind).one()
    private = secrets.decrypt(str(row.private_key))
    if private is None:
        raise GodfatherError("SECRETS_KEY cannot decrypt this organization's SSH keys", 503)
    return str(row.public_key), private


def _find(db, org_id: int, pod_id: str) -> ComputePod:
    row = db.query(ComputePod).filter_by(organization_id=org_id, pod_id=pod_id).first()
    if row is None:
        raise GodfatherError("Pod not found", 404)
    return row


def _status(live: dict | None, provider: str = hosting.DEFAULT) -> str:
    return _provider(provider).status(live)


def _ssh_address(row: ComputePod, live: object) -> tuple[str, int]:
    provider = _provider_of(row)
    address = provider.ssh_address(cast(dict, live))
    if address is None:
        raise GodfatherError(
            f"{provider.title} has not given the pod an SSH address yet. Wait a minute and try again", 503
        )
    return address


def _pod_dict(row: ComputePod, live: dict | None) -> dict:
    provider = _provider_of(row)
    return {
        "id": row.pod_id,
        "name": row.name,
        "provider": provider.name,
        "status": provider.status(live),
        "is_public": bool(row.is_public),
        "allowed_users": list(cast(list, row.allowed_users) or []),
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "machine": provider.machine(live),
        "cost_per_hour": (live or {}).get("cost", (live or {}).get("costPerHr")),
    }


def list_pods(db, org_id: int, client: hosting.HostingClient | None = None) -> list[dict]:
    """Every pod the org created here, with its live status from its provider."""
    rows = db.query(ComputePod).filter_by(organization_id=org_id).order_by(ComputePod.created_at).all()
    clients = _Clients(db, org_id, client)
    return [_pod_dict(row, _call(clients(row).get_pod, str(row.pod_id))) for row in rows]


def get_pod(db, org_id: int, pod_id: str, client: hosting.HostingClient | None = None) -> dict:
    row = _find(db, org_id, pod_id)
    client = client or _client(db, org_id, str(row.provider))
    return _pod_dict(row, _call(client.get_pod, pod_id))


def _users(value: object) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_ALLOWED_USERS:
        raise GodfatherError(f"allowed_users must be a list of at most {MAX_ALLOWED_USERS} Discord ids")
    users = [str(v) for v in value]
    if not all(u.isdigit() and 5 <= len(u) <= 25 for u in users):
        raise GodfatherError("allowed_users must hold Discord ids")
    return sorted(set(users))


def _int(data: dict, key: str, default: int, low: int, high: int) -> int:
    value = data.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise GodfatherError(f"{key} must be a whole number from {low} to {high}")
    return value


def _text(data: dict, key: str, default: str, limit: int = 200) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise GodfatherError(f"{key} must be text of at most {limit} characters")
    return value.strip()


def pod_request(data: dict, backend_public: str, ca_public: str, image: str) -> tuple[dict, dict]:
    """The RunPod create body and the settings recorded with the pod, from an officer's request.

    image is the default when the request names none.
    """
    cpu = bool(data.get("use_cpu_only", False))
    cloud = _text(data, "cloud_type", "COMMUNITY")
    if cloud not in CLOUD_TYPES:
        raise GodfatherError("cloud_type must be COMMUNITY or SECURE")
    env = data.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise GodfatherError("env must map names to text")
    if any(k.startswith(POD_ENV_PREFIX) for k in env):
        raise GodfatherError(f"env names starting with {POD_ENV_PREFIX} are reserved")
    volume = 0 if cpu else _int(data, "volume_in_gb", 0, 0, 2000)
    if 0 < volume < MIN_VOLUME_GB:
        raise GodfatherError(f"volume_in_gb must be 0 or from {MIN_VOLUME_GB} to 2000")
    settings = {
        "name": _text(data, "name", f"pod-{random.token_hex(4)}", 100),
        "image_name": _text(data, "image_name", image),
        "cloud_type": cloud,
        "use_cpu_only": cpu,
        "volume_in_gb": volume,
        "container_disk_in_gb": _int(data, "container_disk_in_gb", 20, 1, 500),
        "volume_mount_path": _text(data, "volume_mount_path", "/workspace"),
        "env_names": sorted(env),
    }
    body: dict[str, Any] = {
        "name": settings["name"],
        "image": settings["image_name"],
        "cloud": cloud,
        "disk": settings["container_disk_in_gb"],
        "ports": ["22/tcp"],
        "env": {
            **env,
            f"{POD_ENV_PREFIX}SSH_PUBLIC_KEY": backend_public,
            f"{POD_ENV_PREFIX}SSH_CA_PUBLIC_KEY": ca_public,
            f"{POD_ENV_PREFIX}SETUP": "true",
        },
    }
    if cpu:
        settings["cpu_flavor"] = _text(data, "cpu_flavor", DEFAULT_CPU_FLAVOR, 50)
        vcpus = _int(data, "vcpu_count", 2, 2, 64)
        if vcpus & (vcpus - 1):
            raise GodfatherError("vcpu_count must be a power of two")
        settings["vcpu_count"] = vcpus
        body["cpu"] = {"id": settings["cpu_flavor"], "vcpuCount": vcpus}
    else:
        settings["gpu_type_id"] = _text(data, "gpu_type_id", DEFAULT_GPU, 100)
        body["gpu"] = {"id": settings["gpu_type_id"], "count": 1}
        if settings["volume_in_gb"]:
            body["mounts"] = {"persistent": {"size": settings["volume_in_gb"], "path": settings["volume_mount_path"]}}
    return body, settings


def _org(db, org_id: int) -> Organization:
    org = db.query(Organization).filter_by(id=org_id).first()
    if org is None:
        raise GodfatherError("No such organization", 404)
    return org


def godfather_settings(db, org_id: int, deployment_image: str) -> dict:
    """The org's default pod image, or None, and the deployment default it falls back to."""
    saved = (cast(dict, _org(db, org_id).config) or {}).get(CONFIG_KEY) or {}
    return {"pod_image": saved.get("pod_image"), "deployment_pod_image": deployment_image}


def pod_image(db, org_id: int, deployment_image: str) -> str:
    """The image a new pod gets when the request names none."""
    return godfather_settings(db, org_id, deployment_image)["pod_image"] or deployment_image


def update_godfather_settings(db, org_id: int, data: object, deployment_image: str) -> dict:
    """Set the org's default pod image. null or an empty string goes back to the deployment default. Commits."""
    if not isinstance(data, dict) or set(data) - {"pod_image"}:
        raise GodfatherError("Send an object with pod_image")
    value = cast(dict, data).get("pod_image")
    if value is not None and not isinstance(value, str):
        raise GodfatherError("pod_image must be a string")
    value = (value or "").strip()
    if len(value) > 200 or any(c.isspace() for c in value):
        raise GodfatherError("pod_image must be an image name of at most 200 characters, with no spaces")
    org = _org(db, org_id)
    config = dict(cast(dict, org.config) or {})
    current = {k: v for k, v in (config.get(CONFIG_KEY) or {}).items() if k != "pod_image"}
    config[CONFIG_KEY] = current | ({"pod_image": value} if value else {})
    org.config = config
    flag_modified(org, "config")
    db.commit()
    return godfather_settings(db, org_id, deployment_image)


def create_pod(
    db,
    org_id: int,
    data: object,
    creator: str | None,
    image: str,
    client: hosting.HostingClient | None = None,
) -> dict:
    """Create a pod on the org's provider account and record it, from image unless the request names one. Commits.

    provider names the hosting provider, runpod when missing. The create body follows the RunPod v2 API.
    """
    if not isinstance(data, dict):
        raise GodfatherError("Send a JSON object")
    data = cast(dict, data)
    limits.check(db, org_id, PODS_LIMIT)
    provider = _provider(data.get("provider", hosting.DEFAULT))
    client = client or _client(db, org_id, provider.name)
    backend_public, _ = keypair(db, org_id, BACKEND_KEY)
    ca_public, _ = keypair(db, org_id, USER_CA_KEY)
    body, settings = pod_request(data, backend_public, ca_public, image)
    allowed = _users(data.get("allowed_users", []))
    created = _call(client.create_pod, body)
    if not isinstance(created, dict) or not created.get("id"):
        raise GodfatherError(f"{provider.title} did not return a pod id", 424)
    row = ComputePod(
        organization_id=org_id,
        pod_id=str(created["id"]),
        provider=provider.name,
        name=settings["name"],
        is_public=bool(data.get("is_public", False)),
        allowed_users=allowed,
        config=settings,
        created_by=creator,
    )
    db.add(row)
    db.commit()
    logger.info("Godfather pod created org=%s pod=%s by=%s", org_id, row.pod_id, creator)
    return _pod_dict(row, created)


def update_pod(db, org_id: int, pod_id: str, data: object) -> dict:
    """Change who may connect: is_public and allowed_users. Commits."""
    if not isinstance(data, dict) or not ({"is_public", "allowed_users"} & set(data)):
        raise GodfatherError("Send is_public or allowed_users")
    data = cast(dict, data)
    row = _find(db, org_id, pod_id)
    if "is_public" in data:
        if not isinstance(data["is_public"], bool):
            raise GodfatherError("is_public must be true or false")
        row.is_public = data["is_public"]
    if "allowed_users" in data:
        row.allowed_users = _users(data["allowed_users"])
    db.commit()
    return _pod_dict(row, None) | {"status": None}


def act(db, org_id: int, pod_id: str, action: object, client: hosting.HostingClient | None = None) -> dict:
    """Start, stop, restart or terminate a pod. Terminate also forgets it. Commits."""
    if action not in ACTIONS:
        raise GodfatherError(f"action must be one of {', '.join(ACTIONS)}")
    row = _find(db, org_id, pod_id)
    name = str(row.name)
    client = client or _client(db, org_id, str(row.provider))
    if action == "start":
        _call(client.start_pod, pod_id)
    elif action == "stop":
        _call(client.stop_pod, pod_id)
    elif action == "restart":
        _call(client.stop_pod, pod_id)
        _call(client.start_pod, pod_id)
    else:
        try:
            client.delete_pod(pod_id)
        except hosting.HostingError as e:
            # A pod already deleted on the provider is forgotten here too
            if e.status != 404:
                raise _error(e) from e
            logger.info("Godfather pod already gone on %s org=%s pod=%s", row.provider, org_id, pod_id)
        from modules.godfather.schedule import delete_pod_sessions

        delete_pod_sessions(db, org_id, pod_id)
        db.query(ComputeConnection).filter_by(organization_id=org_id, pod_id=pod_id).delete()
        db.delete(row)
        db.commit()
    logger.info("Godfather pod %s org=%s pod=%s", action, org_id, pod_id)
    announce(org_id, name, pod_id, str(action), "an officer or a tool")
    return {"id": pod_id, "action": action}


def member_page(directory, guild_id, query: str = "", role: str = "", limit: int = 50) -> dict:
    """Server members for the allowed members picker, sorted by name. Bots are left out.

    A query searches names through Discord. Without one, the whole member list is read. role keeps the members
    that hold that role. total counts every match; members holds the first limit.
    """
    if query:
        found = directory.search_members(guild_id, query, 100)
    else:
        found = directory.list_members(guild_id)
    matches = [m for m in found if not m.get("bot") and (not role or role in m.get("roles", []))]
    matches.sort(key=lambda m: (str(m["name"]).casefold(), m["id"]))
    return {"members": matches[:limit], "total": len(matches)}


def _may_connect(row: ComputePod, discord_id: str) -> bool:
    return bool(row.is_public) or discord_id in (cast(list, row.allowed_users) or [])


def accessible_pods(db, org_id: int, discord_id: str, client: hosting.HostingClient | None = None) -> list[dict]:
    """Running pods this member may connect to."""
    rows = [r for r in db.query(ComputePod).filter_by(organization_id=org_id) if _may_connect(r, discord_id)]
    if not rows:
        return []
    clients = _Clients(db, org_id, client)
    found = []
    for row in rows:
        live = _call(clients(row).get_pod, str(row.pod_id))
        if _status(live, str(row.provider)) == "RUNNING":
            found.append({"id": row.pod_id, "name": row.name, "status": "RUNNING", "is_public": bool(row.is_public)})
    return found


def connect(
    db,
    org_id: int,
    pod_id: str,
    discord_id: str,
    username: str,
    is_admin: bool,
    public_key: object,
    client: hosting.HostingClient | None = None,
) -> dict:
    """SSH details and a certificate for the caller's own key. Officers get root."""
    if not ssh.is_valid_public_key(public_key):
        raise GodfatherError("A valid SSH public key is required")
    row = _find(db, org_id, pod_id)
    if not is_admin and not _may_connect(row, discord_id):
        raise GodfatherError("Pod not accessible", 403)
    client = client or _client(db, org_id, str(row.provider))
    live = _call(client.get_pod, pod_id)
    if _status(live, str(row.provider)) != "RUNNING":
        raise GodfatherError("Pod is not running", 409)
    address = _ssh_address(row, live)
    _, ca_private = keypair(db, org_id, USER_CA_KEY)
    user = ssh.safe_username(username or discord_id)
    certificate = ssh.sign_user_key(ca_private, cast(str, public_key), pod_id, discord_id, user, is_admin)
    record_connection(db, org_id, pod_id, discord_id, user, is_admin)
    logger.info("godfather certificate org=%s pod=%s discord_id=%s admin=%s", org_id, pod_id, discord_id, is_admin)
    return {
        "host": address[0],
        "port": address[1],
        "username": "root",
        "user_folder": user,
        "is_admin": is_admin,
        "certificate": certificate,
    }


def pod_files(db, org_id: int, pod_id: str, client: hosting.HostingClient | None = None, opener=None):
    """An open SFTP session on a running pod, as root with the org's backend key."""
    from modules.godfather.files import PodFiles

    row = _find(db, org_id, pod_id)
    client = client or _client(db, org_id, str(row.provider))
    live = _call(client.get_pod, pod_id)
    if _status(live, str(row.provider)) != "RUNNING":
        raise GodfatherError("Pod is not running", 409)
    address = _ssh_address(row, live)
    _, backend_private = keypair(db, org_id, BACKEND_KEY)
    return (opener or PodFiles.open)(address[0], address[1], backend_private)


def record_connection(db, org_id: int, pod_id: str, discord_id: str, username: str, is_admin: bool) -> None:
    """Record a certificate issued for a pod and delete the org's connections older than CONNECTION_KEEP_DAYS."""
    db.add(
        ComputeConnection(
            organization_id=org_id, pod_id=pod_id, discord_id=discord_id, username=username, is_admin=is_admin
        )
    )
    cutoff = utcnow() - datetime.timedelta(days=CONNECTION_KEEP_DAYS)
    db.query(ComputeConnection).filter(
        ComputeConnection.organization_id == org_id, ComputeConnection.created_at < cutoff
    ).delete(synchronize_session=False)
    db.commit()


def _named(ids: list[str], name_of: Callable[[str], str | None] | None) -> dict[str, str | None]:
    """Display names for the first NAME_LOOKUPS ids. The others, and ids name_of does not know, get None."""
    names: dict[str, str | None] = dict.fromkeys(ids)
    if name_of is not None:
        for discord_id in ids[:NAME_LOOKUPS]:
            names[discord_id] = name_of(discord_id)
    return names


def _recent(db, org_id: int, pod_id: str) -> list[ComputeConnection]:
    query = db.query(ComputeConnection).filter_by(organization_id=org_id, pod_id=pod_id)
    return (
        query.order_by(ComputeConnection.created_at.desc(), ComputeConnection.id.desc()).limit(RECENT_CONNECTIONS).all()
    )


def pod_members(db, org_id: int, pod_id: str, name_of: Callable[[str], str | None] | None = None) -> dict:
    """Who may connect to a pod and who got a certificate for it, newest first.

    name_of gives a member's display name from a Discord id, or None.
    """
    row = _find(db, org_id, pod_id)
    allowed = list(cast(list, row.allowed_users) or [])
    recent = _recent(db, org_id, pod_id)
    ids = list(dict.fromkeys([*(str(c.discord_id) for c in recent), *allowed]))
    names = _named(ids, name_of)
    return {
        "pod_id": pod_id,
        "access": {
            "is_public": bool(row.is_public),
            "allowed": [{"discord_id": i, "name": names.get(i)} for i in allowed],
        },
        "recent": [
            {
                "discord_id": c.discord_id,
                "name": names.get(str(c.discord_id)),
                "username": c.username,
                "is_admin": bool(c.is_admin),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in recent
        ],
    }


def connected_now(
    db,
    org_id: int,
    pod_id: str,
    name_of: Callable[[str], str | None] | None = None,
    client: hosting.HostingClient | None = None,
    reader: Callable[[str, int, str], list[dict]] | None = None,
) -> dict:
    """The live SSH sessions on a pod. state is known or unknown; an unknown state has a reason and no sessions.

    reader takes host, port and the backend private key and returns the sessions from presence.sessions.
    """
    from modules.godfather import presence

    row = _find(db, org_id, pod_id)
    try:
        live = _call((client or _client(db, org_id, str(row.provider))).get_pod, pod_id)
        if _status(live, str(row.provider)) != "RUNNING":
            return {"pod_id": pod_id, "state": "unknown", "reason": "The pod is not running", "sessions": []}
        address = _provider_of(row).ssh_address(cast(dict, live))
        if address is None:
            return {"pod_id": pod_id, "state": "unknown", "reason": "The pod has no SSH address yet", "sessions": []}
        _, backend_private = keypair(db, org_id, BACKEND_KEY)
        found = (reader or presence.sessions)(address[0], address[1], backend_private)
    except ServiceError as e:
        logger.info("godfather presence unknown org=%s pod=%s: %s", org_id, pod_id, e.message)
        return {"pod_id": pod_id, "state": "unknown", "reason": e.message, "sessions": []}
    # A username maps to the member who last got a certificate with it for this pod
    owners: dict[str, str] = {}
    for c in reversed(_recent(db, org_id, pod_id)):
        owners[str(c.username)] = str(c.discord_id)
    names = _named(list(dict.fromkeys(owners[s["username"]] for s in found if s["username"] in owners)), name_of)
    sessions = [
        s | {"discord_id": owners.get(s["username"]), "name": names.get(owners.get(s["username"], ""))} for s in found
    ]
    return {"pod_id": pod_id, "state": "known", "reason": None, "sessions": sessions}
