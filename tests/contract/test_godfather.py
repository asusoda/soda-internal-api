"""Pods on an org's RunPod account: officers manage them, members connect with short-lived certificates."""

from types import TracebackType

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.serialization import SSHCertificate, load_ssh_public_identity

from tests.contract.conftest import MEMBER_DISCORD_ID


class FakeRunPod:
    def __init__(self):
        self.pods: dict[str, dict] = {}
        self.calls: list[tuple] = []

    def create_pod(self, body):
        pod_id = f"pod{len(self.pods) + 1}"
        self.calls.append(("create", body))
        self.pods[pod_id] = {
            "id": pod_id,
            "status": "RUNNING",
            "cost": 0.2,
            "dataCenterId": "US-TX-3",
            "gpu": {"id": "NVIDIA A40", "count": 1},
            "runtime": {"ports": [{"ip": "203.0.113.5", "private": 22, "public": 40022, "type": "tcp"}]},
        }
        return self.pods[pod_id]

    def get_pod(self, pod_id):
        return self.pods.get(pod_id)

    def start_pod(self, pod_id):
        self.calls.append(("start", pod_id))
        self.pods[pod_id]["status"] = "RUNNING"

    def stop_pod(self, pod_id):
        self.calls.append(("stop", pod_id))
        self.pods[pod_id]["status"] = "EXITED"

    def delete_pod(self, pod_id):
        from core.integrations.runpod import RunPodError

        self.calls.append(("delete", pod_id))
        if pod_id not in self.pods:
            raise RunPodError("RunPod answered 404: pod not found", 404)
        self.pods.pop(pod_id)


@pytest.fixture
def runpod(app, monkeypatch):
    from core.db import db_connect
    from modules.godfather import service
    from modules.godfather.models import ComputeConnection, ComputeKey, ComputePod, ComputeSession

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    fake = FakeRunPod()
    monkeypatch.setattr(service, "_client", lambda db, org_id, provider="runpod": fake)
    yield fake
    db = db_connect.SessionLocal()
    db.query(ComputeSession).delete()
    db.query(ComputeConnection).delete()
    db.query(ComputePod).delete()
    db.query(ComputeKey).delete()
    db.commit()
    db.close()


def _user_key():
    from modules.godfather import ssh

    return ssh.generate_keypair("alice@laptop")[0]


def _create(client, headers, **body):
    return client.post("/api/compute/soda/pods", json={"name": "workshop", **body}, headers=headers)


def test_officer_creates_and_lists_a_pod(client, officer_headers, runpod):
    response = _create(client, officer_headers, gpu_type_id="NVIDIA A40", env={"HF_HOME": "/workspace/hf"})
    assert response.status_code == 201
    assert response.get_json()["pod"]["status"] == "RUNNING"
    _, body = runpod.calls[0]
    assert body["gpu"] == {"id": "NVIDIA A40", "count": 1} and body["cloud"] == "COMMUNITY"
    assert body["image"] == "ghcr.io/theaisocietyasu/godfather-base:latest" and body["ports"] == ["22/tcp"]
    assert body["disk"] == 20 and "mounts" not in body
    assert body["env"]["HF_HOME"] == "/workspace/hf"
    assert body["env"]["GODFATHER_SSH_CA_PUBLIC_KEY"].startswith("ssh-ed25519 ")
    assert "PRIVATE" not in str(body)

    pods = client.get("/api/compute/soda/pods", headers=officer_headers).get_json()["pods"]
    assert [(p["id"], p["name"], p["status"]) for p in pods] == [("pod1", "workshop", "RUNNING")]


def test_cpu_pods_and_bad_requests(client, officer_headers, runpod):
    assert _create(client, officer_headers, use_cpu_only=True).status_code == 201
    _, body = runpod.calls[0]
    assert body["cpu"] == {"id": "cpu3c", "vcpuCount": 2} and "gpu" not in body and "mounts" not in body
    assert _create(client, officer_headers, volume_in_gb=50, volume_mount_path="/data").status_code == 201
    assert runpod.calls[1][1]["mounts"] == {"persistent": {"size": 50, "path": "/data"}}
    for bad in (
        {"env": {"GODFATHER_SETUP": "false"}},
        {"volume_in_gb": -1},
        {"volume_in_gb": 5},
        {"use_cpu_only": True, "vcpu_count": 3},
        {"cloud_type": "MOON"},
        {"allowed_users": ["not-an-id"]},
    ):
        assert _create(client, officer_headers, **bad).status_code == 400


