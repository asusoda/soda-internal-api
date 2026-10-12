"""Settings come from the environment only. Doppler sets it; Platform reads no .env or key file."""

import json

from core.config import Config, _service_account

KEY = {"type": "service_account", "client_email": "calendar@example.iam.gserviceaccount.com"}


def test_service_account_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT", json.dumps(KEY))
    assert _service_account() == KEY


def test_service_account_is_off_when_missing_or_not_an_object(monkeypatch):
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT", raising=False)
    assert _service_account() is None
    for raw in ("", "   ", "{not json", '["a list"]'):
        monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT", raw)
        assert _service_account() is None


def test_files_in_the_working_directory_are_not_read(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("NOTION_API_KEY=from-dotenv\n")
    (tmp_path / "google-secret.json").write_text(json.dumps(KEY))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT", raising=False)
    settings = Config()
    assert settings.NOTION_API_KEY == ""
    assert settings.GOOGLE_SERVICE_ACCOUNT is None
