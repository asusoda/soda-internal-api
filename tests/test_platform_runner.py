"""The This server runner's policy checks (deploy/runner/platform_runner.py), with no podman."""

import pytest

from tests import runner_fake
from tests.runner_fake import POLICY, FakePodman, runner

BODY = {"image": "ghcr.io/example/app:1.0", "memory_mb": 128, "ports": [], "volumes": []}


@pytest.fixture
def policy(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "managed", lambda: [])
    return runner.load_policy_dict({**POLICY, "data_root": str(tmp_path)})


def _refused(policy, org="soda", app="web", **change) -> str:
    with pytest.raises(runner.Refused) as refused:
        runner.check(policy, org, app, {**BODY, **change})
    return refused.value.message


def test_a_host_path_must_be_allowed_for_the_org_also_through_dot_dot(policy):
    escape = "/var/www/vaultwarden/data/../../soda-internal-api"
    assert "not allowed" in _refused(policy, volumes=[{"host": escape, "path": "/x"}])
    assert "not allowed" in _refused(policy, org="ais", volumes=[{"host": "/var/www/vaultwarden/data", "path": "/d"}])
    allowed = runner.check(
        policy, "soda", "vault", {**BODY, "volumes": [{"host": "/var/www/vaultwarden/data", "path": "/data"}]}
    )
    assert allowed["volumes"][0]["host"] == "/var/www/vaultwarden/data"


def test_a_named_volume_lives_under_the_app_folder(policy, tmp_path):
    checked = runner.check(policy, "soda", "web", {**BODY, "volumes": [{"name": "data", "path": "/data"}]})
    assert checked["volumes"][0]["host"] == str(tmp_path / "soda" / "web" / "data")
    assert "absolute path" in _refused(policy, volumes=[{"name": "data", "path": "/a/../../etc"}])


def test_memory_cpu_ports_and_names_are_capped(policy, monkeypatch):
    assert "memory_mb" in _refused(policy, memory_mb=4096)
    assert "cpus" in _refused(policy, cpus=8)
    assert "host port 22" in _refused(policy, ports=[{"container": 22, "host": 22}])
    assert "org" in _refused(policy, org="../etc")
    assert "image" in _refused(policy, image="ghcr.io/example/app")
    used = {"Name": "app-other-big", "HostConfig": {"Memory": 1500 * 1024 * 1024}}
    monkeypatch.setattr(runner, "managed", lambda: [used])
    assert "MB left" in _refused(policy)


def test_a_shared_app_uses_the_shared_section_and_no_org_can(policy, tmp_path):
    shared_vault = {
        **BODY,
        "volumes": [{"host": "/srv/shared/vault", "path": "/data"}],
        "ports": [{"container": 80, "host": 8082}],
    }
    checked = runner.check(policy, None, "vault", shared_vault)
    assert checked["volumes"][0]["host"] == "/srv/shared/vault"
    assert "not allowed" in _refused(policy, org="soda", volumes=[{"host": "/srv/shared/vault", "path": "/d"}])
    assert "host port 8082" in _refused(policy, org="soda", ports=[{"container": 80, "host": 8082}])
    named = runner.check(policy, None, "vault", {**BODY, "volumes": [{"name": "data", "path": "/data"}]})
    assert named["volumes"][0]["host"] == str(tmp_path / ".shared" / "vault" / "data")
    assert runner.container_name(None, "vault") == "shared-vault"


def test_only_a_public_port_of_the_policy_binds_every_address(policy):
    policy["orgs"]["soda"]["host_ports"] = [8081, 8080]
    policy["orgs"]["soda"]["public_ports"] = [8080]
    checked = runner.check(
        policy, "soda", "web", {**BODY, "ports": [{"container": 80, "host": 8080}, {"container": 81, "host": 8081}]}
    )
    assert [(p["host"], p["public"]) for p in checked["ports"]] == [(8080, True), (8081, False)]


def test_a_tcp_health_check_only_needs_the_port_to_accept(monkeypatch):
    import socket

    listener = socket.create_server(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    info = {
        "Name": "app-soda--db",
        "Config": {"Labels": {"platform.managed": "1", "platform.org": "soda", "platform.app": "db"}},
        "HostConfig": {"PortBindings": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(port)}]}},
        "NetworkSettings": {"Networks": {}},
    }
    monkeypatch.setattr(runner, "_inspect", lambda name: info)
    try:
        assert runner.health("soda", "db", 5432, None) == {"ok": True}
    finally:
        listener.close()
    assert runner.health("soda", "db", 5432, None)["ok"] is False


def test_only_a_listed_database_runs_without_no_new_privileges(policy):
    policy["orgs"]["soda"]["no_new_privileges_off"] = ["crm-db"]
    assert runner.check(policy, "soda", "crm-db", BODY)["no_new_privileges"] is False
    assert runner.check(policy, "soda", "crm-server", BODY)["no_new_privileges"] is True
    assert runner.check(policy, "ais", "crm-db", BODY)["no_new_privileges"] is True