def test_member_sees_and_connects_to_shared_running_pods(client, member_client, officer_headers, runpod, monkeypatch):
    from modules.godfather import api

    monkeypatch.setattr(api, "_is_officer", lambda org, discord_id: False)
    _create(client, officer_headers)
    assert member_client.get("/api/compute/soda/me/pods").get_json() == {"pods": []}
    key = _user_key()
    denied = member_client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": key})
    assert denied.status_code == 403

    shared = client.put(
        "/api/compute/soda/pods/pod1", json={"allowed_users": [MEMBER_DISCORD_ID]}, headers=officer_headers
    )
    assert shared.get_json()["pod"]["allowed_users"] == [MEMBER_DISCORD_ID]
    assert [p["id"] for p in member_client.get("/api/compute/soda/me/pods").get_json()["pods"]] == ["pod1"]

    info = member_client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": key}).get_json()["ssh_info"]
    assert (info["host"], info["port"], info["username"], info["is_admin"]) == ("203.0.113.5", 40022, "root", False)
    cert = load_ssh_public_identity(info["certificate"].encode())
    assert isinstance(cert, SSHCertificate)
    assert cert.valid_principals == [b"gf-pod1"]
    assert cert.critical_options[b"force-command"].startswith(b"/usr/local/bin/godfather-login ")
    assert member_client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": "nope"}).status_code == 400

    client.post("/api/compute/soda/pods/pod1/action", json={"action": "stop"}, headers=officer_headers)
    assert member_client.get("/api/compute/soda/me/pods").get_json() == {"pods": []}
    stopped = member_client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": key})
    assert stopped.status_code == 409


def test_officers_get_root_certificates(client, member_client, officer_headers, runpod):
    _create(client, officer_headers)
    info = member_client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": _user_key()}).get_json()
    cert = load_ssh_public_identity(info["ssh_info"]["certificate"].encode())
    assert isinstance(cert, SSHCertificate)
    assert info["ssh_info"]["is_admin"] is True and cert.critical_options == {}


def test_actions_and_terminate(client, officer_headers, runpod):
    _create(client, officer_headers)
    for action in ("stop", "start", "restart"):
        assert (
            client.post(
                "/api/compute/soda/pods/pod1/action", json={"action": action}, headers=officer_headers
            ).status_code
            == 200
        )
    assert runpod.calls[1:] == [("stop", "pod1"), ("start", "pod1"), ("stop", "pod1"), ("start", "pod1")]
    assert (
        client.post(
            "/api/compute/soda/pods/pod1/action", json={"action": "explode"}, headers=officer_headers
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/compute/soda/pods/pod1/action", json={"action": "terminate"}, headers=officer_headers
        ).status_code
        == 200
    )
    assert client.get("/api/compute/soda/pods", headers=officer_headers).get_json() == {"pods": []}
    assert client.get("/api/compute/soda/pods/pod1", headers=officer_headers).status_code == 404


def test_terminate_forgets_a_pod_already_deleted_on_runpod(client, officer_headers, runpod):
    _create(client, officer_headers)
    runpod.pods.clear()
    gone = client.post("/api/compute/soda/pods/pod1/action", json={"action": "terminate"}, headers=officer_headers)
    assert gone.status_code == 200
    assert client.get("/api/compute/soda/pods", headers=officer_headers).get_json() == {"pods": []}


