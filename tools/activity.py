from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import re
from typing import Any

from auth import CanvasAPIError
from tools.common import canvas_client, expand_canvas_id


def resource_id(value: Any, *, course_id: str | None = None) -> str:
    text = str(value).strip()
    if not re.fullmatch(r"[0-9]+(?:~[0-9]+)?", text):
        raise ValueError("Canvas resource IDs must be numeric or shard~id.")
    return expand_canvas_id(text, course_id=course_id)


def selected_courses(client, args, warnings):
    if args.get("course_id"):
        return [{"id": resource_id(args["course_id"])}]
    result = client.activity_list(
        "courses", params={"enrollment_state": "active", "enrollment_type": "student"},
        limit=args.get("courses_limit", 30),
    )
    if result["truncated"]:
        warnings.append({"scope": "courses", "reason": "courses_limit reached"})
    return result["items"]


def _limited(client, endpoint, *, limit, warnings, params=None):
    result = client.activity_list(endpoint, params=params, limit=limit)
    if result["truncated"]:
        warnings.append({"scope": endpoint, "reason": "scan limit reached"})
    return result["items"]


def _failure(warnings, scope, exc):
    warnings.append({"scope": scope, "reason": str(exc), "status_code": exc.status_code})


def submission_state(assignment: dict, now: datetime) -> str:
    submission = assignment.get("submission") or {}
    if submission.get("excused"):
        return "excused"
    types = assignment.get("submission_types") or []
    state = submission.get("workflow_state")
    if "external_tool" in types and not submission.get("submitted_at") and state not in {"submitted", "graded", "pending_review"}:
        return "external_tool"
    if submission.get("missing"):
        return "missing"
    if state == "graded":
        return "graded"
    if submission.get("submitted_at") or state in {"submitted", "pending_review"}:
        return "submitted"
    if types and set(types) <= {"none", "not_graded", "on_paper"}:
        return "not_required"
    if assignment.get("published") is False:
        return "unpublished"
    if not submission:
        return "unknown"
    # cached_due_date is the current student's effective deadline, including
    # overrides. A null value means no deadline, rather than the base deadline.
    due = submission.get("cached_due_date") if "cached_due_date" in submission else assignment.get("due_at")
    if due:
        try:
            parsed = datetime.fromisoformat(str(due).replace("Z", "+00:00"))
            if parsed.tzinfo is not None and parsed < now:
                return "overdue"
        except (ValueError, TypeError):
            pass
    return "unsubmitted"


def get_my_submission_status(args: dict[str, Any]) -> dict[str, Any]:
    client = canvas_client()
    warnings: list[dict] = []
    courses = selected_courses(client, args, warnings)
    rows = []
    now = datetime.now(timezone.utc)
    for course in courses:
        cid = str(course["id"])
        endpoint = f"courses/{cid}/assignments"
        try:
            assignments = _limited(client, endpoint, limit=args.get("assignments_limit", 100),
                                   params={"include": ["submission"]}, warnings=warnings)
        except CanvasAPIError as exc:
            _failure(warnings, endpoint, exc)
            continue
        for assignment in assignments:
            submission = assignment.get("submission") or {}
            rows.append({
                "course_id": cid, "course_code": course.get("course_code"),
                "assignment_id": str(assignment["id"]), "name": assignment.get("name"),
                "status": submission_state(assignment, now),
                "due_at": submission.get("cached_due_date") if "cached_due_date" in submission else assignment.get("due_at"),
                "submitted_at": submission.get("submitted_at"),
                "late": submission.get("late"), "missing": submission.get("missing"),
                "excused": submission.get("excused"), "workflow_state": submission.get("workflow_state"),
                "score": submission.get("score"), "grade": submission.get("grade"),
                "attempt": submission.get("attempt"), "html_url": assignment.get("html_url"),
            })
    counts = dict(Counter(row["status"] for row in rows))
    scanned = len(rows)
    if args.get("missing_only"):
        rows = [row for row in rows if row["status"] == "missing"]
    if args.get("status"):
        rows = [row for row in rows if row["status"] == args["status"]]
    limit = args.get("limit", 100)
    return {"assignments": rows[:limit], "count": len(rows[:limit]),
            "matched_count": len(rows), "scanned_count": scanned, "status_counts": counts,
            "courses_checked": len(courses), "partial": bool(warnings),
            "truncated": len(rows) > limit, "warnings": warnings,
            "checked_at": now.isoformat(),
            "note": "missing uses Canvas's flag; overdue is inferred from the effective due date. External-tool work may need checking in the external service."}


