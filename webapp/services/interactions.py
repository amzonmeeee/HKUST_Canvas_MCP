"""Expose a small v2 tool subset. Model writes can only create human previews."""

from __future__ import annotations

import copy
import json
import time
from threading import Lock
from uuid import uuid4

from jsonschema import ValidationError, validate

from specs.registry import TOOL_SPECS

from .canvas import CanvasServiceError

READ_TOOLS = {
    "get_my_submission_status",
    "get_my_peer_reviews_todo",
    "list_conversations",
    "get_conversation_details",
    "get_course_structure",
    "list_module_items",
    "get_assignment_details",
    "list_course_assignments",
    "get_course_overview",
    "get_course_syllabus",
    "list_course_announcements",
    "get_discussion_topic_details",
    "list_course_discussion_topics",
    "list_todo_items",
}
WRITE_TOOLS = {
    "post_discussion_entry",
    "reply_to_discussion_entry",
    "add_submission_comment",
    "send_conversation",
    "reply_to_conversation",
    "mark_module_item_done",
}


def scrub(value):
    if isinstance(value, dict):
        return {
            k: scrub(v)
            for k, v in value.items()
            if k
            not in {
                "confirmation_token",
                "profile_path",
                "cookie",
                "cookies",
                "csrf_token",
                "access_token",
                "api_key",
                "download_path",
                "local_path",
                "path",
            }
        }
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


class InteractionService:
    def __init__(self, canvas):
        self.canvas = canvas
        self._pending = {}
        self._lock = Lock()
        self._specs = {
            s.name: s for s in TOOL_SPECS if s.name in READ_TOOLS | WRITE_TOOLS
        }

    def tools(self, workspace):
        output = []
        for spec in self._specs.values():
            if not workspace.get(
                "canvas_course_id"
            ) and "course_id" in spec.parameters.get("required", []):
                continue
            parameters = copy.deepcopy(spec.parameters)
            parameters["properties"].pop("confirmation_token", None)
            description = spec.description
            if spec.name in WRITE_TOOLS:
                description = (
                    "Propose a Canvas action for human approval; this tool NEVER writes. "
                    + description.split(" Preview first")[0]
                )
            output.append(
                {
                    "name": spec.name,
                    "description": description,
                    "parameters": parameters,
                }
            )
        return output

    def invoke(self, workspace, name, args):
        if (
            name not in self._specs
            or not isinstance(args, dict)
            or "confirmation_token" in args
        ):
            raise CanvasServiceError(
                "tool_not_allowed",
                "This action is not available to the web assistant.",
                422,
            )
        spec = self._specs[name]
        schema = copy.deepcopy(spec.parameters)
        schema["properties"].pop("confirmation_token", None)
        try:
            validate(args, schema)
        except ValidationError as exc:
            raise CanvasServiceError(
                "invalid_tool_arguments", "Check the action fields and try again.", 422
            ) from exc
        if len(json.dumps(args)) > 25000:
            raise CanvasServiceError(
                "invalid_tool_arguments", "The action payload is too large.", 422
            )
        # A course workspace cannot use model tools to silently read/write another course.
        course_id = workspace.get("canvas_course_id")
        if (
            course_id
            and "course_id" in schema["properties"]
            and "course_id" not in args
        ):
            args = {**args, "course_id": course_id}
        if "course_id" in args and str(args["course_id"]) != str(course_id):
            raise CanvasServiceError(
                "tool_scope",
                "The action must target this workspace's Canvas course.",
                422,
            )
        if (
            name == "send_conversation"
            and args.get("context_code")
            and args["context_code"] != f"course_{course_id}"
        ):
            raise CanvasServiceError(
                "tool_scope", "Conversation context must match this workspace.", 422
            )
        result = self.canvas._invoke(name, args)
        if name not in WRITE_TOOLS:
            cleaned = scrub(result)
            text = json.dumps(cleaned)
            if len(text) > 60000:
                return {
                    "truncated": True,
                    "message": "The live Canvas response was too large. Request a smaller limit or a single item.",
                }
            return cleaned
        if result.get("status") != "preview" or result.get("written") is not False:
            return scrub(result)
        identifier = str(uuid4())
        preview = {
            "id": identifier,
            "workspace_id": workspace["id"],
            "tool": name,
            "account": scrub(result.get("account", {})),
            "target": scrub(result.get("target", {})),
            "payload": scrub(result.get("payload", {})),
            "expires_at": result.get("expires_at"),
            "status": "pending",
            "written": False,
        }
        with self._lock:
            self._prune()
            if len(self._pending) >= 100:
                raise CanvasServiceError(
                    "too_many_previews",
                    "Cancel pending actions before preparing more.",
                    429,
                )
            self._pending[identifier] = {
                "preview": preview,
                "args": copy.deepcopy(args),
                "token": result["confirmation_token"],
                "deadline": time.monotonic() + 600,
            }
        return {"requires_human_approval": True, "preview": preview}

    def _prune(self):
        expired = [
            k for k, v in self._pending.items() if v["deadline"] < time.monotonic()
        ]
        for key in expired:
            self._pending.pop(key, None)

    def previews(self, workspace_id):
        with self._lock:
            self._prune()
            return [
                copy.deepcopy(p["preview"])
                for p in self._pending.values()
                if p["preview"]["workspace_id"] == workspace_id
            ]

    def confirm(self, workspace_id, identifier):
        # Remove before dispatch: disconnects and ambiguous Canvas errors never trigger automatic retries.
        with self._lock:
            self._prune()
            pending = self._pending.get(identifier)
            if not pending or pending["preview"]["workspace_id"] != workspace_id:
                raise CanvasServiceError(
                    "preview_expired",
                    "This action is expired, cancelled or already confirmed. Create a new preview.",
                    409,
                )
            self._pending.pop(identifier)
        return scrub(
            self.canvas._invoke(
                pending["preview"]["tool"],
                {**pending["args"], "confirmation_token": pending["token"]},
            )
        )

    def cancel(self, workspace_id, identifier):
        with self._lock:
            pending = self._pending.get(identifier)
            if pending and pending["preview"]["workspace_id"] == workspace_id:
                self._pending.pop(identifier)
                return True
            return False

    def cancel_all(self):
        with self._lock:
            self._pending.clear()