def test_keys_are_stored_encrypted_and_reused(client, officer_headers, runpod):
    from core.db import db_connect
    from modules.godfather.models import ComputeKey

    _create(client, officer_headers)
    _create(client, officer_headers, name="second")
    first_ca = runpod.calls[0][1]["env"]["GODFATHER_SSH_CA_PUBLIC_KEY"]
    assert runpod.calls[1][1]["env"]["GODFATHER_SSH_CA_PUBLIC_KEY"] == first_ca
    db = db_connect.SessionLocal()
    rows = db.query(ComputeKey).all()
    db.close()
    assert sorted(r.kind for r in rows) == ["backend", "user_ca"]
    assert all("PRIVATE KEY" not in r.private_key for r in rows)


def test_without_a_runpod_key_the_org_is_told(client, officer_headers, app, monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    response = _create(client, officer_headers)
    assert response.status_code == 400 and "runpod_api_key" in response.get_json()["error"]


def test_turning_godfather_off_hides_the_routes(client, officer_headers, runpod, restore_soda_config):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    soda_id = next(o["id"] for o in orgs if o["prefix"] == "soda")
    client.put(f"/api/organizations/{soda_id}/modules", json={"modules": {"godfather": False}}, headers=officer_headers)
    assert client.get("/api/compute/soda/pods", headers=officer_headers).status_code == 404


class FakeSFTP:
    """An in-memory filesystem with the paramiko SFTPClient calls PodFiles uses."""

    def __init__(self):
        self.files: dict[str, bytes] = {"/workspace/train.py": b"print('hi')\n"}
        self.dirs: set[str] = {"/", "/workspace", "/workspace/data"}

    def _attr(self, name, path):
        import stat
        from types import SimpleNamespace

        is_dir = path in self.dirs
        mode = (stat.S_IFDIR | 0o755) if is_dir else (stat.S_IFREG | 0o644)
        size = 0 if is_dir else len(self.files[path])
        return SimpleNamespace(filename=name, st_mode=mode, st_size=size, st_mtime=1)

    def listdir_attr(self, path):
        if path not in self.dirs:
            raise FileNotFoundError(path)
        prefix = path.rstrip("/") + "/"
        names = {p[len(prefix) :] for p in [*self.files, *self.dirs] if p.startswith(prefix) and p != path}
        return [self._attr(n, prefix + n) for n in sorted(names) if "/" not in n]

    def stat(self, path):
        if path not in self.files and path not in self.dirs:
            raise FileNotFoundError(path)
        return self._attr(path.rsplit("/", 1)[-1], path)

    def open(self, path, mode):
        import io

        sftp = self
        if mode == "r":
            if path not in self.files:
                raise FileNotFoundError(path)
            return io.BytesIO(self.files[path])

        class Writer(io.BytesIO):
            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc_val: BaseException | None,
                exc_tb: TracebackType | None,
            ) -> None:
                sftp.files[path] = self.getvalue()
                super().__exit__(exc_type, exc_val, exc_tb)

        return Writer()

    def getfo(self, path, buffer):
        buffer.write(self.files[path])

    def putfo(self, stream, path):
        self.files[path] = stream.read()

    def mkdir(self, path):
        if path in self.dirs:
            raise OSError("exists")
        self.dirs.add(path)

    def rename(self, old, new):
        self.files[new] = self.files.pop(old)

    def close(self):
        pass


class FakeSSH:
    def __init__(self):
        self.commands: list[str] = []

    def exec_command(self, command, timeout=None):
        from types import SimpleNamespace

        self.commands.append(command)
        stdout = SimpleNamespace(channel=SimpleNamespace(recv_exit_status=lambda: 0))
        return None, stdout, None

    def close(self):
        pass


@pytest.fixture
def pod_fs(runpod, monkeypatch):
    from modules.godfather import files

    sftp, ssh = FakeSFTP(), FakeSSH()
    opened: list[tuple] = []

    def fake_open(host, port, private_key):
        opened.append((host, port, private_key.startswith("-----BEGIN OPENSSH PRIVATE KEY-----")))
        return files.PodFiles(ssh, sftp)

    monkeypatch.setattr(files.PodFiles, "open", staticmethod(fake_open))
    yield sftp, ssh, opened


