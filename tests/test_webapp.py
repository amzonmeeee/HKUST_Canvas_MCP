from __future__ import annotations

import asyncio
import errno
import json
import sqlite3
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from auth import CanvasAPIError
from webapp.api import create_app
from webapp.db import SCHEMA_VERSION, WorkspaceRepository, validate_data_dir
from webapp.services.canvas import CanvasService, CanvasServiceError

ORIGIN = "http://127.0.0.1:8765"
LAUNCH = "synthetic-launch-secret"
COURSE = {
    "id": "101",
    "name": "Synthetic course",
    "course_code": "TEST1000",
    "term_name": "Test term",
    "canvas_url": "https://canvas.ust.hk/courses/101",
}


@pytest.fixture(autouse=True)
def isolated_web_profile(monkeypatch):
    monkeypatch.setattr(
        "webapp.services.canvas.resolve_selected_chrome_profile",
        lambda: ("Synthetic profile", None),
    )


@pytest.fixture
def canvas_service():
    service = mock.Mock(spec=CanvasService)
    service.profile_name.return_value = "Synthetic profile"
    service.status.return_value = {
        "auth_verified": True,
        "auth_status": "verified",
        "profile_name": "Synthetic profile",
        "message": "Connected.",
    }
    service.courses.return_value = {"courses": [COURSE], "count": 1, "truncated": False}
    service.course.return_value = COURSE.copy()
    return service


@pytest.fixture
def app(tmp_path, canvas_service):
    return create_app(
        data_dir=tmp_path / "app-data",
        launch_secret=LAUNCH,
        canvas_service=canvas_service,
    )


@pytest.fixture
def client(app):
    with TestClient(app, base_url=ORIGIN) as test_client:
        bootstrap = test_client.post(
            "/api/session",
            headers={"Origin": ORIGIN, "Authorization": f"Bearer {LAUNCH}"},
        )
        assert bootstrap.status_code == 200
        test_client.headers.update(
            {"Origin": ORIGIN, "X-Workbench-CSRF": bootstrap.json()["csrf_token"]}
        )
        yield test_client


def test_custom_workspace_crud_and_persistence(client, app, tmp_path, canvas_service):
    created = client.post(
        "/api/workspaces",
        json={"title": "  Reading project  ", "description": "Local only"},
    )
    assert created.status_code == 201
    workspace = created.json()
    UUID(workspace["id"])
    assert workspace["kind"] == "custom" and workspace["title"] == "Reading project"
    assert workspace["canvas_course_id"] is None and workspace["last_sync_at"] is None
    assert client.get(f"/api/workspaces/{workspace['id']}").json() == workspace
    changed = client.patch(
        f"/api/workspaces/{workspace['id']}",
        json={"title": "Renamed", "description": "Updated"},
    )
    assert changed.status_code == 200 and changed.json()["description"] == "Updated"
    reloaded = WorkspaceRepository(tmp_path / "app-data")
    reloaded.initialize()
    assert reloaded.get(workspace["id"])["title"] == "Renamed"
    assert len(client.get("/api/workspaces").json()["workspaces"]) == 1
    assert client.delete(f"/api/workspaces/{workspace['id']}").status_code == 204
    assert client.get(f"/api/workspaces/{workspace['id']}").status_code == 404
    canvas_service.course.assert_not_called()


def test_course_workspace_is_unique_and_reopens_offline(client, canvas_service):
    payload = {"kind": "canvas_course", "canvas_course_id": "101"}
    first = client.post("/api/workspaces", json=payload)
    assert first.status_code == 201
    canvas_service.course.side_effect = CanvasServiceError(
        "canvas_unavailable", "Offline"
    )
    second = client.post("/api/workspaces", json=payload)
    assert second.json()["id"] == first.json()["id"]
    assert first.json()["title"] == COURSE["name"]
    assert canvas_service.course.call_count == 1


