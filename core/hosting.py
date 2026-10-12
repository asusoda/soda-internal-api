"""Hosting providers: the clouds an org runs Godfather pods and apps on. No Flask here.

A provider gives an org a client for its own account, tells whether the org configured it, and reads the
provider's pod shape: status, hardware, SSH address and public URL of a port. Modules store the provider
name with each pod and app and call get() with it. A module in PROVIDER_MODULES calls register() when it
is imported. The providers are RunPod (core/integrations/runpod.py), on the org's own account, and This server
(core/integrations/server.py), capped containers on the deployment's server.
"""

import importlib
from typing import Any, Protocol

from core.errors import ServiceError

DEFAULT = "runpod"


class HostingError(RuntimeError):
    """A provider refused or failed a request. status is the provider's HTTP status, or None."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.message = message
        self.status = status


class ProviderError(ServiceError):
    """The provider name is unknown, or the org has not configured the provider."""


class HostingClient(Protocol):
    """The calls Godfather and hosting make on an org's provider account. The pod dicts are the provider's own."""

    def list_pods(self) -> list[dict]: ...

    def get_pod(self, pod_id: str) -> dict | None: ...

    def create_pod(self, body: dict) -> dict: ...

    def update_pod(self, pod_id: str, body: dict) -> Any: ...

    def start_pod(self, pod_id: str) -> Any: ...

    def stop_pod(self, pod_id: str) -> Any: ...

    def delete_pod(self, pod_id: str) -> Any: ...


class HostingProvider(Protocol):
    """One hosting provider. name is the key stored with pods and apps."""

    name: str
    title: str
    # The key in core.integrations.registry where an org saves its keys for this provider, or "" for none
    integration: str
    # Whether Godfather can run member pods here: they need an SSH address
    godfather: bool

    def configured(self, db, org_id: int | None) -> bool:
        """Whether the org saved the keys this provider needs. org_id None is the deployment, for shared apps."""
        ...

    def client(self, db, org_id: int | None) -> HostingClient:
        """A client for the org's account. Raises ProviderError with status 400 when the org has no keys."""
        ...

    def status(self, pod: dict | None) -> str:
        """RUNNING, EXITED, GONE (pod is None), UNKNOWN, or another upper-case state of the provider."""
        ...

    def machine(self, pod: dict | None) -> dict | None:
        """The pod's hardware and location, or None."""
        ...

    def ssh_address(self, pod: dict) -> tuple[str, int] | None:
        """(host, port) of a running pod's SSH port, or None when it has none yet."""
        ...

    def proxy_url(self, pod_id: str, port: int, path: str) -> str:
        """The address of an http port of a pod that Platform can reach. Raises HostingError when there is none."""
        ...

    def healthy(self, pod_id: str, port: int, path: str | None) -> bool:
        """Whether the pod answers path on port with a status below 400. path None checks that the port accepts a
        connection."""
        ...

    def validate(self, manifest: dict) -> None:
        """Raise HostingError when the app manifest has fields this provider cannot run, or lacks one it needs."""
        ...

    def request(
        self, app_name: str, org_prefix: str | None, pod_id: str | None, manifest: dict, image: str, env: dict
    ) -> tuple[str, str, dict]:
        """The call a deploy makes, as (method, path, body): create the pod, or change the one in pod_id."""
        ...


PROVIDERS: dict[str, HostingProvider] = {}
# Importing these registers their providers
PROVIDER_MODULES = ["core.integrations.runpod", "core.integrations.server"]


def register(provider: HostingProvider) -> None:
    PROVIDERS[provider.name] = provider


def load() -> None:
    """Import every provider module, so each provider and its integration are registered."""
    for name in PROVIDER_MODULES:
        importlib.import_module(name)


def get(name: object) -> HostingProvider:
    """The provider with this name. Raises ProviderError with status 400 for an unknown name."""
    load()
    provider = PROVIDERS.get(name) if isinstance(name, str) else None
    if provider is None:
        known = ", ".join(sorted(PROVIDERS)) or "none"
        raise ProviderError(f"provider must be one of: {known}")
    return provider


def listing(db, org_id: int) -> list[dict]:
    """Each provider with its title, its integration key and whether the org configured it."""
    load()
    return [
        {"name": p.name, "title": p.title, "integration": p.integration, "configured": p.configured(db, org_id)}
        for p in sorted(PROVIDERS.values(), key=lambda p: p.title.lower())
    ]