def test_officers_manage_files_on_a_running_pod(client, officer_headers, pod_fs):
    import io

    sftp, ssh, opened = pod_fs
    _create(client, officer_headers)
    base = "/api/compute/soda/pods/pod1/files"

    listing = client.get(base, headers=officer_headers).get_json()
    assert listing["path"] == "/workspace"
    assert [(f["name"], f["type"]) for f in listing["files"]] == [("data", "directory"), ("train.py", "file")]
    assert opened[0] == ("203.0.113.5", 40022, True)

    read = client.post(f"{base}/read", json={"path": "/workspace/../workspace/train.py"}, headers=officer_headers)
    assert read.get_json() == {"path": "/workspace/train.py", "content": "print('hi')\n"}
    client.post(f"{base}/write", json={"path": "/workspace/train.py", "content": "x = 1\n"}, headers=officer_headers)
    assert sftp.files["/workspace/train.py"] == b"x = 1\n"

    download = client.post(f"{base}/download", json={"path": "/workspace/train.py"}, headers=officer_headers)
    assert download.status_code == 200 and download.data == b"x = 1\n"
    assert "train.py" in download.headers["Content-Disposition"]

    uploaded = client.post(
        f"{base}/upload",
        data={"path": "/workspace/data", "file": (io.BytesIO(b"a,b\n"), "rows.csv")},
        headers=officer_headers,
        content_type="multipart/form-data",
    )
    assert uploaded.get_json() == {"path": "/workspace/data/rows.csv"}
    assert sftp.files["/workspace/data/rows.csv"] == b"a,b\n"

    assert client.post(f"{base}/mkdir", json={"path": "/workspace/out"}, headers=officer_headers).status_code == 200
    renamed = client.post(
        f"{base}/rename",
        json={"old_path": "/workspace/train.py", "new_path": "/workspace/main.py"},
        headers=officer_headers,
    )
    assert renamed.status_code == 200 and "/workspace/main.py" in sftp.files
    deleted = client.post(f"{base}/delete", json={"path": "/workspace/it's here"}, headers=officer_headers)
    assert deleted.status_code == 200 and ssh.commands == ["rm -rf -- '/workspace/it'\"'\"'s here'"]


def test_file_requests_are_checked(client, member_client, officer_headers, pod_fs, runpod):
    _create(client, officer_headers)
    base = "/api/compute/soda/pods/pod1/files"
    assert client.post(f"{base}/read", json={"path": "relative.txt"}, headers=officer_headers).status_code == 400
    assert client.post(f"{base}/read", json={"path": "/missing"}, headers=officer_headers).status_code == 404
    for path in ("/", "/workspace/", "/root/../root"):
        assert client.post(f"{base}/delete", json={"path": path}, headers=officer_headers).status_code == 400
    assert client.post(f"{base}/upload", data={}, headers=officer_headers).status_code == 400
    assert client.get("/api/compute/soda/pods/nope/files", headers=officer_headers).status_code == 404
    assert member_client.get(f"{base}").status_code in (401, 403)

    client.post("/api/compute/soda/pods/pod1/action", json={"action": "stop"}, headers=officer_headers)
    assert client.get(base, headers=officer_headers).status_code == 409


def test_sessions_start_and_stop_a_pod(client, officer_headers, runpod):
    import datetime

    from core.db import db_connect
    from modules.godfather import schedule

    _create(client, officer_headers)
    runpod.pods["pod1"]["status"] = "EXITED"
    base = "/api/compute/soda/pods/pod1/sessions"
    utc = datetime.datetime(2099, 10, 9, 0, 0)

    def at(minutes):
        return utc + datetime.timedelta(minutes=minutes)

    created = client.post(
        base,
        json={"title": "Intro to CUDA", "start_at": "2099-10-08T17:00:00-07:00", "stop_at": "2099-10-09T02:00:00Z"},
        headers=officer_headers,
    )
    assert created.status_code == 201
    assert created.get_json()["session"]["start_at"] == "2099-10-09T00:00:00+00:00"
    client.post(
        base, json={"start_at": "2099-10-09T01:30:00Z", "stop_at": "2099-10-09T03:00:00Z"}, headers=officer_headers
    )
    assert len(client.get(base, headers=officer_headers).get_json()["sessions"]) == 2

    db = db_connect.SessionLocal()
    run = lambda minutes: schedule.run(db, now=at(minutes), client_for=lambda db, org_id, provider: runpod)  # noqa: E731
    assert run(-30) == {"started": [], "stopped": [], "failed": []}
    assert run(-5)["started"] == ["pod1"]
    assert runpod.pods["pod1"]["status"] == "RUNNING"
    assert run(60) == {"started": [], "stopped": [], "failed": []}
    # The first session ends while the second still runs
    assert run(125) == {"started": [], "stopped": [], "failed": []}
    assert run(185)["stopped"] == ["pod1"]
    assert runpod.pods["pod1"]["status"] == "EXITED"
    assert run(200) == {"started": [], "stopped": [], "failed": []}
    db.close()


