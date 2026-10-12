"""Checks that a URL names a public host, so a URL from a user cannot make the server reach its own network."""

import ipaddress
import socket
from urllib.parse import urlsplit


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
