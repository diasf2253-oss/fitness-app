"""
Staging/production environment plumbing:
  - /api/ping reports which environment this API is (the frontend's
    STAGING badge reads it)
  - CORS settings parse comma-separated origins and stay off by default
"""
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.main import app

client = TestClient(app)


class TestPingEnv:
    def test_ping_reports_env(self):
        body = client.get("/api/ping").json()
        assert body["status"] == "ok"
        assert body["env"] == settings.app_env

    def test_ping_reflects_staging(self, monkeypatch):
        monkeypatch.setattr(settings, "app_env", "staging")
        assert client.get("/api/ping").json()["env"] == "staging"


class TestCorsSettings:
    def test_defaults_add_no_origins(self):
        s = Settings(_env_file=None)
        assert s.cors_origin_list == []
        assert s.cors_allow_origin_regex == ""

    def test_comma_separated_origins_parse_and_trim(self):
        s = Settings(
            _env_file=None,
            cors_origins=" https://a.vercel.app, https://b.vercel.app ,",
        )
        assert s.cors_origin_list == ["https://a.vercel.app", "https://b.vercel.app"]

    def test_app_env_defaults_to_production(self):
        assert Settings(_env_file=None).app_env == "production"
