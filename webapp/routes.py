from __future__ import annotations

from dataclasses import asdict
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .native_providers import (
    KINDS,
    ClaudeCodeProvider,
    CodexProvider,
    find_cli,
    inspect_login,
)
from .parsers import MAX_FILE_BYTES, ParseError
from .providers import (
    Capabilities,
    HTTPProvider,
    KeychainSecrets,
    ProviderError,
    validate_base_url,
)
from .services.canvas import CanvasServiceError
from .services.interactions import InteractionService
from .services.sources import SourceService
from .services.study import StudyService, artifact_markdown
from .source_preview import reading_text
from .store import StudyStore


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceSelection(StrictModel):
    source_ids: list[UUID] = Field(max_length=300)
    force: bool = False


class TextSource(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=200000)


class ProviderConfig(StrictModel):
    id: UUID | None = None
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["openai", "anthropic", "compatible", "codex", "claude_code"]
    model: str = Field(min_length=1, max_length=160)
    base_url: str = Field(default="", max_length=500)
    api_key: str | None = Field(default=None, max_length=1000)
    remove_key: bool = False
    streaming: bool = True
    native_tools: bool = False
    structured_output: bool = False

    @field_validator("name", "model")
    @classmethod
    def clean_string(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("Enter a nonempty name without control characters.")
        return value.strip()

    @field_validator("api_key")
    @classmethod
    def clean_key(cls, value):
        if value is not None and (not value.strip() or any(ord(c) < 32 for c in value)):
            raise ValueError("Enter a valid API key or leave it blank.")
        return value.strip() if value is not None else None


class ChatRequest(StrictModel):
    provider_id: UUID
    conversation_id: UUID | None = None
    source_ids: list[UUID] = Field(default_factory=list, max_length=300)
    message: str = Field(min_length=1, max_length=12000)
    live_tools: bool = False
    temporary: bool = False


class GenerateRequest(StrictModel):
    provider_id: UUID
    source_ids: list[UUID] = Field(max_length=300)
    kind: Literal[
        "quiz",
        "flashcards",
        "study_guide",
        "document",
        "spreadsheet",
        "mindmap",
        "slides",
        "infographic",
    ]
    topic: str = Field(default="", max_length=1000)
    count: int = Field(default=5, ge=1, le=20)
    difficulty: Literal["introductory", "intermediate", "advanced"] = "intermediate"
    prompt: str = Field(default="", max_length=6000)
    template: Literal[
        "automatic", "study_notes", "revision_outline", "analysis_report"
    ] = "automatic"
    language: Literal["automatic", "en", "zh-Hant", "zh-Hans"] = "automatic"
    orientation: Literal["landscape", "portrait", "square"] = "landscape"
    visual_style: Literal["automatic", "editorial", "bold", "notebook", "playful"] = (
        "automatic"
    )
    slide_format: Literal["detailed", "presenter"] = "detailed"


class NoteRequest(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(max_length=200000)
    message_id: UUID | None = None
    artifact_id: UUID | None = None
    artifact_index: int | None = Field(default=None, ge=0, le=19)


class ActionRequest(StrictModel):
    name: str = Field(max_length=80)
    arguments: dict = Field(default_factory=dict)


class Confirmation(StrictModel):
    approved: Literal[True]


class ProfileSelection(StrictModel):
    profile_id: str = Field(min_length=1, max_length=100)


def register_study_routes(
    app, repository, canvas, *, secret_store=None, provider_factory=None
):
    import json

    store = StudyStore(repository)
    secrets = secret_store or KeychainSecrets()
    sources = SourceService(store, canvas)
    interactions = InteractionService(canvas)

    def factory(config):
        if config["kind"] in KINDS:
            return (CodexProvider if config["kind"] == "codex" else ClaudeCodeProvider)(
                config
            )
        # Do not touch Keychain on ordinary page loads or for keyless local servers.
        key = secrets.get(config["id"]) if config.get("key_saved") else None
        if config.get("key_saved") and not key:
            raise ProviderError(
                "provider_auth",
                "The saved key is unavailable. Save it again in Provider settings.",
                401,
            )
        return HTTPProvider(config, key)

    study = StudyService(store, provider_factory or factory, interactions)
    app.state.study_store, app.state.sources, app.state.study = store, sources, study
    app.state.interactions = interactions
    router = APIRouter(prefix="/api")

    @router.get("/canvas/profiles")
    def profiles():
        return canvas.profiles()

    @router.put("/canvas/profile")
    def select_profile(payload: ProfileSelection):
        result = canvas.choose_profile(payload.profile_id)
        interactions.cancel_all()
        return result

    @app.exception_handler(ProviderError)
    @app.exception_handler(ParseError)
    async def study_error(request, exc):
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}},
            status_code=getattr(exc, "status_code", 422),
        )

    def workspace(identifier):
        row = repository.get(str(identifier))
        if row is None:
            raise HTTPException(404, "Workspace not found.")
        return row

    def source(workspace_id, source_id):
        workspace(workspace_id)
        row = store.source(str(workspace_id), str(source_id))
        if row is None:
            raise HTTPException(404, "Source not found in this workspace.")
        return row

    @router.get("/workspaces/{workspace_id}/sources")
    def list_sources(workspace_id: UUID):
        workspace(workspace_id)
        return {"sources": store.sources(str(workspace_id))}

    @router.post("/workspaces/{workspace_id}/sources/inventory")
    def inventory(workspace_id: UUID):
        return sources.inventory(workspace(workspace_id))

    @router.post("/workspaces/{workspace_id}/sources/sync")
    def sync(workspace_id: UUID, payload: SourceSelection):
        row = workspace(workspace_id)
        # Validate the entire selection before doing work, avoiding partial mutation on a bad scope.
        for identifier in payload.source_ids:
            source(workspace_id, identifier)
        return sources.sync(
            row, [str(i) for i in payload.source_ids], force=payload.force
        )

    @router.post("/workspaces/{workspace_id}/sources/sync-course")
    def sync_course(workspace_id: UUID):
        row = workspace(workspace_id)
        inventory_result = sources.inventory(row)
        identifiers = [
            s["id"]
            for s in inventory_result["sources"]
            if s["kind"] not in {"upload", "external"}
        ]
        result = sources.sync(row, identifiers)
        return {**result, "warnings": inventory_result["warnings"]}

    @router.post("/workspaces/{workspace_id}/sources/{source_id}/refresh")
    def refresh_source(workspace_id: UUID, source_id: UUID):
        source(workspace_id, source_id)
        return sources.sync(workspace(workspace_id), [str(source_id)], force=True)[
            "sources"
        ][0]

    @router.post("/workspaces/{workspace_id}/sources/upload", status_code=201)
    async def upload_source(workspace_id: UUID, request: Request):
        workspace(workspace_id)
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            raise HTTPException(422, "Invalid upload length.") from None
        if not length or length > MAX_FILE_BYTES + 1024 * 1024:
            raise HTTPException(413, "Upload one file of at most 25 MB.")
        async with request.form(
            max_files=1, max_fields=0, max_part_size=MAX_FILE_BYTES
        ) as form:
            file = form.get("file")
            # Starlette creates UploadFile instances; FastAPI's subtype is not used by request.form.
            from starlette.datastructures import UploadFile as StarletteUploadFile

            if not isinstance(file, StarletteUploadFile):
                raise HTTPException(422, "Choose one file to upload.")
            data = await file.read(MAX_FILE_BYTES + 1)
            import asyncio

            return await asyncio.to_thread(
                sources.upload, str(workspace_id), file.filename or "Upload", data
            )

    @router.post("/workspaces/{workspace_id}/sources/text", status_code=201)
    def text_source(workspace_id: UUID, payload: TextSource):
        workspace(workspace_id)
        return sources.upload(
            str(workspace_id), payload.title + ".md", payload.content.encode()
        )

    @router.get("/workspaces/{workspace_id}/sources/{source_id}")
    def source_details(workspace_id: UUID, source_id: UUID, offset: int = 0):
        row = source(workspace_id, source_id)
        chunks = store.chunks(str(workspace_id), str(source_id))
        if offset < 0:
            raise HTTPException(422, "Invalid chunk offset.")
        try:
            display_html = sources.preview(workspace(workspace_id), row)
        except CanvasServiceError:
            # Previously indexed sources remain readable when Canvas is offline.
            display_html = None
        return {
            "source": row,
            "chunks": chunks[offset : offset + 30],
            "total_chunks": len(chunks),
            "display_html": display_html,
            "display_text": reading_text(chunks),
        }

    @router.get("/workspaces/{workspace_id}/citations/{chunk_id}")
    def citation_detail(workspace_id: UUID, chunk_id: UUID):
        workspace(workspace_id)
        from contextlib import closing

        from .store import decode

        with closing(repository._connect()) as db:
            row = db.execute(
                "SELECT c.*,s.title AS source_title,s.canvas_url,s.status AS source_status FROM source_chunks c JOIN sources s ON s.id=c.source_id WHERE c.id=? AND c.workspace_id=?",
                (str(chunk_id), str(workspace_id)),
            ).fetchone()
        if row is None:
            raise HTTPException(
                404,
                "This citation is no longer in the current source version. Its saved excerpt is still available in the answer.",
            )
        return decode(row)

    @router.delete("/workspaces/{workspace_id}/sources/{source_id}", status_code=204)
    def delete_source(workspace_id: UUID, source_id: UUID):
        source(workspace_id, source_id)
        store.delete_source(str(workspace_id), str(source_id))
        sources.remove_files(str(source_id))
        return Response(status_code=204)

    def public_provider(config):
        result = dict(config)
        result["has_key"] = bool(result.pop("key_saved", False))
        result["credential_store"] = "system" if result["has_key"] else "not_required"
        if config["kind"] in KINDS:
            result["credential_store"] = "native_cli"
        return result

    @router.get("/providers")
    def providers():
        return {"providers": [public_provider(c) for c in store.providers()]}

    @router.get("/local-clients")
    def local_clients():
        from .local_clients import client_options

        return client_options(canvas.profile_name())

    @router.post("/providers/local/{kind}", status_code=201)
    async def connect_local(kind: Literal["codex", "claude_code"]):
        # Inspect login only on an explicit connect action; no inference or copied tokens.
        status = await inspect_login(kind)
        existing = next((p for p in store.providers() if p["kind"] == kind), None)
        if existing:
            return public_provider(existing)
        return public_provider(
            store.save_provider(
                {
                    "id": str(uuid4()),
                    "name": KINDS[kind],
                    "kind": kind,
                    "model": status["model"],
                    "base_url": "",
                    "key_saved": False,
                    "capabilities": asdict(
                        Capabilities(streaming=True, structured_output=True)
                    ),
                }
            )
        )

    @router.post("/local-clients/{kind}/login")
    async def login_local(kind: Literal["codex", "claude_code"]):
        from .local_clients import open_login

        return await open_login(kind)

    @router.post("/local-clients/{kind}/open")
    async def open_client(kind: Literal["codex", "claude"]):
        from .local_clients import open_desktop

        return await open_desktop(kind)

    @router.post("/local-clients/{kind}/connect")
    async def connect_client(kind: Literal["codex", "claude"]):
        from .local_clients import connect_desktop

        return await connect_desktop(kind, canvas.profile_name())

    @router.post("/providers", status_code=201)
    def save_provider(payload: ProviderConfig):
        if payload.kind in KINDS:
            find_cli(payload.kind)
            if payload.api_key or payload.remove_key or payload.native_tools:
                raise HTTPException(
                    422,
                    "CLI providers use their own login and do not support live tools here.",
                )
        if payload.api_key and payload.remove_key:
            raise HTTPException(422, "Choose either save key or remove key.")
        identifier = str(payload.id or uuid4())
        existing = store.provider(identifier)
        if payload.id and existing is None:
            raise HTTPException(404, "Provider not found.")
        if existing and payload.kind != existing["kind"]:
            raise HTTPException(
                422, "Create a separate configuration to change provider type."
            )
        base_url = validate_base_url(payload.kind, payload.base_url)
        if existing and base_url != existing["base_url"] and not payload.remove_key:
            raise HTTPException(
                422,
                "Remove the old key when changing endpoints, then save a new key if needed.",
            )
        if payload.api_key:
            secrets.set(identifier, payload.api_key)
        if payload.remove_key and existing and existing.get("key_saved"):
            secrets.delete(identifier)
        config = {
            "id": identifier,
            "name": payload.name,
            "kind": payload.kind,
            "model": payload.model,
            "base_url": base_url,
            "key_saved": bool(payload.api_key)
            or bool(existing and existing.get("key_saved") and not payload.remove_key),
            "capabilities": asdict(
                Capabilities(
                    streaming=True if payload.kind in KINDS else payload.streaming,
                    native_tools=False
                    if payload.kind in KINDS
                    else payload.native_tools,
                    structured_output=True
                    if payload.kind in KINDS
                    else payload.structured_output,
                )
            ),
        }
        return public_provider(store.save_provider(config))

    @router.delete("/providers/{provider_id}", status_code=204)
    def delete_provider(provider_id: UUID):
        if store.provider(str(provider_id)) is None:
            raise HTTPException(404, "Provider not found.")
        if store.provider(str(provider_id)).get("key_saved"):
            secrets.delete(str(provider_id))
        store.delete_provider(str(provider_id))
        return Response(status_code=204)

    @router.post("/providers/{provider_id}/test")
    async def test_provider(provider_id: UUID):
        config = store.provider(str(provider_id))
        if config is None:
            raise HTTPException(404, "Provider not found.")
        provider = (provider_factory or factory)(config)
        text = ""
        async for event in provider.stream_chat(
            [
                {
                    "role": "user",
                    "content": "Reply only with OK. This is a connection test; no course data is included.",
                }
            ]
        ):
            if event["type"] == "text_delta":
                text += event["text"]
        return {
            "status": "connected",
            "model": config["model"],
            "received_text": bool(text),
        }

    @router.get("/workspaces/{workspace_id}/conversations")
    def conversations(workspace_id: UUID):
        workspace(workspace_id)
        return {"conversations": store.conversations(str(workspace_id))}

    @router.get("/workspaces/{workspace_id}/conversations/{conversation_id}")
    def conversation(
        workspace_id: UUID, conversation_id: UUID, temporary: bool = False
    ):
        workspace(workspace_id)
        result = (study.temporary if temporary else store).conversation(
            str(workspace_id), str(conversation_id)
        )
        if result is None:
            raise HTTPException(404, "Conversation not found.")
        return result

    @router.post(
        "/workspaces/{workspace_id}/temporary-conversations/{conversation_id}/save"
    )
    def save_temporary(workspace_id: UUID, conversation_id: UUID):
        workspace(workspace_id)
        return study.save_temporary(str(workspace_id), str(conversation_id))

    @router.delete(
        "/workspaces/{workspace_id}/conversations/{conversation_id}", status_code=204
    )
    def delete_conversation(
        workspace_id: UUID, conversation_id: UUID, temporary: bool = False
    ):
        workspace(workspace_id)
        with study._lock:
            if str(conversation_id) in study._running:
                raise HTTPException(409, "Stop the response first.")
            removed = (study.temporary if temporary else store).delete_conversation(
                str(workspace_id), str(conversation_id)
            )
        if not removed:
            raise HTTPException(404, "Conversation not found.")
        return Response(status_code=204)

    @router.post("/workspaces/{workspace_id}/chat")
    def chat(workspace_id: UUID, payload: ChatRequest):
        if not payload.message.strip():
            raise HTTPException(422, "Enter a message.")
        prepared = study.prepare_chat(
            workspace(workspace_id),
            str(payload.provider_id),
            [str(i) for i in payload.source_ids],
            payload.message.strip(),
            str(payload.conversation_id) if payload.conversation_id else None,
            payload.live_tools,
            temporary=payload.temporary,
        )

        async def events():
            async for event in study.chat(prepared):
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @router.post("/workspaces/{workspace_id}/artifacts/generate", status_code=201)
    async def generate(workspace_id: UUID, payload: GenerateRequest):
        return await study.generate(
            workspace(workspace_id),
            str(payload.provider_id),
            [str(i) for i in payload.source_ids],
            payload.kind,
            payload.topic,
            payload.count,
            payload.difficulty,
            prompt=payload.prompt,
            template=payload.template,
            language=payload.language,
            orientation=payload.orientation,
            visual_style=payload.visual_style,
            slide_format=payload.slide_format,
        )

    @router.get("/workspaces/{workspace_id}/artifacts")
    def artifacts(workspace_id: UUID):
        workspace(workspace_id)
        return {"artifacts": store.artifacts(str(workspace_id))}

    def artifact(workspace_id, artifact_id):
        workspace(workspace_id)
        result = next(
            (
                a
                for a in store.artifacts(str(workspace_id))
                if a["id"] == str(artifact_id)
            ),
            None,
        )
        if result is None:
            raise HTTPException(404, "Artifact not found.")
        return result

    @router.get("/workspaces/{workspace_id}/artifacts/{artifact_id}")
    def get_artifact(workspace_id: UUID, artifact_id: UUID):
        return artifact(workspace_id, artifact_id)

    @router.get("/workspaces/{workspace_id}/artifacts/{artifact_id}/export")
    def export_artifact(
        workspace_id: UUID,
        artifact_id: UUID,
        format: Literal["json", "markdown", "docx", "xlsx", "pptx", "svg"] = "json",
        template: Literal[
            "automatic", "study_notes", "revision_outline", "analysis_report"
        ] = "automatic",
    ):
        row = artifact(workspace_id, artifact_id)
        filename = (
            f"study-{artifact_id}."
            + {
                "json": "json",
                "markdown": "md",
                "docx": "docx",
                "xlsx": "xlsx",
                "pptx": "pptx",
                "svg": "svg",
            }[format]
        )
        if format in {"pptx", "svg"}:
            from .visual_exports import visual_export

            return Response(
                visual_export(row, format),
                media_type="image/svg+xml"
                if format == "svg"
                else "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        if format in {"docx", "xlsx"}:
            from .office_exports import excel_export, word_export

            return Response(
                word_export(row, template) if format == "docx" else excel_export(row),
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if format == "docx"
                else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        content = (
            json.dumps(row, ensure_ascii=False, indent=2)
            if format == "json"
            else artifact_markdown(row)
        )
        return Response(
            content,
            media_type="application/json" if format == "json" else "text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.delete(
        "/workspaces/{workspace_id}/artifacts/{artifact_id}", status_code=204
    )
    def delete_artifact(workspace_id: UUID, artifact_id: UUID):
        artifact(workspace_id, artifact_id)
        store.delete_artifact(str(workspace_id), str(artifact_id))
        return Response(status_code=204)

    @router.get("/workspaces/{workspace_id}/notes")
    def notes(workspace_id: UUID):
        workspace(workspace_id)
        return {"notes": store.notes(str(workspace_id))}

    def save_note(workspace_id, payload, identifier=None):
        workspace(workspace_id)
        if not payload.title.strip():
            raise HTTPException(422, "Enter a note title.")
        provenance, content = {}, payload.content
        if payload.message_id and payload.artifact_id:
            raise HTTPException(422, "Choose one note origin.")
        if payload.artifact_index is not None and not payload.artifact_id:
            raise HTTPException(422, "An artifact excerpt requires its saved artifact.")
        if payload.artifact_id:
            row = artifact(workspace_id, payload.artifact_id)
            if payload.artifact_index is not None:
                key = {
                    "quiz": "questions",
                    "flashcards": "cards",
                    "study_guide": "sections",
                    "document": "sections",
                    "spreadsheet": "rows",
                    "mindmap": "nodes",
                    "slides": "slides",
                    "infographic": "sections",
                }[row["kind"]]
                if payload.artifact_index >= len(row["content"][key]):
                    raise HTTPException(
                        422, "This excerpt is outside the saved artifact."
                    )
                item = row["content"][key][payload.artifact_index]
                excerpt_citations = [
                    c
                    for c in row["provenance"]["citations"]
                    if c["chunk_id"] in item["citations"]
                ]
                row = {
                    **row,
                    "content": {
                        **row["content"],
                        "title": row["title"] + " — excerpt",
                        key: [item],
                    },
                    "provenance": {
                        **row["provenance"],
                        "artifact_index": payload.artifact_index,
                        "citations": excerpt_citations,
                        "source_ids": list(
                            dict.fromkeys(c["source_id"] for c in excerpt_citations)
                        ),
                    },
                }
            content, provenance = (
                artifact_markdown(row),
                {"artifact_id": row["id"], **row["provenance"]},
            )
        if payload.message_id:
            from contextlib import closing

            from .store import decode

            with closing(repository._connect()) as db:
                row = decode(
                    db.execute(
                        "SELECT m.* FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.id=? AND c.workspace_id=? AND m.role='assistant'",
                        (str(payload.message_id), str(workspace_id)),
                    ).fetchone()
                )
            if row is None:
                raise HTTPException(
                    404, "Assistant message not found in this workspace."
                )
            content, provenance = (
                row["content"],
                {
                    "message_id": row["id"],
                    "citations": row["citations"],
                    "provider_id": row["provider_id"],
                    "model": row["model"],
                },
            )
        if identifier and not any(
            n["id"] == str(identifier) for n in store.notes(str(workspace_id))
        ):
            raise HTTPException(404, "Note not found.")
        return store.save_note(
            str(workspace_id),
            payload.title.strip(),
            content,
            provenance,
            str(identifier) if identifier else None,
        )

    @router.post("/workspaces/{workspace_id}/notes", status_code=201)
    def create_note(workspace_id: UUID, payload: NoteRequest):
        return save_note(workspace_id, payload)

    @router.put("/workspaces/{workspace_id}/notes/{note_id}")
    def update_note(workspace_id: UUID, note_id: UUID, payload: NoteRequest):
        return save_note(workspace_id, payload, note_id)

    @router.delete("/workspaces/{workspace_id}/notes/{note_id}", status_code=204)
    def delete_note(workspace_id: UUID, note_id: UUID):
        workspace(workspace_id)
        if not store.delete_note(str(workspace_id), str(note_id)):
            raise HTTPException(404, "Note not found.")
        return Response(status_code=204)

    @router.get("/workspaces/{workspace_id}/actions")
    def actions(workspace_id: UUID):
        return {
            "tools": interactions.tools(workspace(workspace_id)),
            "previews": interactions.previews(str(workspace_id)),
        }

    @router.post("/workspaces/{workspace_id}/actions/preview")
    def action_preview(workspace_id: UUID, payload: ActionRequest):
        return interactions.invoke(
            workspace(workspace_id), payload.name, payload.arguments
        )

    @router.post("/workspaces/{workspace_id}/actions/{preview_id}/confirm")
    def confirm_action(workspace_id: UUID, preview_id: UUID, payload: Confirmation):
        workspace(workspace_id)
        return interactions.confirm(str(workspace_id), str(preview_id))

    @router.delete("/workspaces/{workspace_id}/actions/{preview_id}", status_code=204)
    def cancel_action(workspace_id: UUID, preview_id: UUID):
        workspace(workspace_id)
        if not interactions.cancel(str(workspace_id), str(preview_id)):
            raise HTTPException(404, "Pending action not found.")
        return Response(status_code=204)

    app.include_router(router)
