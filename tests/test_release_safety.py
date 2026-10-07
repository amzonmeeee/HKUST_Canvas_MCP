"""Release safety regressions: isolated settings, synthetic profiles, no live writes."""

import asyncio
import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from auth import CanvasAPIError, get_auth_status, settings
from auth.chrome_cookies import ChromeProfile
from auth.profiles import resolve_chrome_profile_path, resolve_selected_chrome_profile
from canvas_mcp import server
from client import CanvasClient
from specs.registry import dispatch_tool_call
from webapp.api import create_app
from webapp.services.canvas import CanvasService, CanvasServiceError


@pytest.fixture
def profile_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(settings, "CONFIG_PATH", tmp_path / "config/settings.json")
    monkeypatch.delenv("CANVAS_CHROME_PROFILE", raising=False)
    monkeypatch.delenv("CANVAS_CHROME_PROFILE_PATH", raising=False)
    profile = tmp_path / "Chrome/Default"
    profile.mkdir(parents=True)
    (profile / "Cookies").write_bytes(b"synthetic-browser-cookie-data")
    settings.set_selected_profile(name="Synthetic profile", path=str(profile))
    return profile


@pytest.fixture
def mcp_permissions(monkeypatch):
    monkeypatch.delenv("CANVAS_MCP_ALLOW_WRITES", raising=False)
    server.configure_permissions(allow_writes=False)
    yield
    server.configure_permissions(allow_writes=False)


@pytest.mark.parametrize("override", ["none", "env_name", "env_path", "explicit"])
def test_unlink_blocks_fallbacks_and_survives_settings_clear(
    profile_settings, monkeypatch, override
):
    settings.unlink_selected_profile()
    if override == "env_name":
        monkeypatch.setenv("CANVAS_CHROME_PROFILE", "Synthetic profile")
    if override == "env_path":
        monkeypatch.setenv("CANVAS_CHROME_PROFILE_PATH", str(profile_settings))
    assert resolve_selected_chrome_profile() == (None, None)
    args = {"profile_path": str(profile_settings)} if override == "explicit" else {}
    with pytest.raises(CanvasAPIError, match="unlinked"):
        resolve_chrome_profile_path(**args)
    assert get_auth_status(**args)["auth_status"] == "unconfigured"
    settings.clear_settings()
    assert settings.load_settings() == {"canvas_connection": "unlinked"}
    assert (
        profile_settings / "Cookies"
    ).read_bytes() == b"synthetic-browser-cookie-data"


def test_failed_atomic_unlink_keeps_previous_setting(profile_settings, monkeypatch):
    old = settings.CONFIG_PATH.read_bytes()
    monkeypatch.setattr(
        settings.os, "replace", Mock(side_effect=OSError("synthetic failure"))
    )
    with pytest.raises(OSError):
        settings.unlink_selected_profile()
    assert settings.CONFIG_PATH.read_bytes() == old
    assert not list(settings.CONFIG_DIR.glob("settings-*"))
    with pytest.raises(CanvasServiceError) as error:
        CanvasService().unlink_profile()
    assert error.value.code == "canvas_settings_unavailable"
    assert error.value.status_code == 503


def test_unlink_stops_cached_client_and_registry_dispatch(
    profile_settings, monkeypatch
):
    cookie_provider = Mock(return_value=("synthetic-session", "synthetic-csrf"))
    client = CanvasClient(
        cookie_provider=cookie_provider, profile_path=str(profile_settings)
    )
    handler = Mock(return_value={"unexpected": True})
    from specs import registry
    from specs.schema import tool_spec

    monkeypatch.setitem(
        registry._SPEC_MAP,
        "synthetic_canvas_read",
        tool_spec(
            name="synthetic_canvas_read", description="Synthetic read", handler=handler
        ),
    )
    settings.unlink_selected_profile()
    with pytest.raises(CanvasAPIError, match="unlinked"):
        client._run_with_canvas(Mock())
    cookie_provider.assert_not_called()
    assert dispatch_tool_call("synthetic_canvas_read")["error"] == "canvas_unconfigured"
    handler.assert_not_called()
    assert "error" not in dispatch_tool_call("get_today")


