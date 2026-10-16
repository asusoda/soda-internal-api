"""core.net: requests to a URL from a user connect only to an address that passed the public check."""

import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from core import net

REAL_GETADDRINFO = socket.getaddrinfo
# The Host header of each request that the test server answered
HOSTS: list[str] = []


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        HOSTS.append(str(self.headers.get("Host")))
        body = b'{"results": []}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.do_GET()

    def log_message(self, format, *args):
        pass


@pytest.fixture
def server():
    """An HTTP server on 127.0.0.1 that records the Host header of each request."""
    HOSTS.clear()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def rebind(monkeypatch):
    """rebind.test resolves to a public address the first time and to 127.0.0.1 after that."""
    calls = {"count": 0}

    def getaddrinfo(host, port, *args, **kwargs):
        if host != "rebind.test":
            return REAL_GETADDRINFO(host, port, *args, **kwargs)
        calls["count"] += 1
        address = "93.184.216.34" if calls["count"] == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("no_proxy", "*")
    return calls


def test_connection_uses_the_checked_address(server, monkeypatch):
    port = server.server_address[1]

    def public_addresses(host, port):
        assert host == "pinned.test"
        return ["127.0.0.1"]

    def getaddrinfo(host, port, *args, **kwargs):
        if host == "pinned.test":
            raise socket.gaierror("a second lookup of pinned.test")
        return REAL_GETADDRINFO(host, port, *args, **kwargs)

    monkeypatch.setattr(net, "public_addresses", public_addresses)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    response = net.get(f"http://pinned.test:{port}/", timeout=5)
    assert response.status_code == 200
    assert HOSTS == [f"pinned.test:{port}"]


def test_get_refuses_a_private_address():
    with pytest.raises(net.NotPublic):
        net.get("http://127.0.0.1:9/", timeout=5)


def test_uptime_probe_refuses_a_rebound_address(server, rebind):
    from modules.uptime import probe

    result = probe.fetch(f"http://rebind.test:{server.server_address[1]}/", 5)
    assert result.status_code is None and "non-public" in (result.error or "")
    assert HOSTS == []


def test_knowledge_fetch_refuses_a_rebound_address(server, rebind):
    from modules.knowledge import fetch

    with pytest.raises(fetch.FetchRejected):
        fetch.fetch_http(f"http://rebind.test:{server.server_address[1]}/")
    assert HOSTS == []


def test_firecrawl_of_an_org_refuses_a_rebound_address(server, rebind):
    from modules.knowledge import fetch

    firecrawl = fetch.Firecrawl(f"http://rebind.test:{server.server_address[1]}", public_only=True)
    with pytest.raises(fetch.FetchRejected):
        fetch.fetch_firecrawl("https://example.com/", firecrawl)
    assert HOSTS == []


def test_searxng_of_an_org_refuses_a_rebound_address(server, rebind):
    from modules.knowledge import fetch
    from modules.submodules import search

    with pytest.raises(fetch.FetchRejected):
        search.search_json(f"http://rebind.test:{server.server_address[1]}/search?q=x&format=json", True)
    assert HOSTS == []


def test_embedder_of_an_org_refuses_a_rebound_address(server, rebind):
    from modules.knowledge import embedder

    service = embedder.Embedder(url=f"http://rebind.test:{server.server_address[1]}/v1", model="m", public_only=True)
    with pytest.raises(embedder.EmbeddingError):
        service.embed(["text"])
    assert HOSTS == []
