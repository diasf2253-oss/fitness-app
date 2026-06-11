"""
Phase 5 tests — single-origin SPA serving.
Uses a throwaway FastAPI app + tmp dist dir so the main test apps
(which run API-only) stay unaffected.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import SPAStaticFiles, mount_frontend


def make_app(tmp_path):
    (tmp_path / "index.html").write_text("<html><body>SPA SHELL</body></html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('hi')")
    spa = FastAPI()

    @spa.get("/api/ping")
    def ping():
        return {"status": "ok"}

    assert mount_frontend(spa, tmp_path) is True
    return TestClient(spa)


class TestSPAServing:
    def test_root_serves_index(self, tmp_path):
        client = make_app(tmp_path)
        r = client.get("/")
        assert r.status_code == 200
        assert "SPA SHELL" in r.text

    def test_real_assets_served(self, tmp_path):
        client = make_app(tmp_path)
        r = client.get("/assets/app.js")
        assert r.status_code == 200
        assert "console.log" in r.text

    def test_client_route_falls_back_to_index(self, tmp_path):
        client = make_app(tmp_path)
        r = client.get("/history")
        assert r.status_code == 200
        assert "SPA SHELL" in r.text

    def test_api_routes_win_over_spa(self, tmp_path):
        client = make_app(tmp_path)
        assert client.get("/api/ping").json() == {"status": "ok"}

    def test_not_mounted_without_build(self, tmp_path):
        empty = tmp_path / "nope"
        spa = FastAPI()
        assert mount_frontend(spa, empty) is False