def test_concurrent_course_creation_keeps_single_workspace(tmp_path):
    repo = WorkspaceRepository(tmp_path / "concurrent")
    repo.initialize()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: repo.create(title=COURSE["name"], course=COURSE), range(8)
            )
        )
    assert len({row["id"] for row in results}) == 1 and len(repo.list()) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": "   "},
        {"title": "a" * 161},
        {"title": "Title", "description": "a" * 2001},
        {"title": "Title", "canvas_course_id": "101"},
        {"kind": "canvas_course"},
        {"kind": "canvas_course", "canvas_course_id": "../cookies"},
        {"kind": "canvas_course", "canvas_course_id": "101", "title": "Spoofed"},
        {"kind": "canvas_course", "canvas_course_id": "101", "description": "Spoofed"},
        {"title": "Title", "path": "/etc/passwd"},
    ],
)
def test_invalid_workspace_payloads_never_create_or_call_canvas(
    client, payload, canvas_service
):
    assert client.post("/api/workspaces", json=payload).status_code == 422
    assert client.get("/api/workspaces").json()["workspaces"] == []
    canvas_service.course.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {"title": " "},
        {"title": None},
        {"description": None},
        {"kind": "canvas_course"},
        {"canvas_course_id": "101"},
    ],
)
def test_invalid_workspace_updates_preserve_original(client, payload):
    original = client.post("/api/workspaces", json={"title": "Original"}).json()
    assert (
        client.patch(f"/api/workspaces/{original['id']}", json=payload).status_code
        == 422
    )
    assert client.get(f"/api/workspaces/{original['id']}").json()["title"] == "Original"


def test_course_id_mismatch_is_not_saved(client, canvas_service):
    canvas_service.course.return_value = {**COURSE, "id": "202"}
    result = client.post(
        "/api/workspaces", json={"kind": "canvas_course", "canvas_course_id": "101"}
    )
    assert (
        result.status_code == 502
        and result.json()["error"]["code"] == "invalid_canvas_response"
    )
    assert client.get("/api/workspaces").json()["workspaces"] == []


def test_canvas_failures_do_not_block_local_workspaces(client, canvas_service):
    canvas_service.courses.side_effect = CanvasServiceError(
        "canvas_auth_expired", "Sign in again.", 401
    )
    assert client.get("/api/canvas/courses").status_code == 401
    assert (
        client.post("/api/workspaces", json={"title": "Offline reading"}).status_code
        == 201
    )
    assert len(client.get("/api/workspaces").json()["workspaces"]) == 1


def test_canvas_reads_and_settings(client, canvas_service):
    assert client.get("/api/canvas/courses").json()["courses"] == [COURSE]
    assert client.get("/api/canvas/courses/101").json() == COURSE
    assert client.get("/api/canvas/courses/not-a-number").status_code == 422
    assert client.get("/api/canvas/status").json()["auth_verified"] is True
    settings = client.get("/api/settings").json()
    assert settings["profile_name"] == "Synthetic profile"
    assert settings["providers_available"] is True
    assert settings["mcp_command"] == "canvas-mcp --transport stdio"


@pytest.mark.parametrize(
    "path", ["/api/workspaces", "/api/canvas/courses", "/api/settings", "/api/session"]
)
def test_api_requires_launch_session(app, path):
    with TestClient(app, base_url=ORIGIN) as raw:
        assert raw.get(path).status_code == 401


@pytest.mark.parametrize(
    "host",
    [
        "evil.example:8765",
        "localhost:8765",
        "127.0.0.1:9999",
        "127.0.0.1",
        "127.0.0.1:8765.evil.example",
    ],
)
def test_dns_rebinding_and_wrong_hosts_are_rejected(client, host):
    assert client.get("/api/workspaces", headers={"Host": host}).status_code == 400


@pytest.mark.parametrize(
    "origin",
    ["https://evil.example", "http://localhost:8765", "null", "http://127.0.0.1:9999"],
)
def test_foreign_origins_are_rejected_for_reads_and_writes(client, origin):
    assert client.get("/api/workspaces", headers={"Origin": origin}).status_code == 403
    assert (
        client.post(
            "/api/workspaces", headers={"Origin": origin}, json={"title": "Rejected"}
        ).status_code
        == 403
    )


def test_missing_origin_csrf_and_cross_site_fetch_are_rejected(client):
    client.headers.pop("Origin")
    assert client.post("/api/workspaces", json={"title": "Rejected"}).status_code == 403
    client.headers["Origin"] = ORIGIN
    client.headers.pop("X-Workbench-CSRF")
    assert client.post("/api/workspaces", json={"title": "Rejected"}).status_code == 403
    assert (
        client.get(
            "/api/workspaces", headers={"Sec-Fetch-Site": "cross-site"}
        ).status_code
        == 403
    )
    assert client.get("/api/workspaces").json()["workspaces"] == []


