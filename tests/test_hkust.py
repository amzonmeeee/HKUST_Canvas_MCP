from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from auth import CanvasAPIError
from auth.chrome_cookies import read_chrome_cookies
from auth.profiles import resolve_chrome_profile_path
from auth.resolve import HKUST_CANVAS_BASE_URL, resolve_canvas_base_url
from client import CanvasClient, create_canvas_client_from_env


def test_hkust_cookies_selected_among_other_sites(monkeypatch):
    cookies = [
        SimpleNamespace(name=name, value=value, domain=domain)
        for domain, session, csrf in [
            (".other.instructure.com", "other-session", "other-csrf"),
            (".canvas.ust.hk", "ust-session", "ust%2Bcsrf"),
        ]
        for name, value in [("canvas_session", session), ("_csrf_token", csrf)]
    ]
    monkeypatch.setattr("browser_cookie3.chrome", lambda **kwargs: cookies)
    assert read_chrome_cookies(resolve_canvas_base_url()) == ("ust-session", "ust%2Bcsrf")


def test_other_site_session_is_not_a_fallback(monkeypatch):
    cookies = [SimpleNamespace(name=name, value="secret", domain="other.instructure.com")
               for name in ("canvas_session", "_csrf_token")]
    monkeypatch.setattr("browser_cookie3.chrome", lambda **kwargs: cookies)
    assert read_chrome_cookies(HKUST_CANVAS_BASE_URL) is None


def test_client_requires_hkust_session(monkeypatch):
    monkeypatch.setattr("client.read_chrome_session_cookies", lambda *args, **kwargs: None)
    monkeypatch.setattr("auth.errors.list_canvas_cookie_domains", lambda **kwargs: ["other.instructure.com"])
    with pytest.raises(CanvasAPIError, match="No usable Canvas session.*canvas.ust.hk"):
        create_canvas_client_from_env(profile_path="/tmp/UST Profile")


def test_client_freezes_profile_but_refreshes_cookies(monkeypatch):
    reader = Mock(side_effect=[("session-one", "csrf"), ("session-two", "csrf")])
    monkeypatch.setattr("client.read_chrome_session_cookies", reader)
    monkeypatch.setenv("CANVAS_CHROME_PROFILE_PATH", "/tmp/UST Profile")
    client = create_canvas_client_from_env()
    monkeypatch.setenv("CANVAS_CHROME_PROFILE_PATH", "/tmp/Other Profile")
    assert client.cookie_provider() == ("session-two", "csrf")
    expected_path = str(Path("/tmp/UST Profile").resolve())
    assert client.profile_path == expected_path
    assert all(call.kwargs["profile_path"] == expected_path for call in reader.call_args_list)


def test_explicit_profile_name_does_not_use_saved_path(monkeypatch):
    monkeypatch.setattr("auth.profiles.resolve_selected_chrome_profile", lambda: ("Other", "/tmp/Other"))
    resolver = Mock(return_value=SimpleNamespace(path="/tmp/UST"))
    monkeypatch.setattr("auth.profiles.resolve_chrome_profile", resolver)
    assert resolve_chrome_profile_path(profile_name="UST") == "/tmp/UST"
    resolver.assert_called_once_with(profile_name="UST", profile_path=None)


def test_unknown_profile_does_not_fall_back(monkeypatch):
    monkeypatch.setattr("auth.profiles.resolve_chrome_profile", lambda **kwargs: None)
    with pytest.raises(CanvasAPIError, match="could not be resolved"):
        resolve_chrome_profile_path(profile_name="Missing")


@pytest.mark.parametrize("url", ["https://other.instructure.com", "http://canvas.ust.hk", "https://canvas.ust.hk.evil.test"])
def test_client_rejects_other_origins(url):
    with pytest.raises(CanvasAPIError, match="only supports"):
        CanvasClient(base_url=url)


def test_real_sdk_uses_chrome_cookies_and_decoded_csrf(monkeypatch):
    sent = []
    def send(session, request, **kwargs):
        sent.append(request)
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps({"id": 7, "name": "UST Student"}).encode()
        response.url = request.url
        response.request = request
        return response

    monkeypatch.setattr("requests.sessions.Session.send", send)
    client = CanvasClient(cookie_provider=lambda: ("ust-session", "token%2Bpart%3D"))
    user = client._call_canvas(lambda canvas: canvas.get_current_user(), "get current user")
    assert user.id == 7
    assert len(sent) == 1
    request = sent[0]
    assert request.url == "https://canvas.ust.hk/api/v1/users/self"
    assert "canvas_session=ust-session" in request.headers["Cookie"]
    assert "_csrf_token=token%2Bpart%3D" in request.headers["Cookie"]
    assert request.headers["X-CSRF-Token"] == "token+part="
    assert not request.headers.get("Authorization", "").strip().removeprefix("Bearer").strip()


