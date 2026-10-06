from __future__ import annotations

from tools import activity, interactions
from specs.schema import tool_spec

ID = {"type": "string", "pattern": r"^[0-9]+(?:~[0-9]+)?$", "description": "Canvas numeric ID (resolve a course code first)."}
LIMIT = {"type": "integer", "minimum": 1, "maximum": 300}
TEXT = {"type": "string", "minLength": 1, "maxLength": 100000}
CONFIRM = {"type": "string", "minLength": 1, "maxLength": 128, "description": "Omit to preview. After explicit user approval, repeat identical arguments with the preview's single-use token."}
SCAN = {"course_id": ID, "courses_limit": LIMIT, "assignments_limit": LIMIT, "limit": LIMIT}


def read_spec(name, description, properties, required=None):
    return tool_spec(name=name, description=description, handler=getattr(activity, name),
                     properties=properties, required=required,
                     annotations={"readOnlyHint": True, "openWorldHint": True})


def write_spec(name, description, properties, required, *, idempotent=False):
    return tool_spec(name=name,
        description=description + " Preview first, show the exact target/content, obtain explicit user approval, then repeat with confirmation_token. No mutation without a valid, single-use confirmation bound to this account and Chrome profile.",
        handler=getattr(interactions, name), properties={**properties, "confirmation_token": CONFIRM},
        required=required, annotations={"readOnlyHint": False, "destructiveHint": False,
                                       "idempotentHint": idempotent, "openWorldHint": True})


ACTIVITY_TOOL_SPECS = [
    read_spec("get_my_submission_status", "Current student's assignment status and missing/overdue tracking, across active student courses or one course. Results disclose scan limits and failed courses; external-tool work is not inferred missing.",
        {**SCAN, "missing_only": {"type": "boolean"}, "status": {"type": "string", "enum": ["missing", "overdue", "unsubmitted", "submitted", "graded", "excused", "not_required", "external_tool", "unpublished", "unknown"]}}),
    read_spec("get_my_peer_reviews_todo", "Pending peer reviews assigned to the current user, merging assignment and Planner discovery. Failed or bounded scans are explicitly partial. assignment_id requires course_id.",
        {**SCAN, "assignment_id": ID, "reviews_limit": LIMIT, "planner_limit": LIMIT}),
    read_spec("list_conversations", "List the current user's Canvas Inbox conversations without marking them read.",
        {"scope": {"type": "string", "enum": ["unread", "starred", "archived", "sent"]},
         "filter": {"type": "array", "items": {"type": "string"}, "maxItems": 100},
         "filter_mode": {"type": "string", "enum": ["and", "or"]}, "limit": LIMIT}),
    read_spec("get_conversation_details", "Read a Canvas conversation with auto_mark_as_read=false; message output can be bounded.",
        {"conversation_id": ID, "limit": LIMIT}, ["conversation_id"]),
    read_spec("get_course_structure", "Course module-to-item tree with prerequisites, progression, completion requirements, links and content details. Fetches canonical item endpoints and reports partial results. Includes only resources accessible in modules.",
        {"course_id": ID, "include_unpublished": {"type": "boolean"}, "modules_limit": LIMIT, "items_limit": LIMIT}, ["course_id"]),
    read_spec("list_module_items", "List a module's items with completion requirements and content details, without changing completion state.",
        {"course_id": ID, "module_id": ID, "limit": LIMIT}, ["course_id", "module_id"]),
    write_spec("post_discussion_entry", "Post an entry to an existing course discussion.",
        {"course_id": ID, "topic_id": ID, "message": TEXT}, ["course_id", "topic_id", "message"]),
    write_spec("reply_to_discussion_entry", "Reply to an existing discussion entry.",
        {"course_id": ID, "topic_id": ID, "entry_id": ID, "message": TEXT}, ["course_id", "topic_id", "entry_id", "message"]),
    write_spec("add_submission_comment", "Add a text comment to YOUR OWN assignment submission. Does not submit, grade, or change another student's work.",
        {"course_id": ID, "assignment_id": ID, "comment": TEXT, "attempt": {"type": "integer", "minimum": 1}}, ["course_id", "assignment_id", "comment"]),
    write_spec("send_conversation", "Send a Canvas Inbox message to explicit Canvas user IDs. Group delivery defaults to false (individual conversations).",
        {"recipients": {"type": "array", "items": ID, "minItems": 1, "maxItems": 100, "uniqueItems": True},
         "subject": {**TEXT, "maxLength": 255}, "body": TEXT, "course_id": ID, "group_conversation": {"type": "boolean"}}, ["recipients", "subject", "body"]),
    write_spec("reply_to_conversation", "Reply to the participants of a Canvas Inbox conversation; participants are shown in the preview.",
        {"conversation_id": ID, "body": TEXT}, ["conversation_id", "body"]),
    write_spec("update_conversation", "Mark an Inbox conversation read/unread or archive it, after preview and approval.",
        {"conversation_id": ID, "workflow_state": {"type": "string", "enum": ["read", "unread", "archived"]}}, ["conversation_id", "workflow_state"], idempotent=True),
    write_spec("mark_module_item_done", "Mark a module item done for yourself, or undo it with done=false. Requires must_mark_done and verifies the resulting completion state.",
        {"course_id": ID, "module_id": ID, "item_id": ID, "done": {"type": "boolean"}}, ["course_id", "module_id", "item_id"], idempotent=True),
]
