from __future__ import annotations

import os
from pathlib import Path
from threading import RLock

from auth import get_auth_status
from auth.chrome_cookies import list_chrome_profiles
from auth.profiles import resolve_selected_chrome_profile
from auth.settings import (
    is_canvas_unlinked,
    set_selected_profile,
    unlink_selected_profile,
)
from specs.registry import dispatch_tool_call
from tools.common import canvas_client, reset_canvas_client


class CanvasServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 502):
        super().__init__(message)
        self.code, self.status_code = code, status_code


class CanvasService:
    """Reuse registered v2 handlers; expose only the fields this UI needs."""

    def __init__(self, configured=None):
        self._profile_context = None
        self._lock = RLock()
        self._configured = configured or (lambda: True)

    def status(self) -> dict:
        with self._lock:
            return self._status()

    def profiles(self):
        with self._lock:
            name, path = resolve_selected_chrome_profile()
            unlinked = is_canvas_unlinked()
            return {
                "unlinked": unlinked,
                "profiles": [
                    {
                        "id": Path(p.path).name,
                        "name": p.name,
                        "location": f"Chrome / {Path(p.path).name}",
                        "selected": False
                        if unlinked
                        else str(Path(p.path)) == str(path)
                        if path
                        else p.name == name
                        or (not name and Path(p.path).name == "Default"),
                    }
                    for p in list_chrome_profiles()
                ],
            }

    def choose_profile(self, profile_id):
        with self._lock:
            profile = next(
                (p for p in list_chrome_profiles() if Path(p.path).name == profile_id),
                None,
            )
            if profile is None:
                raise CanvasServiceError(
                    "profile_not_found",
                    "This Chrome profile is no longer available. Refresh the profile list.",
                    404,
                )
            set_selected_profile(name=profile.name, path=profile.path)
            # An explicit in-app choice supersedes this process's launch overrides.
            os.environ.pop("CANVAS_CHROME_PROFILE", None)
            os.environ.pop("CANVAS_CHROME_PROFILE_PATH", None)
            reset_canvas_client()
            self._profile_context = None
            return {"profile_name": profile.name, "saved": True}

    def unlink_profile(self):
        with self._lock:
            try:
                unlink_selected_profile()
            except OSError as exc:
                raise CanvasServiceError(
                    "canvas_settings_unavailable",
                    "The Canvas profile could not be unlinked. Check settings folder permissions, then retry.",
                    503,
                ) from exc
            reset_canvas_client()
            self._profile_context = None
            return {"unlinked": True, "cached_data_retained": True}

    def _require_connected(self):
        if is_canvas_unlinked() or not self._configured():
            raise CanvasServiceError(
                "canvas_unconfigured",
                "Canvas is not connected. Choose a Chrome profile to reconnect.",
                409,
            )

    def _status(self) -> dict:
        if is_canvas_unlinked() or not self._configured():
            return {
                "auth_verified": False,
                "auth_status": "unconfigured",
                "profile_name": None,
                "message": "Canvas is not connected. Choose a Chrome profile to reconnect. Saved workspaces and sources are kept.",
            }
        try:
            result = get_auth_status()
        # Browser/keychain adapters raise platform-specific errors. Their raw
        # details must not cross the local HTTP privacy boundary.
        except Exception:  # noqa: BLE001
            return {
                "auth_verified": False,
                "auth_status": "unavailable",
                "profile_name": self.profile_name(),
                "message": "Canvas could not be checked. Open HKUST Canvas in Chrome, then retry.",
            }
        verified = result.get("auth_verified") is True
        unavailable = result.get("auth_status") in {
            "probe_failed",
            "unexpected_response",
        }
        return {
            "auth_verified": verified,
            "auth_status": "verified"
            if verified
            else "unavailable"
            if unavailable
            else "sign_in_required",
            "profile_name": self.profile_name(),
            "message": "Connected through Chrome."
            if verified
            else "Canvas could not be reached. Check your network and Chrome session, then retry."
            if unavailable
            else "Sign in to HKUST Canvas in your selected Chrome profile, then retry.",
            **({"account": result["account"]} if verified and isinstance(result.get("account"), dict) else {}),
        }

    @staticmethod
    def profile_name() -> str | None:
        name, path = resolve_selected_chrome_profile()
        return name or ("Selected by profile path" if path else None)

    def _invoke(self, name: str, args: dict) -> dict:
        with self._lock:
            self._require_connected()
            context = resolve_selected_chrome_profile()
            if context != self._profile_context:
                reset_canvas_client()
                self._profile_context = context
            result = dispatch_tool_call(name, args)
        if "error" in result:
            status = result.get("status_code")
            if result["error"] == "forbidden":
                raise CanvasServiceError(
                    "canvas_access_denied",
                    "Canvas denied access. Check your Chrome session and course permissions, then retry.",
                    403,
                )
            if status == 403 or result["error"] == "permission_denied":
                raise CanvasServiceError(
                    "canvas_permission_denied",
                    "Canvas denied access to this resource.",
                    403,
                )
            if status == 404 or result["error"] == "not_found":
                raise CanvasServiceError(
                    "canvas_not_found",
                    "This Canvas course is no longer available.",
                    404,
                )
            if status == 401 or result["error"] == "auth_error":
                raise CanvasServiceError(
                    "canvas_auth_expired",
                    "Sign in to HKUST Canvas in Chrome, then retry.",
                    401,
                )
            raise CanvasServiceError(
                "canvas_unavailable",
                "Canvas is unavailable. Check your Chrome session and network, then retry.",
            )
        return result

    def client_call(self, method: str, **args):
        """Internal adapter, never exposed as an arbitrary HTTP method dispatcher."""
        from auth import CanvasAPIError

        with self._lock:
            self._require_connected()
            context = resolve_selected_chrome_profile()
            if context != self._profile_context:
                reset_canvas_client()
                self._profile_context = context
            try:
                return getattr(canvas_client(), method)(**args)
            except CanvasAPIError as exc:
                status = exc.status_code or 502
                code = {
                    401: "canvas_auth_expired",
                    403: "canvas_permission_denied",
                    404: "canvas_not_found",
                }.get(status, "canvas_unavailable")
                raise CanvasServiceError(
                    code,
                    "Canvas could not provide this source. Check your Chrome session and course permissions.",
                    status,
                ) from exc
            except Exception as exc:
                raise CanvasServiceError(
                    "canvas_unavailable",
                    "Canvas could not provide this source. Check your network and retry.",
                ) from exc

    def courses(self) -> dict:
        result = self._invoke("list_courses", {"favorites_only": False, "limit": 300})
        courses = [self._course(row) for row in result.get("courses", [])]
        return {
            "courses": courses,
            "count": len(courses),
            "truncated": len(courses) >= 300,
        }

    def course(self, course_id: str) -> dict:
        row = self._invoke("get_course_overview", {"course_id": course_id})["course"]
        return self._course({**row, "term_name": (row.get("term") or {}).get("name")})

    @staticmethod
    def _course(row: dict) -> dict:
        course_id = str(row["id"])
        if not course_id.isascii() or not course_id.isdecimal():
            raise CanvasServiceError(
                "invalid_canvas_response",
                "Canvas returned an invalid course identifier.",
            )
        return {
            "id": course_id,
            "name": str(row.get("name") or "Untitled course"),
            "course_code": row.get("course_code"),
            "term_name": row.get("term_name"),
            "canvas_url": f"https://canvas.ust.hk/courses/{course_id}",
        }