def test_expired_cookies_stop_action_and_close_sdk_session(monkeypatch):
    action = Mock()
    close = Mock()
    monkeypatch.setattr("requests.sessions.Session.close", close)
    client = CanvasClient(cookie_provider=lambda: None)
    with pytest.raises(CanvasAPIError, match="No usable Chrome session"):
        client._run_with_canvas(action)
    action.assert_not_called()
    close.assert_called_once()


@pytest.mark.parametrize("status_code,content_type,expected", [
    (200, "application/json", "verified"),
    (302, "text/html", "not_logged_in"),
    (401, "application/json", "not_logged_in"),
    (200, "text/html", "unexpected_response"),
])
def test_auth_probe_checks_hkust_without_following_redirects(monkeypatch, status_code, content_type, expected):
    from auth.probe import get_auth_status

    monkeypatch.setattr("auth.probe.read_chrome_cookies", lambda *args, **kwargs: ("session", "csrf"))
    monkeypatch.setattr("auth.probe.list_canvas_cookie_domains_for_profile", lambda **kwargs: (["canvas.ust.hk"], None))
    response = requests.Response()
    response.status_code = status_code
    response.headers["content-type"] = content_type
    if status_code == 302:
        response.headers["location"] = "https://login.example.test"
    response._content = b"{}"
    get = Mock(return_value=response)
    monkeypatch.setattr("requests.sessions.Session.get", get)
    status = get_auth_status(profile_path="/tmp/UST Profile")
    assert status["auth_status"] == expected
    assert status["auth_verified"] is (expected == "verified")
    assert get.call_args.args == ("https://canvas.ust.hk/api/v1/users/self",)
    assert get.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("url", [
    "https://canvas.ust.hk/courses/123/assignments/42",
    "HTTPS://CANVAS.UST.HK:443/courses/123/assignments/42",
    "https://canvas.ust.hk:443/api/v1/courses/123/assignments/42",
    "/courses/123/assignments/42",
    "//canvas.ust.hk/courses/123/assignments/42",
])
def test_url_resolver_looks_up_hkust_urls_and_preserves_relative_paths(url, mock_client):
    from specs.registry import dispatch_tool_call

    mock_client.get_assignment.return_value = {"id": 42, "name": "UST Assignment"}
    result = dispatch_tool_call("resolve_canvas_url", {"url": url})
    assert "error" not in result
    assert result["details"] is not None
    assert result["resource_type"] == "assignment"
    assert mock_client.get_assignment.call_args.kwargs["course_id"] == "123"
    assert mock_client.get_assignment.call_args.kwargs["assignment_id"] == "42"


def test_url_resolver_preserves_plain_numeric_hkust_assignment_ids(mock_client):
    from specs.registry import dispatch_tool_call

    mock_client.get_assignment.return_value = {"id": 67890, "name": "UST Assignment"}
    result = dispatch_tool_call("resolve_canvas_url", {
        "url": "https://canvas.ust.hk/courses/12345/assignments/67890",
    })

    assert result["resource_id"] == "67890"
    assert result["resource_id_aliases"] == ["67890"]
    assert result["detail_error"] is None
    assert result["details"]["assignment"]["id"] == "67890"
    mock_client.get_assignment.assert_called_once_with(
        course_id="12345",
        assignment_id="67890",
        include_submission=False,
        include_discussion_topic=True,
    )


@pytest.mark.parametrize("fetch_details", [True, False])
@pytest.mark.parametrize("url", [
    "https://umd.instructure.com/courses/123/assignments/42",
    "https://school.instructure.com/courses/123/assignments/42",
    "https://canvas.other.edu/courses/123/assignments/42",
    "http://canvas.ust.hk/courses/123/assignments/42",
    "https://canvas.ust.hk:8443/courses/123/assignments/42",
    "https://canvas.ust.hk.evil.test/courses/123/assignments/42",
    "https://canvas.ust.hk@other.test/courses/123/assignments/42",
    "//other.instructure.com/courses/123/assignments/42",
    "https://[invalid/courses/123/assignments/42",
    "https://canvas.ust.hk:invalid/courses/123/assignments/42",
])
def test_url_resolver_rejects_foreign_origins_before_lookup(monkeypatch, mock_client, url, fetch_details):
    from specs.registry import dispatch_tool_call

    lookup = Mock()
    monkeypatch.setattr("tools.resolvers.resolve_canvas_resource_details", lookup)
    result = dispatch_tool_call("resolve_canvas_url", {"url": url, "fetch_details": fetch_details})
    assert result["error"] == "invalid_argument"
    lookup.assert_not_called()
    assert mock_client.mock_calls == []