def test_a_running_pod_is_stopped_after_its_session_and_others_are_left_alone(client, officer_headers, runpod):
    import datetime

    from core.db import db_connect
    from modules.godfather import schedule

    _create(client, officer_headers)
    _create(client, officer_headers, name="no sessions")
    body = {"start_at": "2099-10-09T00:00:00Z", "stop_at": "2099-10-09T01:00:00Z"}
    client.post("/api/compute/soda/pods/pod1/sessions", json=body, headers=officer_headers)
    db = db_connect.SessionLocal()
    now = datetime.datetime(2099, 10, 9, 0, 0)
    run = lambda when: schedule.run(db, now=when, client_for=lambda db, org_id, provider: runpod)  # noqa: E731
    assert run(now)["started"] == []
    assert run(now + datetime.timedelta(hours=2))["stopped"] == ["pod1"]
    assert runpod.pods["pod2"]["status"] == "RUNNING"
    db.close()


@pytest.mark.parametrize(
    "body",
    [
        None,
        {"start_at": "2099-10-09T00:00:00Z"},
        {"start_at": "2099-10-09T00:00:00", "stop_at": "2099-10-09T01:00:00"},
        {"start_at": "2099-10-09T02:00:00Z", "stop_at": "2099-10-09T01:00:00Z"},
        {"start_at": "2099-10-09T00:00:00Z", "stop_at": "2099-10-10T01:00:00Z"},
        {"start_at": "2020-01-01T00:00:00Z", "stop_at": "2020-01-01T01:00:00Z"},
        {"start_at": "tomorrow", "stop_at": "later"},
    ],
)
def test_bad_sessions_are_refused(client, officer_headers, runpod, body):
    _create(client, officer_headers)
    assert client.post("/api/compute/soda/pods/pod1/sessions", json=body, headers=officer_headers).status_code == 400


def test_deleting_and_terminating_clear_sessions(client, officer_headers, runpod):
    from core.db import db_connect
    from modules.godfather.models import ComputeSession

    _create(client, officer_headers)
    base = "/api/compute/soda/pods/pod1/sessions"
    body = {"start_at": "2099-01-01T00:00:00Z", "stop_at": "2099-01-01T01:00:00Z"}
    first = client.post(base, json=body, headers=officer_headers).get_json()["session"]["id"]
    client.post(base, json=body, headers=officer_headers)
    assert client.delete(f"{base}/{first}", headers=officer_headers).status_code == 200
    assert client.delete(f"{base}/{first}", headers=officer_headers).status_code == 404
    assert len(client.get(base, headers=officer_headers).get_json()["sessions"]) == 1
    client.post("/api/compute/soda/pods/pod1/action", json={"action": "terminate"}, headers=officer_headers)
    db = db_connect.SessionLocal()
    assert db.query(ComputeSession).count() == 0
    db.close()


# Godfather CLI sign-in: Discord login in the browser, then a bearer token on the member routes.


def _cli_sign_in(client, monkeypatch, discord_id=MEMBER_DISCORD_ID):
    import re

    from modules.accounts import providers

    monkeypatch.setenv("ACCOUNTS_BASE_URL", "https://platform.example")
    monkeypatch.setattr(providers, "discord_user_id", lambda *args, **kwargs: discord_id)
    start = client.get("/api/compute/soda/cli/login")
    assert start.status_code == 302 and "discord.com" in start.location
    assert "redirect_uri=https%3A%2F%2Fplatform.example%2Fapi%2Fcompute%2Fcli%2Fcallback" in start.location
    with client.session_transaction() as session:
        state = session["godfather_cli_login"]["state"]
    page = client.get(f"/api/compute/cli/callback?state={state}&code=abc")
    match = re.search(r"plat_[A-Za-z0-9_\-]+", page.get_data(as_text=True))
    return page, match.group(0) if match else None


