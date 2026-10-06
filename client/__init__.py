from __future__ import annotations

from auth import (
    missing_chrome_session_error,
    read_chrome_session_cookies,
    resolve_canvas_base_url,
)

from auth.profiles import resolve_chrome_profile_path
from auth.resolve import require_hkust_canvas_url

from .assignments import CanvasAssignmentsMixin
from .activity import CanvasActivityMixin
from .base import CanvasClientBase
from .content import CanvasContentMixin
from .courses import CanvasCoursesMixin
from .submissions_write import CanvasSubmissionsWriteMixin


class CanvasClient(
    CanvasActivityMixin,
    CanvasCoursesMixin,
    CanvasAssignmentsMixin,
    CanvasSubmissionsWriteMixin,
    CanvasContentMixin,
    CanvasClientBase,
):
    pass


def create_canvas_client_from_env(
    *, base_url: str | None = None, profile_path: str | None = None
) -> CanvasClient:
    base_url = require_hkust_canvas_url(base_url or resolve_canvas_base_url())
    profile_path = resolve_chrome_profile_path(profile_path=profile_path)
    cookies = read_chrome_session_cookies(base_url, profile_path=profile_path)
    if cookies:
        return CanvasClient(
            base_url=base_url,
            profile_path=profile_path,
            cookie_provider=lambda: read_chrome_session_cookies(
                base_url, profile_path=profile_path
            ),
        )
    raise missing_chrome_session_error(base_url, profile_path=profile_path)