def get_my_peer_reviews_todo(args: dict[str, Any]) -> dict[str, Any]:
    if args.get("assignment_id") and not args.get("course_id"):
        return {"error": "invalid_argument", "message": "assignment_id requires course_id"}
    client = canvas_client()
    me = resource_id(client.activity_get("users/self")["id"])
    warnings: list[dict] = []
    courses = selected_courses(client, args, warnings)
    course_ids = {str(course["id"]) for course in courses}
    reviews: dict[tuple[str, str], dict] = {}
    for course in courses:
        cid = str(course["id"])
        assignments_endpoint = f"courses/{cid}/assignments"
        try:
            if args.get("assignment_id"):
                aid = resource_id(args["assignment_id"], course_id=cid)
                assignments = [client.activity_get(f"{assignments_endpoint}/{aid}")]
            else:
                assignments = _limited(client, assignments_endpoint,
                                       limit=args.get("assignments_limit", 100), warnings=warnings)
        except CanvasAPIError as exc:
            _failure(warnings, assignments_endpoint, exc)
            continue
        for assignment in assignments:
            if not args.get("assignment_id") and not assignment.get("peer_reviews"):
                continue
            aid = str(assignment["id"])
            endpoint = f"{assignments_endpoint}/{aid}/peer_reviews"
            try:
                found = _limited(client, endpoint, limit=args.get("reviews_limit", 100), warnings=warnings)
            except CanvasAPIError as exc:
                _failure(warnings, endpoint, exc)
                continue
            for review in found:
                if str(review.get("assessor_id")) != me or review.get("workflow_state") == "completed":
                    continue
                rid = str(review["id"])
                # Do not expose reviewee names: an assignment can require anonymous reviews.
                reviews[(cid, rid)] = {"id": rid, "course_id": cid, "assignment_id": aid,
                    "assignment_name": assignment.get("name"), "workflow_state": review.get("workflow_state"),
                    "submission_id": str(review["asset_id"]) if review.get("asset_id") is not None else None,
                    "sources": ["assignment"]}

    planner_params = {"filter": "incomplete_items"}
    if args.get("course_id"):
        planner_params["context_codes"] = [f"course_{next(iter(course_ids))}"]
    try:
        items = _limited(client, "planner/items", params=planner_params,
                         limit=args.get("planner_limit", 300), warnings=warnings)
        for item in items:
            if item.get("plannable_type") != "assessment_request":
                continue
            plan = item.get("plannable") or {}
            cid = str(item.get("course_id"))
            if cid not in course_ids or plan.get("workflow_state") == "completed":
                continue
            if plan.get("assessor_id") is not None and str(plan["assessor_id"]) != me:
                continue
            match = re.search(r"/courses/[0-9]+/assignments/([0-9]+)(?:/|$)", str(item.get("html_url", "")))
            aid = match.group(1) if match else None
            # Direct assignment queries must never absorb another assignment's reviews.
            if args.get("assignment_id") and aid != resource_id(args["assignment_id"], course_id=cid):
                continue
            rid = plan.get("id") or item.get("plannable_id")
            if rid is None:
                warnings.append({"scope": "planner/items", "reason": "assessment_request has no ID"})
                continue
            key = (cid, str(rid))
            if key in reviews:
                reviews[key]["sources"].append("planner")
                reviews[key]["html_url"] = item.get("html_url")
            else:
                reviews[key] = {"id": str(rid), "course_id": cid, "assignment_id": aid,
                    "assignment_name": plan.get("title"), "workflow_state": plan.get("workflow_state"),
                    "due_at": plan.get("todo_date") or item.get("plannable_date"),
                    "html_url": item.get("html_url"), "sources": ["planner"]}
    except CanvasAPIError as exc:
        _failure(warnings, "planner/items", exc)
    rows = list(reviews.values())
    limit = args.get("limit", 100)
    return {"peer_reviews": rows[:limit], "count": len(rows[:limit]),
            "matched_count": len(rows), "partial": bool(warnings),
            "truncated": len(rows) > limit, "warnings": warnings,
            "courses_checked": len(courses)}