def test_all_mutation_methods_require_csrf(client):
    workspace = client.post("/api/workspaces", json={"title": "Protected"}).json()
    client.headers["X-Workbench-CSRF"] = "incorrect"
    assert (
        client.patch(
            f"/api/workspaces/{workspace['id']}", json={"title": "Changed"}
        ).status_code
        == 403
    )
    assert client.delete(f"/api/workspaces/{workspace['id']}").status_code == 403
    assert (
        client.get(f"/api/workspaces/{workspace['id']}").json()["title"] == "Protected"
    )


def test_bootstrap_cookie_is_http_only_and_secret_never_in_response(app):
    with TestClient(app, base_url=ORIGIN) as raw:
        assert (
            raw.post(
                "/api/session",
                headers={"Origin": ORIGIN, "Authorization": "Bearer wrong"},
            ).status_code
            == 401
        )
        assert (
            raw.post(
                "/api/session", headers={"Authorization": f"Bearer {LAUNCH}"}
            ).status_code
            == 403
        )
        result = raw.post(
            "/api/session",
            headers={"Origin": ORIGIN, "Authorization": f"Bearer {LAUNCH}"},
        )
        cookie = result.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert LAUNCH not in result.text
        assert len(result.json()["csrf_token"]) >= 32


def test_session_restart_invalidates_old_cookies(tmp_path, canvas_service):
    app_one = create_app(
        data_dir=tmp_path / "same", launch_secret=LAUNCH, canvas_service=canvas_service
    )
    app_two = create_app(
        data_dir=tmp_path / "same", launch_secret=LAUNCH, canvas_service=canvas_service
    )
    with (
        TestClient(app_one, base_url=ORIGIN) as one,
        TestClient(app_two, base_url=ORIGIN) as two,
    ):
        one.post(
            "/api/session",
            headers={"Origin": ORIGIN, "Authorization": f"Bearer {LAUNCH}"},
        )
        two.cookies.update(one.cookies)
        assert two.get("/api/workspaces").status_code == 401


def test_different_loopback_ports_keep_independent_browser_sessions(
    tmp_path, canvas_service
):
    second_origin = "http://127.0.0.1:12345"
    one_app = create_app(
        data_dir=tmp_path / "one", launch_secret=LAUNCH, canvas_service=canvas_service
    )
    two_app = create_app(
        data_dir=tmp_path / "two",
        port=12345,
        launch_secret=LAUNCH,
        canvas_service=canvas_service,
    )
    with (
        TestClient(one_app, base_url=ORIGIN) as one,
        TestClient(two_app, base_url=second_origin) as two,
    ):
        for client, origin in ((one, ORIGIN), (two, second_origin)):
            assert (
                client.post(
                    "/api/session",
                    headers={"Origin": origin, "Authorization": f"Bearer {LAUNCH}"},
                ).status_code
                == 200
            )
        one.cookies.update(two.cookies)
        two.cookies.update(one.cookies)
        assert one.get("/api/workspaces").status_code == 200
        assert two.get("/api/workspaces").status_code == 200


def test_static_shell_spa_routes_and_csp(tmp_path, canvas_service):
    assets = tmp_path / "static"
    (assets / "assets").mkdir(parents=True)
    (assets / "index.html").write_text(
        "<!doctype html><title>Synthetic workbench</title>"
    )
    (assets / "assets" / "app.js").write_text("console.log('synthetic')")
    app = create_app(
        data_dir=tmp_path / "storage", canvas_service=canvas_service, static_dir=assets
    )
    with TestClient(app, base_url=ORIGIN) as raw:
        for path in (
            "/",
            "/settings",
            "/workspace/00000000-0000-4000-8000-000000000001",
        ):
            result = raw.get(path)
            assert result.status_code == 200 and "Synthetic workbench" in result.text
            assert "frame-ancestors 'none'" in result.headers["content-security-policy"]
            assert result.headers["cache-control"] == "no-store"
            assert result.headers["x-content-type-options"] == "nosniff"
        assert raw.get("/assets/app.js").status_code == 200
        assert raw.get("/assets/%2e%2e/%2e%2e/app.db").status_code != 200
        assert raw.get("/api/unknown").status_code == 401
        assert raw.get("/openapi.json").status_code == 404
        assert raw.get("/etc/passwd").status_code == 404