def test_cli_token_works_on_member_routes(app, client, officer_headers, runpod, monkeypatch):
    from modules.godfather import api

    monkeypatch.setattr(api, "_is_officer", lambda org, discord_id: False)
    _create(client, officer_headers, allowed_users=[MEMBER_DISCORD_ID])
    page, token = _cli_sign_in(app.test_client(), monkeypatch)
    assert page.status_code == 200 and token and page.headers["Cache-Control"] == "no-store"

    bearer = {"Authorization": f"Bearer {token}"}
    assert [p["id"] for p in client.get("/api/compute/soda/me/pods", headers=bearer).get_json()["pods"]] == ["pod1"]
    info = client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": _user_key()}, headers=bearer)
    assert info.status_code == 200 and info.get_json()["ssh_info"]["is_admin"] is False

    _, newer = _cli_sign_in(app.test_client(), monkeypatch)
    assert client.get("/api/compute/soda/me/pods", headers=bearer).status_code == 401
    assert client.get("/api/compute/soda/me/pods", headers={"Authorization": f"Bearer {newer}"}).status_code == 200
    assert client.get("/api/compute/soda/me/pods", headers={"Authorization": "Bearer plat_nope"}).status_code == 401


def test_cli_token_follows_server_membership(app, client, officer_headers, runpod, monkeypatch):
    from modules.godfather import api

    _, token = _cli_sign_in(app.test_client(), monkeypatch)
    bearer = {"Authorization": f"Bearer {token}"}
    monkeypatch.setattr(api, "_is_member", lambda org, discord_id: False)
    assert client.get("/api/compute/soda/me/pods", headers=bearer).status_code == 403
    monkeypatch.setattr(api, "_is_member", lambda org, discord_id: None)
    assert client.get("/api/compute/soda/me/pods", headers=bearer).status_code == 503


def test_cli_sign_in_is_refused_when_it_should_be(app, runpod, monkeypatch):
    from modules.godfather import api

    monkeypatch.setattr(api, "_is_member", lambda org, discord_id: False)
    page, token = _cli_sign_in(app.test_client(), monkeypatch)
    assert page.status_code == 403 and token is None

    stray = app.test_client().get("/api/compute/cli/callback?state=forged&code=abc")
    assert stray.status_code == 400

    monkeypatch.delenv("ACCOUNTS_BASE_URL")
    assert app.test_client().get("/api/compute/soda/cli/login").status_code == 503


def test_cli_messages_and_pod_image_come_from_config(app, client, officer_headers, runpod, monkeypatch):
    from core.config import config

    expired = client.get("/api/compute/soda/me/pods", headers={"Authorization": "Bearer plat_nope"})
    assert expired.get_json()["error"] == "The CLI token is invalid or expired. Run godfather auth again."
    stray = app.test_client().get("/api/compute/cli/callback?state=forged&code=abc")
    assert "Run godfather auth again." in stray.get_data(as_text=True)

    monkeypatch.setattr(config, "GODFATHER_CLI_NAME", "gf")
    monkeypatch.setattr(config, "GODFATHER_POD_IMAGE", "example/pod:1")
    expired = client.get("/api/compute/soda/me/pods", headers={"Authorization": "Bearer plat_nope"})
    assert expired.get_json()["error"] == "The CLI token is invalid or expired. Run gf auth again."
    page, token = _cli_sign_in(app.test_client(), monkeypatch)
    assert token and "run gf auth and paste it" in page.get_data(as_text=True)

    assert _create(client, officer_headers).status_code == 201
    assert runpod.calls[0][1]["image"] == "example/pod:1"
    assert set(runpod.calls[0][1]["env"]) >= {"GODFATHER_SSH_PUBLIC_KEY", "GODFATHER_SETUP"}