def test_cli_profile_discovery_after_unlink_never_reads_cookies(
    profile_settings, monkeypatch
):
    from auth.inspect import describe_chrome_profiles

    monkeypatch.setattr(
        "auth.inspect.list_chrome_profiles",
        lambda: [
            ChromeProfile(
                "Synthetic profile",
                str(profile_settings),
                str(profile_settings / "Cookies"),
            )
        ],
    )
    forbidden = Mock(side_effect=AssertionError("No cookie access after unlink"))
    monkeypatch.setattr("auth.inspect.list_canvas_cookie_domains", forbidden)
    settings.unlink_selected_profile()
    profiles = describe_chrome_profiles()
    assert profiles[0]["auth_status"] == "unconfigured"
    assert profiles[0]["selected"] is False
    forbidden.assert_not_called()


def test_unlink_api_requires_session_csrf_preserves_workspace_and_relinks(
    profile_settings, tmp_path, monkeypatch
):
    profile2 = tmp_path / "Chrome/Profile 1"
    profile2.mkdir()
    profiles = [
        ChromeProfile("Synthetic profile", str(profile_settings), None),
        ChromeProfile("Another synthetic profile", str(profile2), None),
    ]
    monkeypatch.setattr("webapp.services.canvas.list_chrome_profiles", lambda: profiles)
    probe = Mock(return_value={"auth_verified": True})
    monkeypatch.setattr("webapp.services.canvas.get_auth_status", probe)
    dispatch = Mock(return_value={"count": 0, "courses": []})
    monkeypatch.setattr("webapp.services.canvas.dispatch_tool_call", dispatch)
    cached = Mock()
    monkeypatch.setattr("webapp.services.canvas.canvas_client", cached)
    service = CanvasService()
    app = create_app(
        data_dir=tmp_path / "workbench",
        launch_secret="synthetic-launch",
        canvas_service=service,
    )
    origin = "http://127.0.0.1:8765"
    with TestClient(app, base_url=origin) as client:
        assert (
            client.delete("/api/canvas/profile", headers={"Origin": origin}).status_code
            == 401
        )
        token = client.post(
            "/api/session",
            headers={"Origin": origin, "Authorization": "Bearer synthetic-launch"},
        ).json()["csrf_token"]
        assert (
            client.delete("/api/canvas/profile", headers={"Origin": origin}).status_code
            == 403
        )
        client.headers.update({"Origin": origin, "X-Workbench-CSRF": token})
        workspace = client.post(
            "/api/workspaces", json={"title": "Synthetic saved work"}
        ).json()
        source = client.post(
            f"/api/workspaces/{workspace['id']}/sources/text",
            json={
                "title": "Synthetic cached source",
                "content": "Synthetic course excerpt kept after unlink.",
            },
        ).json()
        source_url = f"/api/workspaces/{workspace['id']}/sources/{source['id']}"
        cached_source = client.get(source_url).json()
        workspace = client.get(f"/api/workspaces/{workspace['id']}").json()
        app.state.interactions._pending["synthetic-preview"] = {"deadline": 10**30}
        response = client.delete("/api/canvas/profile")
        assert response.json() == {"unlinked": True, "cached_data_retained": True}
        assert app.state.interactions._pending == {}
        assert client.get("/api/canvas/status").json()["auth_status"] == "unconfigured"
        assert client.get("/api/canvas/courses").status_code == 409
        with pytest.raises(CanvasServiceError, match="not connected"):
            service.client_call("list_courses")
        cached.assert_not_called()
        dispatch.assert_not_called()
        probe.assert_not_called()
        assert client.get(f"/api/workspaces/{workspace['id']}").json() == workspace
        assert client.get(source_url).json() == cached_source
        result = client.get("/api/canvas/profiles").json()
        assert result["unlinked"] is True and not any(
            p["selected"] for p in result["profiles"]
        )
        assert client.delete("/api/canvas/profile").status_code == 200
        settings_file = json.loads(settings.CONFIG_PATH.read_text())
        assert settings_file == {"canvas_connection": "unlinked"}
        assert (
            client.put(
                "/api/canvas/profile", json={"profile_id": "Profile 1"}
            ).status_code
            == 200
        )
        assert not settings.is_canvas_unlinked()
        assert resolve_chrome_profile_path() == str(profile2)
        assert client.get("/api/canvas/status").json()["auth_verified"] is True
        assert (
            profile_settings / "Cookies"
        ).read_bytes() == b"synthetic-browser-cookie-data"