def test_missing_frontend_has_actionable_error(app):
    # The app fixture uses a nonexistent explicit asset root to avoid depending on a local build.
    app = create_app(
        data_dir=app.state.repository.data_dir,
        static_dir=Path("/nonexistent-workbench-static"),
        canvas_service=mock.Mock(spec=CanvasService),
    )
    with TestClient(app, base_url=ORIGIN) as raw:
        assert raw.get("/").status_code == 503
        assert raw.get("/").json()["error"]["code"] == "frontend_missing"


def test_database_schema_permissions_and_forward_version(tmp_path):
    repo = WorkspaceRepository(tmp_path / "database")
    repo.initialize()
    assert stat.S_IMODE(repo.data_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(repo.path.stat().st_mode) == 0o600
    with sqlite3.connect(repo.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        columns = [row[1] for row in db.execute("PRAGMA table_info(workspaces)")]
        assert not any(
            word in " ".join(columns) for word in ("cookie", "token", "secret", "key")
        )
        db.execute("PRAGMA user_version=999")
    with pytest.raises(ValueError, match="newer"):
        repo.initialize()


def test_storage_rejects_repository_and_database_symlinks(tmp_path):
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="outside"):
        validate_data_dir(root / "ignored-data")
    alias = tmp_path / "repo-alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="outside"):
        validate_data_dir(alias / "ignored-data")
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "app.db").symlink_to(tmp_path / "unrelated")
    with pytest.raises(ValueError, match="symbolic"):
        WorkspaceRepository(storage).initialize()


def test_canvas_adapter_reuses_registered_tools_and_strips_private_fields(monkeypatch):
    dispatcher = mock.Mock(
        side_effect=[
            {
                "courses": [
                    {
                        **COURSE,
                        "cookies": "synthetic-secret",
                        "teacher": "Synthetic private teacher",
                    }
                ]
            },
            {
                "course": {
                    **COURSE,
                    "term": {"name": "Test term"},
                    "teachers": ["private"],
                    "syllabus_body": "private",
                }
            },
        ]
    )
    monkeypatch.setattr("webapp.services.canvas.dispatch_tool_call", dispatcher)
    service = CanvasService()
    assert service.courses()["courses"] == [COURSE]
    assert service.course("101") == COURSE
    assert dispatcher.call_args_list == [
        mock.call("list_courses", {"favorites_only": False, "limit": 300}),
        mock.call("get_course_overview", {"course_id": "101"}),
    ]


@pytest.mark.parametrize(
    "error,expected",
    [
        ("forbidden", 403),
        ("not_found", 404),
        ("auth_error", 401),
        ("internal_error", 502),
    ],
)
def test_canvas_adapter_redacts_raw_errors(monkeypatch, error, expected):
    monkeypatch.setattr(
        "webapp.services.canvas.dispatch_tool_call",
        lambda *a: {"error": error, "message": "synthetic-private-secret"},
    )
    with pytest.raises(CanvasServiceError) as result:
        CanvasService().courses()
    assert (
        result.value.status_code == expected
        and "synthetic-private-secret" not in str(result.value)
    )


def test_status_whitelist_and_exception_redaction(monkeypatch):
    monkeypatch.setattr(
        "webapp.services.canvas.resolve_selected_chrome_profile",
        lambda: ("Test profile", "/private/synthetic"),
    )
    monkeypatch.setattr(
        "webapp.services.canvas.get_auth_status",
        lambda: {
            "auth_verified": True,
            "selected_chrome_profile_path": "/private/synthetic",
            "probe_location": "https://example.test/?secret=synthetic",
            "cookies": "synthetic",
        },
    )
    service = CanvasService()
    status = service.status()
    assert status["auth_verified"] is True and status["profile_name"] == "Test profile"
    assert set(status) == {"auth_verified", "auth_status", "profile_name", "message"}
    monkeypatch.setattr(
        "webapp.services.canvas.get_auth_status",
        mock.Mock(side_effect=CanvasAPIError("synthetic-private-cookie")),
    )
    assert "synthetic-private-cookie" not in json.dumps(service.status())