@pytest.mark.parametrize("selection,expected_index,verified", [
    ("env_name", 1, True),
    ("env_path", 1, True),
    ("env_name_and_path", 2, True),
    ("saved_name", 1, True),
    ("saved_path", 2, True),
    ("default", 0, True),
    ("default", 0, False),
])
def test_profile_diagnostics_match_effective_authentication(monkeypatch, tmp_path, selection, expected_index, verified):
    from auth.chrome_cookies import ChromeProfile
    from auth.inspect import describe_chrome_profiles

    root = tmp_path / "Chrome"
    profiles = [ChromeProfile(name, str(root / directory), None) for name, directory in [
        ("Default", "Default"), ("UST", "Profile 1"), ("Other", "Profile 2"),
    ]]
    monkeypatch.delenv("CANVAS_CHROME_PROFILE", raising=False)
    monkeypatch.delenv("CANVAS_CHROME_PROFILE_PATH", raising=False)
    saved = {"chrome_profile_name": "Other", "chrome_profile_path": profiles[2].path}
    if selection == "env_name":
        monkeypatch.setenv("CANVAS_CHROME_PROFILE", "UST")
    elif selection == "env_path":
        monkeypatch.setenv("CANVAS_CHROME_PROFILE_PATH", profiles[1].path)
    elif selection == "env_name_and_path":
        monkeypatch.setenv("CANVAS_CHROME_PROFILE", "UST")
        monkeypatch.setenv("CANVAS_CHROME_PROFILE_PATH", profiles[2].path)
    elif selection == "saved_name":
        saved = {"chrome_profile_name": "UST"}
    elif selection == "saved_path":
        saved = {"chrome_profile_path": str(root / "Profile 1" / ".." / "Profile 2")}
    else:
        saved = {}

    monkeypatch.setattr("auth.profiles.load_settings", lambda: saved)
    monkeypatch.setattr("auth.profiles._default_chrome_user_data_dir", lambda: root)
    monkeypatch.setattr("auth.chrome_cookies.list_chrome_profiles", lambda **kwargs: profiles)
    monkeypatch.setattr("auth.inspect.list_chrome_profiles", lambda: profiles)
    monkeypatch.setattr("auth.inspect.list_canvas_cookie_domains", lambda **kwargs: ["canvas.ust.hk"])
    monkeypatch.setattr("auth.inspect.get_auth_status", lambda **kwargs: {
        "auth_status": "verified" if verified else "not_logged_in", "auth_verified": verified,
    })
    monkeypatch.setattr("client.read_chrome_session_cookies", lambda *args, **kwargs: ("session", "csrf"))

    client = create_canvas_client_from_env()
    diagnostics = describe_chrome_profiles()
    selected = [profile for profile in diagnostics if profile["selected"]]
    assert len(selected) == 1
    assert Path(selected[0]["path"]).resolve() == Path(client.profile_path).resolve()
    assert selected[0]["path"] == profiles[expected_index].path
    assert selected[0]["active"] is verified
    assert all(not profile["active"] for profile in diagnostics if not profile["selected"])


@pytest.mark.parametrize("env_value", [None, "https://other.instructure.com"])
def test_base_url_diagnostics_distinguish_fixed_site_from_ignored_env(monkeypatch, env_value):
    from auth.probe import get_auth_status

    if env_value is None:
        monkeypatch.delenv("CANVAS_BASE_URL", raising=False)
    else:
        monkeypatch.setenv("CANVAS_BASE_URL", env_value)
    monkeypatch.setattr("auth.probe.read_chrome_cookies", lambda *args, **kwargs: None)
    monkeypatch.setattr("auth.probe.list_canvas_cookie_domains_for_profile", lambda **kwargs: ([], None))
    monkeypatch.setattr("auth.probe.missing_chrome_session_error", lambda *args, **kwargs: CanvasAPIError("No session"))
    status = get_auth_status(profile_path="/tmp/UST Profile")
    assert status["configured_canvas_base_url"] == HKUST_CANVAS_BASE_URL
    assert status["resolved_canvas_base_url"] == HKUST_CANVAS_BASE_URL
    assert status["canvas_base_url_source"] == "fixed_hkust"
    assert status["ignored_canvas_base_url_env"] == env_value
