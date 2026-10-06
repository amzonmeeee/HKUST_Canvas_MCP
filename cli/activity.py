from __future__ import annotations

from typing import Annotated, Callable

import typer

from cli.assignments import submissions_app
from cli.courses import course_app
from cli.discussions import discussion_app

inbox_app = typer.Typer(help="Canvas Inbox: read, send, reply and manage conversations.")
peer_reviews_app = typer.Typer(help="Peer reviews assigned to you.")

# Shared option declarations keep the first-class commands aligned with MCP.
Course = Annotated[str | None, typer.Option("--course", help="Resolved Canvas course ID; omit for active student courses.")]
Limit = Annotated[int, typer.Option(min=1, max=300, help="Maximum output records.")]
CoursesLimit = Annotated[int, typer.Option(min=1, max=300, help="Maximum active student courses to scan.")]
AssignmentsLimit = Annotated[int, typer.Option(min=1, max=300, help="Maximum assignments scanned per course.")]
Confirm = Annotated[str | None, typer.Option("--confirm", help="Single-use token from a preview; pass only after approving the displayed target and content.")]


def register(app: typer.Typer, invoke: Callable[[str, dict], None]):
    app.add_typer(inbox_app, name="inbox")
    app.add_typer(peer_reviews_app, name="peer-reviews")

    @app.command("submissions")
    def submission_status(
        course_id: Course = None,
        missing_only: Annotated[bool, typer.Option("--missing", help="Only Canvas-marked missing work.")] = False,
        status: Annotated[str | None, typer.Option(help="Filter status, e.g. overdue, unsubmitted, external_tool.")] = None,
        limit: Limit = 100, courses_limit: CoursesLimit = 30,
        assignments_limit: AssignmentsLimit = 100,
    ):
        """Your assignment submission status, including missing and overdue work."""
        invoke("get_my_submission_status", {"course_id": course_id, "missing_only": missing_only,
            "status": status, "limit": limit, "courses_limit": courses_limit, "assignments_limit": assignments_limit})

    @peer_reviews_app.command("todo")
    def peer_todo(
        course_id: Course = None,
        assignment_id: Annotated[str | None, typer.Option("--assignment", help="Check a known assignment directly; requires --course.")] = None,
        limit: Limit = 100, courses_limit: CoursesLimit = 30,
        assignments_limit: AssignmentsLimit = 100,
        reviews_limit: Annotated[int, typer.Option(min=1, max=300, help="Reviews scanned per assignment.")] = 100,
        planner_limit: Annotated[int, typer.Option(min=1, max=300, help="Planner records scanned (includes other item types).")] = 300,
    ):
        invoke("get_my_peer_reviews_todo", {"course_id": course_id, "assignment_id": assignment_id,
            "limit": limit, "courses_limit": courses_limit, "assignments_limit": assignments_limit,
            "reviews_limit": reviews_limit, "planner_limit": planner_limit})

    @inbox_app.command("list")
    def inbox_list(
        scope: Annotated[str | None, typer.Option(help="unread, starred, archived or sent; omit for the Inbox.")] = None,
        filters: Annotated[list[str] | None, typer.Option("--filter", help="Canvas filter, e.g. course_12345; repeat for multiple filters.")] = None,
        filter_mode: Annotated[str, typer.Option(help="Combine filters using and/or.")] = "and",
        limit: Limit = 50,
    ):
        invoke("list_conversations", {"scope": scope, "filter": filters, "filter_mode": filter_mode, "limit": limit})

    @inbox_app.command("show")
    def inbox_show(conversation_id: str, limit: Limit = 100):
        """Read conversation messages without marking the conversation read."""
        invoke("get_conversation_details", {"conversation_id": conversation_id, "limit": limit})

    @inbox_app.command("send")
    def inbox_send(
        recipients: Annotated[list[str], typer.Option("--to", help="Canvas user ID; repeat for multiple recipients.")],
        subject: Annotated[str, typer.Option(help="Message subject.")],
        body: Annotated[str, typer.Option(help="Exact message body.")],
        course_id: Annotated[str | None, typer.Option("--course", help="Optional Canvas course context for this message.")] = None,
        group: Annotated[bool, typer.Option("--group", help="Create a shared group conversation.")] = False,
        confirmation_token: Confirm = None,
    ):
        invoke("send_conversation", {"recipients": recipients, "subject": subject, "body": body,
            "course_id": course_id, "group_conversation": group, "confirmation_token": confirmation_token})

    @inbox_app.command("reply")
    def inbox_reply(
        conversation_id: str,
        body: Annotated[str, typer.Option(help="Exact reply body.")],
        confirmation_token: Confirm = None,
    ):
        invoke("reply_to_conversation", {"conversation_id": conversation_id,
            "body": body, "confirmation_token": confirmation_token})

    @inbox_app.command("update")
    def inbox_update(conversation_id: str,
        state: Annotated[str, typer.Option(help="read, unread or archived.")],
        confirmation_token: Confirm = None,
    ):
        invoke("update_conversation", {"conversation_id": conversation_id,
            "workflow_state": state, "confirmation_token": confirmation_token})

    @discussion_app.command("post")
    def discussion_post(course_id: str, topic_id: str,
        message: Annotated[str, typer.Option(help="Exact post content (HTML supported by Canvas).")],
        confirmation_token: Confirm = None,
    ):
        invoke("post_discussion_entry", {"course_id": course_id, "topic_id": topic_id,
            "message": message, "confirmation_token": confirmation_token})

    @discussion_app.command("reply")
    def discussion_reply(course_id: str, topic_id: str, entry_id: str,
        message: Annotated[str, typer.Option(help="Exact reply content (HTML supported by Canvas).")],
        confirmation_token: Confirm = None,
    ):
        invoke("reply_to_discussion_entry", {"course_id": course_id, "topic_id": topic_id,
            "entry_id": entry_id, "message": message, "confirmation_token": confirmation_token})

    @submissions_app.command("comment")
    def submission_comment(course_id: str, assignment_id: str,
        comment: Annotated[str, typer.Option(help="Comment on your own submission.")],
        attempt: Annotated[int | None, typer.Option(min=1, help="Optional submission attempt.")] = None,
        confirmation_token: Confirm = None,
    ):
        invoke("add_submission_comment", {"course_id": course_id, "assignment_id": assignment_id,
            "comment": comment, "attempt": attempt, "confirmation_token": confirmation_token})

    @course_app.command("structure")
    def course_structure(course_id: str,
        include_unpublished: Annotated[bool, typer.Option("--unpublished/--published-only", help="Include unpublished content if Canvas permits.")] = True,
        modules_limit: Annotated[int, typer.Option(min=1, max=300)] = 100,
        items_limit: Annotated[int, typer.Option(min=1, max=300)] = 100,
    ):
        invoke("get_course_structure", {"course_id": course_id, "include_unpublished": include_unpublished,
            "modules_limit": modules_limit, "items_limit": items_limit})

    @course_app.command("module-items")
    def module_items(course_id: str, module_id: str, limit: Limit = 100):
        invoke("list_module_items", {"course_id": course_id, "module_id": module_id, "limit": limit})

    @course_app.command("module-done")
    def module_done(course_id: str, module_id: str, item_id: str,
        done: Annotated[bool, typer.Option("--done/--undo", help="Mark done or undo a must_mark_done item.")] = True,
        confirmation_token: Confirm = None,
    ):
        invoke("mark_module_item_done", {"course_id": course_id, "module_id": module_id,
            "item_id": item_id, "done": done, "confirmation_token": confirmation_token})
