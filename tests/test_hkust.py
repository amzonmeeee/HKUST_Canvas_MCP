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