def test_web_cli_does_not_require_canvas_authentication(monkeypatch, tmp_path):
    from cli.bootstrap import app

    launch = mock.Mock()
    monkeypatch.setattr("webapp.launcher.launch", launch)
    result = CliRunner().invoke(
        app, ["web", "--port", "0", "--no-open", "--data-dir", str(tmp_path)]
    )
    assert result.exit_code == 0
    launch.assert_called_once_with(port=0, open_browser=False, data_dir=tmp_path)


def test_web_cli_reports_optional_dependencies(monkeypatch):
    from cli.bootstrap import app

    monkeypatch.setattr(
        "webapp.launcher.launch",
        mock.Mock(side_effect=ModuleNotFoundError("missing", name="fastapi")),
    )
    result = CliRunner().invoke(app, ["web", "--no-open"])
    assert result.exit_code == 1 and "uv sync --extra web" in result.output


def test_web_cli_validates_port():
    from cli.bootstrap import app

    result = CliRunner().invoke(app, ["web", "--port", "65536"])
    assert result.exit_code == 2


def test_profile_changes_invalidate_shared_canvas_client(monkeypatch):
    context = ["Synthetic profile", "/synthetic/profile-one"]
    monkeypatch.setattr(
        "webapp.services.canvas.resolve_selected_chrome_profile", lambda: tuple(context)
    )
    monkeypatch.setattr(
        "webapp.services.canvas.dispatch_tool_call", lambda *a: {"courses": []}
    )
    reset = mock.Mock()
    monkeypatch.setattr("webapp.services.canvas.reset_canvas_client", reset)
    service = CanvasService()
    service.courses()
    service.courses()
    assert reset.call_count == 1
    context[:] = ["Other synthetic profile", "/synthetic/profile-two"]
    service.courses()
    assert reset.call_count == 2 and service.profile_name() == "Other synthetic profile"


@pytest.mark.parametrize(
    "status,expected",
    [
        ("probe_failed", "unavailable"),
        ("unexpected_response", "unavailable"),
        ("no_cookies", "sign_in_required"),
        ("not_logged_in", "sign_in_required"),
    ],
)
def test_canvas_status_distinguishes_network_from_sign_in(
    monkeypatch, status, expected
):
    monkeypatch.setattr(
        "webapp.services.canvas.get_auth_status",
        lambda: {"auth_verified": False, "auth_status": status},
    )
    assert CanvasService().status()["auth_status"] == expected


def test_profile_path_selection_is_described_without_exposing_path(monkeypatch):
    monkeypatch.setattr(
        "webapp.services.canvas.resolve_selected_chrome_profile",
        lambda: (None, "/synthetic/private/profile"),
    )
    assert CanvasService().profile_name() == "Selected by profile path"


@pytest.mark.parametrize("path", [Path("/"), Path.home()])
def test_storage_refuses_shared_roots(path):
    with pytest.raises(ValueError, match="dedicated"):
        validate_data_dir(path)


def test_launcher_reserves_loopback_and_falls_back_only_for_occupied_port(monkeypatch):
    from webapp.launcher import reserve_socket

    sock = mock.Mock()
    sock.bind.side_effect = [OSError(errno.EADDRINUSE, "synthetic occupied"), None]
    monkeypatch.setattr("webapp.launcher.socket.socket", lambda *a: sock)
    assert reserve_socket(8765) is sock
    assert sock.bind.call_args_list == [
        mock.call(("127.0.0.1", 8765)),
        mock.call(("127.0.0.1", 0)),
    ]
    sock.close.assert_not_called()
    sock.bind.side_effect = OSError(errno.EACCES, "synthetic denied")
    with pytest.raises(OSError):
        reserve_socket(8765)
    sock.close.assert_called_once()


def test_launcher_opens_browser_after_successful_startup_and_closes_socket(
    monkeypatch, capsys, tmp_path
):
    from webapp.launcher import launch

    sock = mock.Mock()
    sock.getsockname.return_value = ("127.0.0.1", 12345)
    monkeypatch.setattr("webapp.launcher.reserve_socket", lambda port: sock)
    monkeypatch.setattr("webapp.api.create_app", mock.Mock(return_value=object()))
    opened = mock.Mock()
    monkeypatch.setattr("webapp.launcher.webbrowser.open", opened)

    class FakeServer:
        def __init__(self, config):
            assert config.host == "127.0.0.1" and config.access_log is False
            self.started = False

        async def startup(self, sockets=None):
            assert sockets == [sock]
            opened.assert_not_called()
            self.started = True

        def run(self, sockets=None):
            asyncio.run(self.startup(sockets=sockets))

    monkeypatch.setattr("uvicorn.Server", FakeServer)
    launch(port=0, open_browser=True, data_dir=tmp_path)
    assert opened.call_args.args[0].startswith("http://127.0.0.1:12345/#session=")
    assert "Keep this terminal open" in capsys.readouterr().out
    sock.close.assert_called_once()


