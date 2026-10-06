from __future__ import annotations

from .errors import CanvasAPIError
from .urls import canvas_root_url

HKUST_CANVAS_BASE_URL = "https://canvas.ust.hk"


def require_hkust_canvas_url(base_url: str) -> str:
    try:
        root = canvas_root_url(base_url)
    except ValueError as exc:
        raise CanvasAPIError(str(exc)) from exc
    if root != HKUST_CANVAS_BASE_URL:
        raise CanvasAPIError(f"This project only supports {HKUST_CANVAS_BASE_URL}.")
    return HKUST_CANVAS_BASE_URL


def resolve_canvas_base_url(
    *,
    profile_name: str | None = None,
    profile_path: str | None = None,
) -> str:
    """Always target HKUST, regardless of other sessions or environment settings."""
    return HKUST_CANVAS_BASE_URL