def test_a_deploy_counts_memory_again_under_the_lock(policy, monkeypatch):
    seen = {"n": 0}

    def managed():
        seen["n"] += 1
        if seen["n"] == 1:
            return []
        return [{"Name": "app-other-big", "HostConfig": {"Memory": 1500 * 1024 * 1024}}]

    monkeypatch.setattr(runner, "managed", managed)
    monkeypatch.setattr(runner, "ensure_bridge", lambda _policy: None)
    monkeypatch.setattr(runner, "exists", lambda *_args: True)
    ran = []
    monkeypatch.setattr(runner, "podman", lambda *args, **_kw: ran.append(args) or "")
    with pytest.raises(runner.Refused, match="MB left"):
        runner.run(policy, "soda", "web", BODY)
    assert ran == []


def test_the_bridge_container_is_made_once(monkeypatch):
    calls = []
    state = {"exists": False}
    monkeypatch.setattr(runner, "exists", lambda *args: state["exists"])
    monkeypatch.setattr(runner, "podman", lambda *args, **kw: calls.append(args) or "")
    policy = runner.load_policy_dict({"bind_ips": ["127.0.0.1", "10.88.0.1"]})
    runner.ensure_bridge(policy)
    assert calls[0][:4] == ("run", "-d", "--name", "platform-bridge")
    state["exists"] = True
    runner.ensure_bridge(policy)
    assert calls[1] == ("start", "platform-bridge")
    runner.ensure_bridge(runner.load_policy_dict({"bind_ips": ["127.0.0.1"]}))
    assert len(calls) == 2


@pytest.fixture
def podman(monkeypatch, policy):
    """The runner's podman calls on an in-memory fake, with no socket."""
    fake = FakePodman()
    monkeypatch.setattr(runner, "podman", fake.podman)
    monkeypatch.setattr(runner, "exists", fake.exists)
    monkeypatch.setattr(runner, "_inspect", fake.inspect)
    monkeypatch.setattr(runner, "managed", fake.managed)
    monkeypatch.setattr(runner, "ensure_bridge", lambda _policy: None)
    return fake


