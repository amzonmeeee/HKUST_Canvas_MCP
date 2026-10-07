from __future__ import annotations

import os
from pathlib import Path

from .chrome_cookies import _default_chrome_user_data_dir, resolve_chrome_profile
from .settings import is_canvas_unlinked, load_settings


def require_connected_profile() -> None:
    if is_canvas_unlinked():
        from .errors import CanvasAPIError

        raise CanvasAPIError(
            "Canvas profile is unlinked. Choose a profile in Settings or run "
            "canvas settings choose-profile before using Canvas."
        )


def resolve_selected_chrome_profile() -> tuple[str | None, str | None]:
    if is_canvas_unlinked():
        return None, None
    profile_name = os.getenv("CANVAS_CHROME_PROFILE", "").strip() or None
    profile_path = os.getenv("CANVAS_CHROME_PROFILE_PATH", "").strip() or None
    if profile_name or profile_path:
        return profile_name, profile_path

    settings = load_settings()
    return (
        settings.get("chrome_profile_name") or None,
        settings.get("chrome_profile_path") or None,
    )


def resolve_chrome_profile_path(
    *,
    profile_name: str | None = None,
    profile_path: str | None = None,
) -> str:
    require_connected_profile()
    if profile_name is None and profile_path is None:
        profile_name, profile_path = resolve_selected_chrome_profile()
    if not profile_name and not profile_path:
        root = _default_chrome_user_data_dir()
        if root is not None:
            return str(root / "Default")
    if profile_path:
        return str(Path(profile_path).expanduser().resolve())
    resolved = resolve_chrome_profile(
        profile_name=profile_name,
        profile_path=profile_path,
    )
    if resolved is None:
        from .errors import CanvasAPIError

        raise CanvasAPIError(
            f"Chrome profile could not be resolved: {profile_name or 'Default'}"
        )
    return resolved.path