def test_canvas_profile_selection_is_pinned_persistent_and_clears_previews(
    tmp_path, monkeypatch
):
    from auth import settings as saved_settings
    from auth.chrome_cookies import ChromeProfile
    from auth.profiles import resolve_selected_chrome_profile

    service = CanvasService()
    profiles = [
        ChromeProfile(
            name="Synthetic profile", path=str(tmp_path / "Default"), cookie_file=None
        ),
        ChromeProfile(
            name="Other synthetic profile",
            path=str(tmp_path / "Profile 1"),
            cookie_file=None,
        ),
    ]
    monkeypatch.setattr("webapp.services.canvas.list_chrome_profiles", lambda: profiles)
    monkeypatch.setattr(
        "webapp.services.canvas.resolve_selected_chrome_profile",
        resolve_selected_chrome_profile,
    )
    monkeypatch.setattr("webapp.services.canvas.reset_canvas_client", mock.Mock())
    monkeypatch.setattr(saved_settings, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(
        saved_settings, "CONFIG_PATH", tmp_path / "config" / "settings.json"
    )
    monkeypatch.setenv("CANVAS_CHROME_PROFILE", "Synthetic profile")
    monkeypatch.delenv("CANVAS_CHROME_PROFILE_PATH", raising=False)
    app = create_app(
        data_dir=tmp_path / "workbench", launch_secret=LAUNCH, canvas_service=service
    )
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/api/canvas/profiles").status_code == 401
        bootstrap = client.post(
            "/api/session",
            headers={"Origin": ORIGIN, "Authorization": f"Bearer {LAUNCH}"},
        )
        client.headers.update(
            {"Origin": ORIGIN, "X-Workbench-CSRF": bootstrap.json()["csrf_token"]}
        )
        result = client.get("/api/canvas/profiles").json()
        assert result["profiles"][0]["selected"]
        assert all(
            "path" not in p and "cookie_file" not in p for p in result["profiles"]
        )
        app.state.interactions._pending["synthetic"] = {"deadline": 10**30}
        assert (
            client.put(
                "/api/canvas/profile", json={"profile_id": "../../elsewhere"}
            ).status_code
            == 404
        )
        assert "synthetic" in app.state.interactions._pending
        response = client.put("/api/canvas/profile", json={"profile_id": "Profile 1"})
        assert (
            response.status_code == 200
            and response.json()["profile_name"] == "Other synthetic profile"
        )
        assert service.profile_name() == "Other synthetic profile"
        assert not app.state.interactions._pending
        assert saved_settings.load_settings()["chrome_profile_path"] == profiles[1].path
        assert client.get("/api/canvas/profiles").json()["profiles"][1]["selected"]
        assert (
            client.put(
                "/api/canvas/profile",
                json={"profile_id": "Default"},
                headers={"X-Workbench-CSRF": "invalid"},
            ).status_code
            == 403
        )


def test_workspace_archive_is_reversible_and_preserves_content(client, app):
    workspace = client.post("/api/workspaces", json={"title": "Archive fixture"}).json()
    base = f"/api/workspaces/{workspace['id']}"
    source = client.post(
        base + "/sources/text",
        json={
            "title": "Evidence",
            "content": "Keep this source through archive and restore.",
        },
    ).json()
    archived = client.patch(base, json={"archived": True})
    assert archived.status_code == 200 and archived.json()["archived"] == 1
    assert client.get(base + f"/sources/{source['id']}").status_code == 200
    renamed = client.patch(base, json={"title": "Still archived"}).json()
    assert renamed["archived"] == 1
    app.state.repository.initialize()
    assert app.state.repository.get(workspace["id"])["archived"] == 1
    restored = client.patch(base, json={"archived": False})
    assert restored.json()["archived"] == 0
    assert client.get(base + "/sources").json()["sources"][0]["id"] == source["id"]
