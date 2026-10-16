"""One HTTP check of an address. Each URL and each redirect must resolve to public addresses, and the connection goes
to an address that passed the check. No Flask here."""

import time
from dataclasses import dataclass
from urllib.parse import urljoin

import requests

from core import net

USER_AGENT = "PlatformUptime/1.0"
MAX_REDIRECTS = 5


@dataclass(frozen=True)
class Result:
    """The status of the last response and the time to its headers, or the error when no response came back."""

    status_code: int | None = None
    latency_ms: int | None = None
    error: str | None = None
    # The answer of a provider's own health check, which has no status code
    ok: bool | None = None


def fetch(url: str, timeout: float) -> Result:
    """GET url and follow redirects one at a time, so that net.check_public checks each hop. The body is not read.

    timeout is the limit for all hops together.
    """
    started = time.monotonic()
    for _ in range(MAX_REDIRECTS + 1):
        left = timeout - (time.monotonic() - started)
        if left <= 0:
            return Result(error=f"No answer in {timeout:g} seconds")
        try:
            net.check_public(url)
        except ValueError as e:
            return Result(error=str(e))
        try:
            response = net.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=left, allow_redirects=False, stream=True
            )
        except net.NotPublic as e:
            return Result(error=str(e))
        except requests.Timeout:
            return Result(error=f"No answer in {timeout:g} seconds")
        except requests.RequestException as e:
            return Result(error=f"Could not connect: {type(e).__name__}")
        response.close()
        location = response.headers.get("location")
        if response.is_redirect and location:
            url = urljoin(url, location)
            continue
        return Result(status_code=response.status_code, latency_ms=int((time.monotonic() - started) * 1000))
    return Result(error=f"More than {MAX_REDIRECTS} redirects")


def provider_check(provider, pod_id: str, port: int, check: str | None) -> Result:
    """The app's own health check through its provider, such as the This server runner, timed. check is an HTTP
    path, None for a TCP connect, or "running"."""
    started = time.monotonic()
    ok = provider.healthy(pod_id, port, check)
    latency = int((time.monotonic() - started) * 1000)
    return Result(latency_ms=latency, ok=ok, error=None if ok else "The app's health check failed")
