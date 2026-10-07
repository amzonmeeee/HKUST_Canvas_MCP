from __future__ import annotations

from auth.errors import (
    CanvasAPIError,
    missing_chrome_session_error,
)
from auth.probe import get_auth_status
from auth.profiles import require_connected_profile
from auth.resolve import resolve_canvas_base_url
from auth.session import (
    apply_chrome_session_to_http_session,
    read_chrome_session_cookies,
)


def ensure_canvas_auth_configured() -> str:
    require_connected_profile()
    base_url = resolve_canvas_base_url()
    if read_chrome_session_cookies(base_url):
        return "chrome-session"
    raise missing_chrome_session_error(base_url)

__all__ = [
    "CanvasAPIError",
    "apply_chrome_session_to_http_session",
    "ensure_canvas_auth_configured",
    "get_auth_status",
    "missing_chrome_session_error",
    "read_chrome_session_cookies",
    "resolve_canvas_base_url",
]
