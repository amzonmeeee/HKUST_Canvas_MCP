from __future__ import annotations

import secrets
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .db import SCHEMA_VERSION, WorkspaceRepository, default_data_dir
from .security import SESSION_COOKIE, LocalSecurityMiddleware
from .services.canvas import CanvasService, CanvasServiceError


class WorkspaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["custom", "canvas_course"] = "custom"
    title: str | None = Field(default=None, max_length=160)
    description: str = Field(default="", max_length=2000)
    canvas_course_id: str | None = Field(default=None, pattern=r"^[0-9]{1,30}$")

    @model_validator(mode="after")
    def validate_kind(self):
        if self.kind == "canvas_course":
            if not self.canvas_course_id or self.title is not None or self.description:
                raise ValueError(
                    "A course workspace requires only canvas_course_id and kind."
                )
        elif (
            self.canvas_course_id is not None
            or not self.title
            or not self.title.strip()
        ):
            raise ValueError(
                "A custom workspace requires a title and no Canvas course ID."
            )
        if self.title is not None:
            self.title = self.title.strip()
        return self


class WorkspaceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    archived: bool = False

    @field_validator("title", "description")
    @classmethod
    def non_null(cls, value, info):
        if value is None:
            raise ValueError("Fields cannot be null.")
        if info.field_name == "title":
            value = value.strip()
            if not value:
                raise ValueError("Title cannot be blank.")
        return value


def create_app(
    *,
    data_dir: Path | None = None,
    port: int = 8765,
    launch_secret: str | None = None,
    canvas_service: CanvasService | None = None,
    static_dir: Path | None = None,
    secret_store=None,
    provider_factory=None,
) -> FastAPI:
    repository = WorkspaceRepository(data_dir or default_data_dir())
    from .store import StudyStore

    canvas = canvas_service or CanvasService(configured=lambda: StudyStore(repository).setting("canvas_enabled"))
    launch_secret = launch_secret or secrets.token_urlsafe(32)
    session_secret, csrf_secret = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    assets = static_dir or Path(__file__).parent / "static"

    @asynccontextmanager
    async def lifespan(app):
        from .observability import configure_logging

        configure_logging()
        repository.initialize()
        yield

    app = FastAPI(
        title="HKUST Canvas Workbench",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.repository = repository
    app.add_middleware(
        LocalSecurityMiddleware,
        port=port,
        session_secret=session_secret,
        csrf_secret=csrf_secret,
    )

    @app.exception_handler(CanvasServiceError)
    async def canvas_error(request, exc):
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}},
            status_code=exc.status_code,
        )

    @app.exception_handler(sqlite3.Error)
    async def database_error(request, exc):
        return JSONResponse(
            {
                "error": {
                    "code": "database_error",
                    "message": "Local workspace storage is unavailable. Restart canvas web and retry.",
                }
            },
            status_code=503,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # FastAPI's default validation response echoes input, including API keys.
        return JSONResponse(
            {
                "error": {
                    "code": "invalid_request",
                    "message": "Check the request fields and try again.",
                }
            },
            status_code=422,
        )

    @app.post("/api/session")
    def establish_session(request: Request, response: Response):
        bearer = request.headers.get("authorization", "")
        if not secrets.compare_digest(
            bearer.encode(), f"Bearer {launch_secret}".encode()
        ):
            raise HTTPException(
                status_code=401, detail="Use the launch URL printed by canvas web."
            )
        response.set_cookie(
            f"{SESSION_COOKIE}_{port}",
            session_secret,
            httponly=True,
            samesite="strict",
            path="/",
        )
        return {"csrf_token": csrf_secret}

    @app.get("/api/session")
    def session():
        return {"csrf_token": csrf_secret}

    @app.get("/api/settings")
    def settings():
        return {
            "phase": "v3",
            "canvas_url": "https://canvas.ust.hk",
            "profile_name": canvas.profile_name(),
            "storage": "Local application data directory",
            "schema_version": SCHEMA_VERSION,
            "mcp_command": "canvas-mcp --transport stdio",
            "providers_available": True,
        }

    @app.get("/api/canvas/status")
    def canvas_status():
        return canvas.status()

    @app.get("/api/canvas/courses")
    def courses():
        return canvas.courses()

    @app.get("/api/canvas/courses/{course_id}")
    def course(course_id: str):
        if not course_id.isascii() or not course_id.isdecimal() or len(course_id) > 30:
            raise HTTPException(
                status_code=422, detail="Invalid Canvas course identifier."
            )
        return canvas.course(course_id)

    @app.get("/api/workspaces")
    def workspaces():
        return {"workspaces": repository.list()}

    @app.post("/api/workspaces", status_code=201)
    def create_workspace(payload: WorkspaceCreate):
        if payload.kind == "canvas_course":
            existing = repository.for_course(payload.canvas_course_id)
            if existing:
                return existing
            course_data = canvas.course(payload.canvas_course_id)
            if course_data["id"] != payload.canvas_course_id:
                raise CanvasServiceError(
                    "invalid_canvas_response", "Canvas returned a different course."
                )
            return repository.create(title=course_data["name"], course=course_data)
        return repository.create(title=payload.title, description=payload.description)

    def require_workspace(workspace_id: UUID):
        result = repository.get(str(workspace_id))
        if not result:
            raise HTTPException(status_code=404, detail="Workspace not found.")
        return result

    @app.get("/api/workspaces/{workspace_id}")
    def workspace(workspace_id: UUID):
        return require_workspace(workspace_id)

    @app.patch("/api/workspaces/{workspace_id}")
    def update_workspace(workspace_id: UUID, payload: WorkspaceUpdate):
        require_workspace(workspace_id)
        result = repository.update(
            str(workspace_id), payload.model_dump(exclude_unset=True)
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Workspace not found.")
        return result

    @app.delete("/api/workspaces/{workspace_id}", status_code=204)
    def delete_workspace(workspace_id: UUID):
        require_workspace(workspace_id)
        source_ids = [s["id"] for s in app.state.study_store.sources(str(workspace_id))]
        if not repository.delete(str(workspace_id)):
            raise HTTPException(status_code=404, detail="Workspace not found.")
        for source_id in source_ids:
            app.state.sources.remove_files(source_id)
        for preview in app.state.interactions.previews(str(workspace_id)):
            app.state.interactions.cancel(str(workspace_id), preview["id"])
        return Response(status_code=204)

    from .routes import register_study_routes

    register_study_routes(
        app,
        repository,
        canvas,
        secret_store=secret_store,
        provider_factory=provider_factory,
    )

    if (assets / "assets").is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets / "assets", follow_symlink=False),
            name="assets",
        )

    def shell():
        if not (assets / "index.html").is_file():
            return JSONResponse(
                {
                    "error": {
                        "code": "frontend_missing",
                        "message": "Build the frontend with npm run build in web/, then restart canvas web.",
                    }
                },
                status_code=503,
            )
        return FileResponse(assets / "index.html")

    app.add_api_route("/", shell, methods=["GET"], include_in_schema=False)
    app.add_api_route("/settings", shell, methods=["GET"], include_in_schema=False)

    @app.get("/workspace/{workspace_id}", include_in_schema=False)
    def workspace_shell(workspace_id: UUID):
        return shell()

    return app
