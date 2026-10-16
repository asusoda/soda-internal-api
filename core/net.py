"""Checks that a URL names a public host, so a URL from a user cannot make the server reach its own network.

get() and post() connect only to an address that passed the check. A second DNS answer cannot move the connection
to a private address.
"""

import ipaddress
import socket
import threading
from typing import Any
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NameResolutionError, NewConnectionError
from urllib3.poolmanager import PoolManager
from urllib3.util.connection import create_connection


class NotPublic(ValueError):
    """The URL is not http(s), or its host resolves to a non-public address."""


class NoHost(ValueError):
    """The host of the URL does not resolve."""


def public_addresses(host: str, port: int) -> list[str]:
    """The addresses of host, after a check that each one is public. Raises NoHost or NotPublic.

    Connect to one of these, not to the host name: a second lookup can give another address.
    """
    try:
        infos = socket.getaddrinfo(host, port)
    except socket.gaierror as e:
        raise NoHost(f"{host} does not resolve") from e
    addresses = [str(info[4][0]).split("%")[0] for info in infos]
    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise NotPublic(f"{host} resolves to a non-public address")
    if not addresses:
        raise NoHost(f"{host} does not resolve")
    return addresses


def check_public(url: str) -> None:
    """Raise NotPublic unless url is http(s) on a host that resolves only to public addresses."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise NotPublic(f"Only http and https URLs are allowed: {url}")
    public_addresses(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))


def _connect_public(connection: HTTPConnection) -> socket.socket:
    """A socket to the first public address of the connection's host that accepts. TLS still uses the host name."""
    host, port = connection.host, connection.port
    try:
        addresses = public_addresses(host, port)
    except NoHost as e:
        raise NameResolutionError(host, connection, socket.gaierror(str(e))) from e
    error: OSError | None = None
    for address in dict.fromkeys(addresses):
        try:
            return create_connection(
                (address, port),
                connection.timeout,
                source_address=connection.source_address,
                socket_options=connection.socket_options,
            )
        except TimeoutError as e:
            raise ConnectTimeoutError(
                connection, f"Connection to {host} timed out. (connect timeout={connection.timeout})"
            ) from e
        except OSError as e:
            error = e
    raise NewConnectionError(connection, f"Failed to establish a new connection: {error}")


class _PublicHTTPConnection(HTTPConnection):
    def _new_conn(self) -> socket.socket:
        return _connect_public(self)


class _PublicHTTPSConnection(HTTPSConnection):
    def _new_conn(self) -> socket.socket:
        return _connect_public(self)


class _PublicHTTPPool(HTTPConnectionPool):
    ConnectionCls = _PublicHTTPConnection


class _PublicHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _PublicHTTPSConnection


class _PublicPoolManager(PoolManager):
    """A pool manager whose pools open connections with _connect_public."""

    pool_classes_by_scheme: dict[str, type[HTTPConnectionPool]]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.pool_classes_by_scheme = {"http": _PublicHTTPPool, "https": _PublicHTTPSPool}


class _PublicAdapter(HTTPAdapter):
    """An adapter whose connections check the host's addresses and connect to one that passed."""

    def init_poolmanager(self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: Any) -> None:
        super().init_poolmanager(connections, maxsize, block, **pool_kwargs)
        self.poolmanager = _PublicPoolManager(num_pools=connections, maxsize=maxsize, block=block, **pool_kwargs)


_local = threading.local()


def _session() -> requests.Session:
    """A session for this thread that reaches public addresses only. It uses no proxy from the environment."""
    session = getattr(_local, "session", None)
    if session is None:
        session = requests.Session()
        session.trust_env = False
        session.mount("http://", _PublicAdapter())
        session.mount("https://", _PublicAdapter())
        _local.session = session
    return session


def get(url: str, **kwargs: Any) -> requests.Response:
    """requests.get to a public address only. Raises NotPublic or a requests.RequestException."""
    return _session().get(url, **kwargs)


def post(url: str, **kwargs: Any) -> requests.Response:
    """requests.post to a public address only. Raises NotPublic or a requests.RequestException."""
    return _session().post(url, **kwargs)