def test_mcp_read_only_hides_all_mutations_and_stale_tool_cannot_dispatch(
    mcp_permissions, monkeypatch
):
    expected = {
        "post_discussion_entry",
        "reply_to_discussion_entry",
        "add_submission_comment",
        "send_conversation",
        "reply_to_conversation",
        "update_conversation",
        "mark_module_item_done",
        "confirm_assignment_submission",
        "cancel_scheduled_submission",
    }
    assert server.WRITE_TOOL_NAMES == expected
    visible = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert not visible.intersection(expected)
    assert {
        "list_courses",
        "get_course_structure",
        "preview_assignment_submission",
    } <= visible
    server.configure_permissions(allow_writes=True)
    stale = asyncio.run(server.mcp.get_tool("send_conversation"))
    dispatch = Mock(return_value={"status": "preview", "written": False})
    monkeypatch.setattr(server, "dispatch_tool_call", dispatch)
    assert (
        stale.fn(recipients=["1"], subject="Synthetic", body="Synthetic")["written"]
        is False
    )
    dispatch.assert_called_once()
    dispatch.reset_mock()
    server.configure_permissions(allow_writes=False)
    assert (
        stale.fn(recipients=["1"], subject="Synthetic", body="Synthetic")["error"]
        == "mcp_read_only"
    )
    dispatch.assert_not_called()


@pytest.mark.parametrize(
    "args,env,enabled",
    [
        ([], "", False),
        ([], "0", False),
        ([], "false", False),
        ([], "1", True),
        ([], "true", True),
        (["--allow-writes"], "0", True),
        (["--read-only"], "1", False),
    ],
)
def test_mcp_permission_opt_in_and_flag_precedence(
    mcp_permissions, monkeypatch, args, env, enabled
):
    monkeypatch.setenv("CANVAS_MCP_ALLOW_WRITES", env)
    monkeypatch.setattr(server, "ensure_canvas_auth_configured", Mock())
    monkeypatch.setattr(server.mcp, "run", Mock())
    server.main(args)
    visible = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert bool(visible.intersection(server.WRITE_TOOL_NAMES)) is enabled


def test_invalid_mcp_permission_fails_before_auth_or_server(
    mcp_permissions, monkeypatch
):
    monkeypatch.setenv("CANVAS_MCP_ALLOW_WRITES", "yes-please")
    auth, run = Mock(), Mock()
    monkeypatch.setattr(server, "ensure_canvas_auth_configured", auth)
    monkeypatch.setattr(server.mcp, "run", run)
    with pytest.raises(SystemExit) as error:
        server.main([])
    assert error.value.code == 2
    auth.assert_not_called()
    run.assert_not_called()


def test_generated_mcp_setup_pins_read_only_without_forwarding_secrets(monkeypatch):
    from webapp.local_clients import mcp_launcher

    monkeypatch.setenv("CANVAS_MCP_ALLOW_WRITES", "1")
    result = mcp_launcher("Synthetic profile")
    assert "--read-only" in result["args"]
    assert result["env"] == {"CANVAS_CHROME_PROFILE": "Synthetic profile"}