def _container(name, org, app, ports=(), group=None, network=None):
    labels = {"platform.managed": "1", "platform.org": org, "platform.app": app}
    if group:
        labels["platform.group"] = group
    return {
        "Name": name,
        "Id": name,
        "Config": {"Labels": labels, "Image": "ghcr.io/example/app:0.9"},
        "State": {"Status": "exited"},
        "HostConfig": {"PortBindings": {f"{p}/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(p)}] for p in ports}},
        "NetworkSettings": {"Networks": {network or f"platform-{org}": {"IPAddress": "10.89.0.2"}}},
    }


def test_two_orgs_whose_prefix_and_app_name_join_alike_get_two_containers(podman, policy):
    assert runner.container_name("acm", "w-site") != runner.container_name("acm-w", "site")
    assert runner.network_name("acm", "w") != runner.network_name("acm-w", None)
    runner.run(policy, "acm-w", "site", BODY)
    runner.run(policy, "acm", "w-site", BODY)
    assert podman.containers["app-acm-w--site"]["Config"]["Labels"]["platform.org"] == "acm-w"
    assert podman.containers["app-acm--w-site"]["Config"]["Labels"]["platform.org"] == "acm"


def test_a_deploy_moves_the_apps_legacy_container_to_the_new_name(podman, policy):
    podman.containers["app-soda-web"] = _container("app-soda-web", "soda", "web", ports=[20001])
    moved = runner.run(policy, "soda", "web", {**BODY, "ports": [{"container": 80, "host": 20001}]})
    assert moved["id"] == "app-soda--web" and "app-soda-web" not in podman.containers
    # The old container goes before the new one starts, so the host port is free
    removed = podman.calls.index(("rm", "--force", "app-soda-web"))
    started = next(i for i, call in enumerate(podman.calls) if call[0] == "run")
    assert removed < started


def test_a_deploy_does_not_touch_another_orgs_legacy_container(podman, policy):
    # The legacy name of acm-w's app site is also the legacy name of acm's app w-site
    podman.containers["app-acm-w-site"] = _container("app-acm-w-site", "acm-w", "site")
    runner.run(policy, "acm", "w-site", BODY)
    assert podman.containers["app-acm-w-site"]["Config"]["Labels"]["platform.org"] == "acm-w"
    assert not [call for call in podman.calls if call[0] == "rm"]


def test_a_deploy_refuses_a_new_name_that_another_org_holds(podman, policy):
    # An earlier runner named acm-'s app x app-acm--x, the new name of acm's app x
    podman.containers["app-acm--x"] = _container("app-acm--x", "acm-", "x")
    with pytest.raises(runner.Refused, match="not this app's"):
        runner.run(policy, "acm", "x", BODY)
    assert podman.containers["app-acm--x"]["Config"]["Labels"]["platform.org"] == "acm-"


def test_a_host_port_of_another_orgs_container_is_refused_also_when_it_is_stopped(podman, policy):
    podman.containers["app-ais--web"] = _container("app-ais--web", "ais", "web", ports=[20005])
    with pytest.raises(runner.Refused, match="host port 20005 is in use by an app of another org"):
        runner.run(policy, "soda", "web", {**BODY, "ports": [{"container": 80, "host": 20005}]})
    # The org's own container on that port is replaced
    podman.containers["app-soda--web"] = _container("app-soda--web", "soda", "web", ports=[20006])
    runner.run(policy, "soda", "web", {**BODY, "ports": [{"container": 80, "host": 20006}]})


def test_two_dashes_in_a_row_are_refused_in_an_org_an_app_and_a_group(policy):
    assert "org" in _refused(policy, org="acm--w")
    assert "app" in _refused(policy, app="w--site")
    assert "group" in _refused(policy, group="a--b")
    assert runner.check(policy, "a_b", "w-site", {**BODY, "alias": "db"})["alias"] == "db"


def test_the_group_moves_from_its_legacy_network_part_by_part(podman, policy, monkeypatch):
    members: list[dict] = []
    monkeypatch.setattr(runner, "_network_members", lambda network: members if network == "platform-soda-crm" else [])
    body = {**BODY, "group": "crm", "alias": "server"}

    # The database still runs on the legacy network, so the new server joins it too
    members[:] = [_container("app-soda-crm-db", "soda", "crm-db", group="crm", network="platform-soda-crm")]
    runner.run(policy, "soda", "crm-server", body)
    assert ("network", "connect", "--alias", "server", "platform-soda-crm", "app-soda--crm-server") in podman.calls

    # A container of another org on that network: the runner does not join or change it
    podman.calls.clear()
    members[:] = [_container("app-soda-crm", "soda-crm", "web", network="platform-soda-crm")]
    runner.run(policy, "soda", "crm-server", body)
    assert not [call for call in podman.calls if call[0] == "network" and call[1] != "create"]

    # Every part is on the new network: the legacy network goes
    podman.calls.clear()
    members[:] = [_container("app-soda--crm-db", "soda", "crm-db", group="crm", network="app-soda--crm")]
    runner.run(policy, "soda", "crm-server", body)
    assert ("network", "disconnect", "platform-soda-crm", "app-soda--crm-db") in podman.calls
    assert ("network", "rm", "platform-soda-crm") in podman.calls


@pytest.fixture
def served(tmp_path, monkeypatch):
    """The runner on a socket with a fake podman. Answers (status, body) for a request."""
    import json
    import socket as sockets

    path = str(tmp_path / "runner.sock")
    fake = runner_fake.start(path, monkeypatch)

    def request(method: str, url: str) -> tuple[int, dict]:
        with sockets.socket(sockets.AF_UNIX, sockets.SOCK_STREAM) as conn:
            conn.connect(path)
            conn.sendall(f"{method} {url} HTTP/1.0\r\nContent-Length: 0\r\n\r\n".encode())
            raw = b"".join(iter(lambda: conn.recv(65536), b""))
        head, _, body = raw.partition(b"\r\n\r\n")
        return int(head.split()[1]), json.loads(body)

    yield fake, request
    assert fake.server is not None
    fake.server.shutdown()
    fake.server.server_close()


def test_the_runner_acts_only_on_a_container_whose_labels_name_the_org_of_the_path(served):
    fake, request = served
    # acm-w's app site, with the legacy name that acm's app w-site also has
    fake.containers["app-acm-w-site"] = _container("app-acm-w-site", "acm-w", "site")
    for method, url in [
        ("GET", "/apps/acm/w-site"),
        ("GET", "/apps/acm/w-site/logs"),
        ("POST", "/apps/acm/w-site/stop"),
        ("POST", "/apps/acm/w-site/start"),
        ("DELETE", "/apps/acm/w-site"),
    ]:
        assert request(method, url)[0] == 404, (method, url)
    assert "app-acm-w-site" in fake.containers
    assert not [call for call in fake.calls if call[0] in ("rm", "stop", "start", "logs", "podman")]

    # The owner finds it by its legacy name
    status, found = request("GET", "/apps/acm-w/site")
    assert status == 200 and found["id"] == "app-acm-w-site" and found["org"] == "acm-w"
    assert request("DELETE", "/apps/acm-w/site") == (200, {"deleted": "app-acm-w-site"})
    assert "app-acm-w-site" not in fake.containers


def test_the_runner_refuses_an_org_with_two_dashes_in_a_row(served):
    _fake, request = served
    status, answer = request("GET", "/apps/acm--w/site")
    assert status == 400 and "two dashes" in answer["error"]
