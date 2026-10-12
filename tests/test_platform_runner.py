"""The This server runner's policy checks (deploy/runner/platform_runner.py), with no podman."""

import pytest

from tests.runner_fake import POLICY, runner

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