def test_runpod_refusal_reaches_the_dashboard(client, officer_headers, runpod, monkeypatch):
    from core.integrations.runpod import RunPodError

    def refuse(body):
        raise RunPodError("RunPod answered 422: cpu.vcpuCount is required", 422)

    monkeypatch.setattr(runpod, "create_pod", refuse)
    response = _create(client, officer_headers, use_cpu_only=True)
    assert response.status_code == 400
    assert "vcpuCount" in response.get_json()["error"]

    def fail(body):
        raise RunPodError("RunPod could not be reached")

    monkeypatch.setattr(runpod, "create_pod", fail)
    assert _create(client, officer_headers).status_code == 424


def test_pod_list_reads_v2_fields(client, officer_headers, runpod):
    assert _create(client, officer_headers).status_code == 201
    pod = client.get("/api/compute/soda/pods", headers=officer_headers).get_json()["pods"][0]
    assert pod["cost_per_hour"] == 0.2
    assert pod["machine"] == {"gpuTypeId": "NVIDIA A40", "dataCenterId": "US-TX-3"}


# Who is on a pod: access, recent connections and live sessions.


class FakeShell:
    """An SSH client that answers the presence script with fixed output."""

    def __init__(self, output: str, status: int = 0):
        self.output, self.status = output.encode(), status
        self.commands: list[str] = []

    def exec_command(self, command, timeout=None):
        from types import SimpleNamespace

        self.commands.append(command)
        channel = SimpleNamespace(recv_exit_status=lambda: self.status)
        return None, SimpleNamespace(read=lambda limit=-1: self.output, channel=channel), None

    def close(self):
        pass


@pytest.fixture
def names(monkeypatch):
    from modules.godfather import api

    known = {MEMBER_DISCORD_ID: "Alice A"}
    monkeypatch.setattr(api, "_name_lookup", lambda org: known.get)
    return known


def test_connections_are_recorded_and_listed(client, member_client, officer_headers, runpod, names, monkeypatch):
    from modules.godfather import api

    monkeypatch.setattr(api, "_is_officer", lambda org, discord_id: False)
    _create(client, officer_headers, allowed_users=[MEMBER_DISCORD_ID, "222222222222222222"])
    base = "/api/compute/soda/pods/pod1/members"
    empty = client.get(base, headers=officer_headers).get_json()
    assert empty["recent"] == [] and empty["access"]["is_public"] is False
    assert empty["access"]["allowed"] == [
        {"discord_id": "222222222222222222", "name": None},
        {"discord_id": MEMBER_DISCORD_ID, "name": "Alice A"},
    ]

    connected = member_client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": _user_key()})
    assert connected.status_code == 200
    recent = client.get(base, headers=officer_headers).get_json()["recent"]
    assert [(r["discord_id"], r["name"], r["is_admin"]) for r in recent] == [(MEMBER_DISCORD_ID, "Alice A", False)]
    assert recent[0]["username"] == connected.get_json()["ssh_info"]["user_folder"] and recent[0]["created_at"]
    assert member_client.get(base).status_code in (401, 403)
    assert client.get("/api/compute/soda/pods/nope/members", headers=officer_headers).status_code == 404

    client.post("/api/compute/soda/pods/pod1/action", json={"action": "terminate"}, headers=officer_headers)
    from core.db import db_connect
    from modules.godfather.models import ComputeConnection

    db = db_connect.SessionLocal()
    assert db.query(ComputeConnection).count() == 0
    db.close()


def test_old_connections_are_deleted(client, officer_headers, runpod):
    import datetime

    from core.db import db_connect
    from core.time import utcnow
    from modules.godfather import service
    from modules.godfather.models import ComputeConnection

    _create(client, officer_headers)
    db = db_connect.SessionLocal()
    org_id = db.query(service.ComputePod).one().organization_id
    old = utcnow() - datetime.timedelta(days=service.CONNECTION_KEEP_DAYS + 1)
    db.add(ComputeConnection(organization_id=org_id, pod_id="pod1", discord_id="1", username="old", created_at=old))
    db.commit()
    service.record_connection(db, org_id, "pod1", "2", "new", True)
    assert [c.username for c in db.query(ComputeConnection).all()] == ["new"]
    db.close()


