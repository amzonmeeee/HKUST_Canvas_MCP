from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import CanvasAPIError
from .profiles import resolve_chrome_profile_path
from .resolve import require_hkust_canvas_url, resolve_canvas_base_url


def capture_auth_context() -> dict[str, str]:
    return {
        "base_url": resolve_canvas_base_url(),
        "profile_path": resolve_chrome_profile_path(),
    }


def validate_auth_context(context: Any) -> dict[str, str]:
    if not isinstance(context, dict):
        raise CanvasAPIError("Saved Canvas/profile context is missing. Create a new preview.")
    base_url = context.get("base_url")
    profile_path = context.get("profile_path")
    if not isinstance(base_url, str) or not isinstance(profile_path, str) or not profile_path:
        raise CanvasAPIError("Saved Canvas/profile context is incomplete. Create a new preview.")
    if not Path(profile_path).is_absolute():
        raise CanvasAPIError("Saved Chrome profile path must be absolute.")
    return {"base_url": require_hkust_canvas_url(base_url), "profile_path": profile_path}
