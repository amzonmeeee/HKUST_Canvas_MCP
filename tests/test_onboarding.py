from contextlib import contextmanager
from unittest.mock import Mock

from fastapi.testclient import TestClient

from auth.chrome_cookies import ChromeProfile
from webapp.api import create_app
from webapp.db import WorkspaceRepository

ORIGIN = "http://127.0.0.1:8765"


@contextmanager
def connect(app):
    with TestClient(app, base_url=ORIGIN) as client:
        result = client.post("/api/session", headers={"Origin": ORIGIN, "Authorization": "Bearer synthetic"})
        client.headers.update({"Origin": ORIGIN, "X-Workbench-CSRF": result.json()["csrf_token"]})
        yield client


def test_fresh_setup_blocks_implicit_canvas_and_persists_ack(tmp_path, monkeypatch):
    probe = Mock(side_effect=AssertionError("No Chrome probe before explicit selection"))
    monkeypatch.setattr("webapp.services.canvas.get_auth_status", probe)
    app = create_app(data_dir=tmp_path / "app", launch_secret="synthetic")
    with connect(app) as client:
        assert client.get("/api/onboarding").json()["completed"] is False
        assert client.get("/api/canvas/status").json()["auth_status"] == "unconfigured"
        assert client.get("/api/canvas/courses").status_code == 409
        probe.assert_not_called()
        assert client.put("/api/onboarding", json={"privacy_acknowledged": False}).status_code == 422
        assert client.put("/api/onboarding", json={"privacy_acknowledged": True}).json()["completed"]
    with connect(create_app(data_dir=tmp_path / "app", launch_secret="synthetic")) as client:
        assert client.get("/api/onboarding").json() == {"completed": True, "privacy_acknowledged": True, "canvas_enabled": False}


def test_explicit_profile_test_returns_bounded_account_and_invalidates_previews(tmp_path, monkeypatch):
    monkeypatch.setattr("webapp.services.canvas.list_chrome_profiles", lambda: [ChromeProfile("Synthetic profile", str(tmp_path / "Default"), None)])
    monkeypatch.setattr("webapp.services.canvas.get_auth_status", lambda: {"auth_verified": True, "account": {"id": "1", "name": "Synthetic user"}})
    app = create_app(data_dir=tmp_path / "app", launch_secret="synthetic")
    with connect(app) as client:
        app.state.interactions._pending["synthetic-preview"] = {"deadline": 10**30}
        result = client.post("/api/canvas/profile/test", json={"profile_id": "Default"})
        assert result.status_code == 200 and result.json()["account"] == {"id": "1", "name": "Synthetic user"}
        assert app.state.interactions._pending == {}
        assert client.get("/api/onboarding").json()["canvas_enabled"] is True
        assert client.delete("/api/canvas/profile").status_code == 200
        assert client.get("/api/onboarding").json()["canvas_enabled"] is False


def test_migration_preserves_existing_workspace_and_skips_repeated_wizard(tmp_path):
    import sqlite3
    from contextlib import closing

    repo = WorkspaceRepository(tmp_path / "app")
    repo.initialize()
    saved = repo.create(title="Synthetic existing work")
    with closing(sqlite3.connect(repo.path)) as db, db:
        db.execute("DROP TABLE app_settings")
        db.execute("PRAGMA user_version=5")
    with connect(create_app(data_dir=repo.data_dir, launch_secret="synthetic")) as client:
        assert client.get("/api/onboarding").json()["completed"] is True
        assert client.get(f"/api/workspaces/{saved['id']}").json() == saved
