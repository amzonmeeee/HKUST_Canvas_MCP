from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

SESSION_COOKIE = "hkust_workbench_session"


class LocalSecurityMiddleware(BaseHTTPMiddleware):
    """An exact loopback origin, launch session and separate mutation token."""

    def __init__(self, app, *, port: int, session_secret: str, csrf_secret: str):
        super().__init__(app)
        self.host = f"127.0.0.1:{port}"
        self.cookie_name = f"{SESSION_COOKIE}_{port}"
        self.origin = f"http://{self.host}"
        self.session_secret, self.csrf_secret = session_secret, csrf_secret

    @staticmethod
    def reject(code: str, message: str, status: int = 403):
        return JSONResponse(
            {"error": {"code": code, "message": message}}, status_code=status
        )

    async def dispatch(self, request: Request, call_next):
        if request.headers.get("host") != self.host:
            return self.reject(
                "invalid_host", "Use the loopback URL printed by canvas web.", 400
            )
        if request.headers.get("origin") not in (None, self.origin):
            return self.reject(
                "invalid_origin", "Requests must come from this local application."
            )
        if request.headers.get("sec-fetch-site") == "cross-site":
            return self.reject("invalid_origin", "Cross-site requests are blocked.")
        mutation = request.method not in {"GET", "HEAD", "OPTIONS"}
        if mutation and request.headers.get("origin") != self.origin:
            return self.reject("invalid_origin", "A same-origin header is required.")
        is_api = request.url.path == "/api" or request.url.path.startswith("/api/")
        bootstrap = request.url.path == "/api/session" and request.method == "POST"
        if is_api and not bootstrap:
            cookie = request.cookies.get(self.cookie_name, "")
            if not secrets.compare_digest(
                cookie.encode(), self.session_secret.encode()
            ):
                return self.reject(
                    "session_required",
                    "Open the launch URL printed by canvas web.",
                    401,
                )
            if mutation and not secrets.compare_digest(
                request.headers.get("x-workbench-csrf", "").encode(),
                self.csrf_secret.encode(),
            ):
                return self.reject(
                    "csrf_required", "Refresh this page before making changes."
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if is_api or not request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "no-store"
        return response