def test_connected_now_reads_the_sessions_on_the_pod(
    client, member_client, officer_headers, runpod, names, monkeypatch
):
    from modules.godfather import api, files

    monkeypatch.setattr(api, "_is_officer", lambda org, discord_id: False)
    _create(client, officer_headers, is_public=True)
    folder = member_client.post("/api/compute/soda/me/pods/pod1/connect", json={"public_key": _user_key()}).get_json()
    folder = folder["ssh_info"]["user_folder"]
    shell = FakeShell(
        f"member 340 {folder} -c cd '/workspace/users/{folder}' && exec bash\n"
        "admin 25 GODFATHER_USER=root-officer\n"
        "member x broken\n"
        "admin 9 GODFATHER_USER=\n"
    )
    opened: list[tuple] = []

    def fake_open(host, port, private_key, timeout):
        opened.append((host, port, timeout))
        return shell

    monkeypatch.setattr(files, "open_ssh", fake_open)
    body = client.get("/api/compute/soda/pods/pod1/members/connected", headers=officer_headers).get_json()
    assert opened == [("203.0.113.5", 40022, 5)]
    assert body["state"] == "known" and body["reason"] is None
    assert body["sessions"] == [
        {"username": folder, "is_admin": False, "seconds": 340, "discord_id": MEMBER_DISCORD_ID, "name": "Alice A"},
        {"username": "root-officer", "is_admin": True, "seconds": 25, "discord_id": None, "name": None},
    ]
    assert "godfather-login" in shell.commands[0] and "{" not in shell.commands[0].replace("${args#", "")


def test_connected_now_is_unknown_when_it_cannot_be_read(client, officer_headers, runpod, monkeypatch):
    from modules.godfather import files

    _create(client, officer_headers)
    url = "/api/compute/soda/pods/pod1/members/connected"

    def refuse(host, port, private_key, timeout):
        raise files.FilesError("Could not connect to the pod", 502)

    monkeypatch.setattr(files, "open_ssh", refuse)
    failed = client.get(url, headers=officer_headers)
    assert failed.status_code == 200
    assert failed.get_json() == {
        "pod_id": "pod1",
        "state": "unknown",
        "reason": "Could not connect to the pod",
        "sessions": [],
    }

    monkeypatch.setattr(files, "open_ssh", lambda *args: FakeShell("", status=3))
    other_image = client.get(url, headers=officer_headers).get_json()
    assert other_image["state"] == "unknown" and "godfather-login" in other_image["reason"]

    client.post("/api/compute/soda/pods/pod1/action", json={"action": "stop"}, headers=officer_headers)
    stopped = client.get(url, headers=officer_headers).get_json()
    assert stopped["state"] == "unknown" and stopped["reason"] == "The pod is not running"
    assert client.get("/api/compute/soda/pods/nope/members/connected", headers=officer_headers).status_code == 404


def test_presence_script_finds_member_and_officer_sessions():
    import os
    import subprocess

    from modules.godfather import presence

    # A fake ps lists a member session, an officer shell whose environment names its user, and an unrelated process
    officer = subprocess.Popen(["sleep", "30"], env={**os.environ, "GODFATHER_USER": "bob"})
    try:
        fake = (
            "test() { return 0; }; ps() { printf '%s\\n' "
            "\"  12   340 su - godfather_alice -c cd '/workspace/users/alice' && exec bash\" "
            f'"  {officer.pid}    25 bash --rcfile /etc/godfather/admin.bashrc -i" '
            "'   1  9999 sleep infinity'; }; "
        )
        result = subprocess.run(["bash", "-c", fake + presence.SCRIPT], capture_output=True, text=True, check=True)
    finally:
        officer.kill()
        officer.wait()
    assert presence.parse(result.stdout) == [
        {"username": "alice", "is_admin": False, "seconds": 340},
        {"username": "bob", "is_admin": True, "seconds": 25},
    ]