def list_conversations(args: dict[str, Any]) -> dict[str, Any]:
    params = {}
    for key in ("scope", "filter", "filter_mode"):
        if key in args:
            params[key] = args[key]
    result = canvas_client().activity_list("conversations", params=params, limit=args.get("limit", 50))
    return {"conversations": result["items"], "count": len(result["items"]), "truncated": result["truncated"]}


def get_conversation_details(args: dict[str, Any]) -> dict[str, Any]:
    cid = resource_id(args["conversation_id"])
    data = canvas_client().activity_get(f"conversations/{cid}", params={"auto_mark_as_read": False})
    # Canvas returns its complete message list on this endpoint. Bound output,
    # while retaining the conversation and attachment metadata.
    messages = data.get("messages") or []
    limit = args.get("limit", 100)
    return {"conversation": {**data, "messages": messages[:limit]},
            "truncated": len(messages) > limit, "auto_mark_as_read": False}


def list_module_items(args: dict[str, Any]) -> dict[str, Any]:
    cid = resource_id(args["course_id"])
    mid = resource_id(args["module_id"], course_id=cid)
    result = canvas_client().activity_list(f"courses/{cid}/modules/{mid}/items",
        params={"include": ["content_details"]}, limit=args.get("limit", 100))
    return {"course_id": cid, "module_id": mid, "items": result["items"],
            "count": len(result["items"]), "truncated": result["truncated"]}


def get_course_structure(args: dict[str, Any]) -> dict[str, Any]:
    client = canvas_client()
    cid = resource_id(args["course_id"])
    raw_course = client.activity_get(f"courses/{cid}")
    course = {key: raw_course.get(key) for key in ("id", "name", "course_code", "workflow_state", "default_view", "html_url")}
    warnings: list[dict] = []
    modules = _limited(client, f"courses/{cid}/modules", limit=args.get("modules_limit", 100), warnings=warnings)
    tree = []
    counts = Counter()
    for module in modules:
        if args.get("include_unpublished", True) is False and module.get("published") is False:
            continue
        mid = str(module["id"])
        endpoint = f"courses/{cid}/modules/{mid}/items"
        node = {key: module.get(key) for key in ("id", "name", "position", "unlock_at", "published", "state", "prerequisite_module_ids", "require_sequential_progress", "items_count", "completed_at")}
        node["items"] = []
        node["items_truncated"] = False
        try:
            result = client.activity_list(endpoint, params={"include": ["content_details"]}, limit=args.get("items_limit", 100))
            node["items_truncated"] = result["truncated"]
            if result["truncated"]:
                warnings.append({"scope": endpoint, "reason": "items_limit reached"})
            # Always fetch the canonical items endpoint: inline module.items
            # can be partial even when the module list itself is complete.
            node["items"] = [item for item in result["items"] if
                             args.get("include_unpublished", True) or item.get("published") is not False]
            counts.update(item.get("type", "Unknown") for item in node["items"])
        except CanvasAPIError as exc:
            _failure(warnings, endpoint, exc)
            node["items_error"] = str(exc)
        tree.append(node)
    return {"course": course, "modules": tree, "module_count": len(tree),
            "item_count": sum(counts.values()), "item_type_counts": dict(counts),
            "partial": bool(warnings), "warnings": warnings,
            "note": "Contains accessible module items only; unmoduled resources and content hidden by Canvas permissions are not included."}
